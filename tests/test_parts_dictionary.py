"""Checks on the imported geometry and original local texture data."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import os
import struct
import tempfile
import unittest
import zipfile
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('parts_importer',ROOT/'scripts/build_parts_dictionary.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PartsDictionaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=ROOT/'build/parts-library'
        if not (cls.directory/'parts.json').exists():
            raise unittest.SkipTest('Import a local client archive before testing the parts library')
        cls.library=json.loads((cls.directory/'parts.json').read_text())

    def test_every_connection_has_actual_expected_bounds(self):
        panes=[p for p in self.library['parts'] if p['category']=='pane']
        self.assertEqual(len(panes),160)
        for p in panes:
            m=p['connections']
            low=[-.5 if m&8 else -.0625,-.5,-.5 if m&1 else -.0625]
            high=[.5 if m&2 else .0625,.5,.5 if m&4 else .0625]
            np.testing.assert_allclose(p['bounds'],[low,high],atol=1e-7)
            np.testing.assert_allclose(p['dimensions'],np.subtract(high,low),atol=1e-7)

    def test_faces_have_valid_winding_and_texture_indices(self):
        ids=set()
        for part in self.library['parts']:
            self.assertNotIn(part['id'],ids); ids.add(part['id'])
            self.assertGreaterEqual(part['emission'],0); self.assertLessEqual(part['emission'],15)
            for face in part['faces']:
                a=np.array(face)
                normal=np.cross(a[1,:3]-a[0,:3],a[2,:3]-a[0,:3])
                normal/=np.linalg.norm(normal)
                np.testing.assert_allclose(a[:,3:6],np.tile(normal,(4,1)),atol=1e-6)
                self.assertTrue(np.all(a[:,8]>=0))
                self.assertTrue(np.all(a[:,8]<len(self.library['textures'])))

    def test_pane_attachment_is_explicit_not_inferred_from_cube_bounds(self):
        parts={p['block']:p for p in self.library['parts']}
        for part in self.library['parts']:
            self.assertIsInstance(part['pane_attach'],bool)
        for name in ('honey_block','jack_o_lantern','pumpkin'):
            self.assertFalse(parts[name]['pane_attach'],name)
        for name in ('sea_lantern','moss_block','glass','slime_block','pink_stained_glass_pane'):
            self.assertTrue(parts[name]['pane_attach'],name)
        # Jack-o'-lanterns look like full cubes but are connection exceptions.
        self.assertEqual(parts['jack_o_lantern']['dimensions'],[1,1,1])

    def test_source_pane_cull_flags_follow_each_rotated_arm(self):
        for p in self.library['parts']:
            self.assertEqual(len(p['faces']),len(p['face_cull']))
            if p['category']=='pane':
                expected=[d for bit,d in enumerate(([0,0,-1],[1,0,0],[0,0,1],[-1,0,0])) if p['connections']&(1<<bit)]
                actual=[d for d in p['face_cull'] if any(d)]
                self.assertEqual(sorted(actual),sorted(expected))

    def test_source_pixels_and_alpha_are_preserved(self):
        jar=Path(os.environ.get('APPDATA',''))/'.minecraft/versions/1.19.3/1.19.3.jar'
        if not jar.exists() or jar.name!=self.library['source']['jar']:
            self.skipTest('Original local client archive unavailable')
        raw=(self.directory/'textures.rgba').read_bytes()
        self.assertEqual(struct.unpack('<4sIII',raw[:16]),(b'PTEX',16,16,len(self.library['textures'])))
        with zipfile.ZipFile(jar) as z:
            for i,tex in enumerate(self.library['textures']):
                png=z.read('assets/minecraft/textures/'+tex['name']+'.png')
                self.assertEqual(hashlib.sha256(png).hexdigest(),tex['sha256'])
                source=Image.open(io.BytesIO(png)).convert('RGBA')
                frame=source.crop((0,16*tex['frame'],16,16*(tex['frame']+1))).tobytes()
                self.assertEqual(raw[16+i*1024:16+(i+1)*1024],frame)

    def test_repeat_import_is_byte_identical(self):
        jar=Path(os.environ.get('APPDATA',''))/'.minecraft/versions/1.19.3/1.19.3.jar'
        if not jar.exists() or jar.name!=self.library['source']['jar']:
            self.skipTest('Original local client archive unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)
            module.build(jar,ROOT/'parts/catalog.json',output)
            for file in ('parts.json','textures.rgba'):
                self.assertEqual((output/file).read_bytes(),(self.directory/file).read_bytes())

    def test_importer_refuses_unhandled_element_rotation(self):
        importer=module.Importer(None)
        importer.applications=lambda *args: [{'model':'test'}]
        importer.model=lambda *args: {'elements':[{'rotation':{'angle':22.5}}]}
        with self.assertRaisesRegex(ValueError,'Rotated model element'):
            importer.mesh('test',{})


if __name__=='__main__':
    unittest.main()
