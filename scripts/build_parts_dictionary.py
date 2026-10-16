"""Import a reusable parts library from a locally installed Minecraft client JAR.

Only declared parts are imported. Generated copyrighted game assets stay under
ignored build/. Mesh positions are in blocks; textures retain their source alpha.
This importer handles the axis-aligned multipart models used by the catalog,
and rejects unsupported model features instead of silently approximating them.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import math
import struct
import sys
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'generators'))
from _block_lighting import light_colors

DIRECTIONS = {'north': 1, 'east': 2, 'south': 4, 'west': 8}


def identifier(value):
    namespace, name = value.split(':', 1) if ':' in value else ('minecraft', value)
    if namespace != 'minecraft' or '..' in name:
        raise ValueError(f'Unsupported asset identifier: {value}')
    return name


class Importer:
    def __init__(self, archive):
        self.archive = archive
        self.models = {}
        self.textures = {}
        self.texture_data = []
        self.texture_sources = []

    def read(self, name):
        return json.loads(self.archive.read('assets/minecraft/' + name))

    def model(self, name):
        name = identifier(name)
        if name not in self.models:
            raw = self.read('models/' + name + '.json')
            parent = self.model(raw['parent']) if 'parent' in raw else {}
            resolved = {**parent, **raw}
            resolved['textures'] = {**parent.get('textures', {}), **raw.get('textures', {})}
            self.models[name] = resolved
        return self.models[name]

    def texture(self, name, aliases):
        visited = set()
        while name.startswith('#'):
            if name in visited:
                raise ValueError('Cyclic texture reference')
            visited.add(name)
            name = aliases[name[1:]]
        name = identifier(name)
        if name not in self.textures:
            source = 'assets/minecraft/textures/' + name + '.png'
            raw = self.archive.read(source)
            im = Image.open(io.BytesIO(raw)).convert('RGBA')
            frame = 0
            try:
                animation = json.loads(self.archive.read(source + '.mcmeta')).get('animation', {})
                frames = animation.get('frames', [0])
                frame = frames[0].get('index', 0) if isinstance(frames[0], dict) else frames[0]
            except KeyError:
                pass
            if im.width != 16 or im.height % 16:
                raise ValueError(f'Expected native 16px block texture: {source}: {im.size}')
            im = im.crop((0, frame * 16, 16, (frame + 1) * 16))
            self.textures[name] = len(self.texture_data)
            self.texture_data.append(im.tobytes())
            self.texture_sources.append(dict(name=name, sha256=hashlib.sha256(raw).hexdigest(), frame=frame))
        return self.textures[name]

    def applications(self, block, state):
        definitions = self.read('blockstates/' + block + '.json')
        if 'multipart' in definitions:
            for item in definitions['multipart']:
                when = item.get('when', {})
                if any(key in ('OR', 'AND') for key in when):
                    raise ValueError('Complex multipart condition not supported by this catalog')
                if all(state.get(key) in value.split('|') for key, value in when.items()):
                    yield item['apply']
        else:
            for key, application in definitions['variants'].items():
                wanted = dict(v.split('=') for v in key.split(',')) if key else {}
                if all(state.get(k) == v for k, v in wanted.items()):
                    yield application
                    return
            raise ValueError(f'No model for {block} {state}')

    def mesh(self, block, state):
        faces = []
        self.face_cull = []
        for application in self.applications(block, state):
            # Stable representative for weighted texture rotations, no RNG.
            if isinstance(application, list):
                application = application[0]
            if application.get('x', 0):
                raise ValueError('X-rotated models are outside the initial parts catalog')
            model = self.model(application['model'])
            angle = math.radians(application.get('y', 0))
            rotation = np.array([[math.cos(angle), 0, -math.sin(angle)],
                                 [0, 1, 0], [math.sin(angle), 0, math.cos(angle)]])
            for element in model.get('elements', []):
                if 'rotation' in element:
                    raise ValueError('Rotated model element is not supported')
                x0, y0, z0 = element['from']
                x1, y1, z1 = element['to']
                # Quad order: UV top-left, bottom-left, bottom-right, top-right;
                # winding faces outward. Original per-face UVs remain unscaled.
                corners = {
                    'north': [[x1,y1,z0],[x1,y0,z0],[x0,y0,z0],[x0,y1,z0]],
                    'south': [[x0,y1,z1],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1]],
                    'west': [[x0,y1,z0],[x0,y0,z0],[x0,y0,z1],[x0,y1,z1]],
                    'east': [[x1,y1,z1],[x1,y0,z1],[x1,y0,z0],[x1,y1,z0]],
                    'up': [[x0,y1,z0],[x0,y1,z1],[x1,y1,z1],[x1,y1,z0]],
                    'down': [[x0,y0,z1],[x0,y0,z0],[x1,y0,z0],[x1,y0,z1]],
                }
                default_uv = {
                    'north': [16-x1,16-y1,16-x0,16-y0],
                    'south': [x0,16-y1,x1,16-y0],
                    'west': [z0,16-y1,z1,16-y0],
                    'east': [16-z1,16-y1,16-z0,16-y0],
                    'up': [x0,z0,x1,z1], 'down': [x0,16-z1,x1,16-z0],
                }
                for direction, face in element['faces'].items():
                    uv = face.get('uv', default_uv[direction])
                    u0,v0,u1,v1 = np.array(uv) / 16.
                    texcoords = [[u0,v0],[u0,v1],[u1,v1],[u1,v0]]
                    turn = face.get('rotation', 0) // 90
                    texcoords = texcoords[-turn:] + texcoords[:-turn] if turn else texcoords
                    # Fence top/bottom textures need the blockstate UV lock.
                    if application.get('uvlock') and direction in ('up','down'):
                        steps = application.get('y', 0) // 90
                        for _ in range(steps):
                            texcoords = [[1-v,u] if direction == 'up' else [v,1-u] for u,v in texcoords]
                    xyz = (np.array(corners[direction], float) / 16. - .5) @ rotation.T
                    normal = np.cross(xyz[1]-xyz[0], xyz[2]-xyz[0])
                    normal /= np.linalg.norm(normal)
                    layer = self.texture(face['texture'], model['textures'])
                    faces.append(np.column_stack((xyz, np.tile(normal,(4,1)), texcoords, np.full(4,layer))).round(7).tolist())
                    normals={'north':[0,0,-1],'south':[0,0,1],'west':[-1,0,0],'east':[1,0,0],'up':[0,1,0],'down':[0,-1,0]}
                    cull=np.array(normals[face['cullface']] if 'cullface' in face else [0,0,0]) @ rotation.T
                    self.face_cull.append(cull.round().astype(int).tolist())
        if not faces:
            raise ValueError(f'Empty part: {block} {state}')
        return faces


def build(jar, catalog_path, output):
    catalog = json.loads(catalog_path.read_text())
    parts = []
    with zipfile.ZipFile(jar) as archive:
        importer = Importer(archive)
        def add(block, category, state=None, **properties):
            state = state or {}
            faces = importer.mesh(block, state)
            xyz = np.array(faces)[:,:,:3].reshape(-1,3)
            key = block + ('[' + ','.join(f'{k}={v}' for k,v in sorted(state.items())) + ']' if state else '')
            parts.append(dict(id=key, name=block.replace('_',' ').title(), block=block,
                              category=category, state=state, faces=faces, face_cull=importer.face_cull,
                              bounds=[xyz.min(0).tolist(),xyz.max(0).tolist()],
                              dimensions=(xyz.max(0)-xyz.min(0)).round(7).tolist(),
                              emission=properties.pop('emission',0),
                              pane_attach=properties.pop('pane_attach',False),
                              translucent=properties.pop('translucent',False), **properties))
        add('white_concrete', 'reference', pane_attach=True)
        for core in catalog['core_blocks']:
            properties = core.copy()
            if not isinstance(properties.get('pane_attach'), bool):
                raise ValueError('Declare pane_attach for every core; model bounds do not establish attachment')
            block = properties.pop('block')
            state_string = properties.pop('state', '')
            state = dict(s.split('=') for s in state_string.split(',')) if state_string else {}
            add(block, 'core', state, **properties)
        for colour in catalog['glass_colours']:
            block = 'glass' if colour == 'clear' else colour + '_stained_glass'
            add(block, 'glass', translucent=True, colour=colour, pane_attach=True)
            for mask in range(16):
                state = {key: str(bool(mask & bit)).lower() for key,bit in DIRECTIONS.items()}
                add(block + '_pane', 'pane', state, translucent=True, colour=colour, connections=mask, pane_attach=True)
        for block in catalog['fences']:
            for mask in range(16):
                state = {key: str(bool(mask & bit)).lower() for key,bit in DIRECTIONS.items()}
                add(block, 'fence', state, connections=mask)
        output.mkdir(parents=True, exist_ok=True)
        atlas = b''.join(importer.texture_data)
        (output / 'textures.rgba').write_bytes(struct.pack('<4sIII', b'PTEX',16,16,len(importer.texture_data)) + atlas)
        document = dict(version=1, source=dict(jar=jar.name, sha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                        catalog_sha256=hashlib.sha256(catalog_path.read_bytes()).hexdigest()),
                        units='blocks', textures=importer.texture_sources, parts=parts,
                        light_colours=light_colors(np.arange(16), catalog['lighting']).tolist(),
                        lighting=catalog['lighting'],
                        limitations=['Static first animation frame.', 'Gallery omits Minecraft ambient occlusion and shadows.',
                                     'Only catalogued axis-aligned models are imported.',
                                     'Block emission and pane attachment are declared in the catalog; neither is stored in model JSON.'])
        (output / 'parts.json').write_text(json.dumps(document,separators=(',',':')),encoding='utf8')
        print(f'Built {len(parts)} parts, {len(importer.texture_data)} native textures from {jar.name} in {output}')
        return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, default=ROOT/'parts/catalog.json')
    parser.add_argument('--output', type=Path, default=ROOT/'build/parts-library')
    args = parser.parse_args()
    build(args.jar,args.catalog,args.output)
