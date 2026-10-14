"""Freeze and render scaffold-only trials; never read/write the viewer preset.

Uses the existing hidden native build/check_lighting.exe diagnostic. Exported
FSTAR003 records are diagnostic cubes/graph links, not generated star population.
"""
from pathlib import Path
import argparse
import json
import inspect
import hashlib
import struct
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'generators'))
from _block_scaffold import grow, cell_colors


def write_buffer(path, positions, colors, shapes):
    records = np.column_stack((positions, colors, np.ones(len(positions)), shapes)).astype('<f4')
    path.write_bytes(b'FSTAR003' + struct.pack('<Q', len(records)) + records.tobytes())


def freeze_graph(graph, path):
    offsets = np.cumsum([0] + [len(p) for p in graph.paths])
    np.savez_compressed(path, cells=graph.cells, edges=graph.edges,
                        path_nodes=np.concatenate(graph.paths), path_offsets=offsets,
                        parents=graph.parents, roots=graph.roots, owners=graph.owners,
                        cell_paths=graph.cell_paths)


def render_case(out, name, seed, params, views=('oblique', 'top', 'side', 'links'), fixed_camera=False):
    params = dict({k: p.default for k, p in inspect.signature(grow).parameters.items() if k != 'seed'}, **params)
    started = time.perf_counter()
    graph = grow(seed, **params)
    elapsed = time.perf_counter() - started
    freeze_graph(graph, out / (name + '.npz'))
    row = dict(name=name, seed=seed, params=params, seconds=elapsed,
               source_sha256=hashlib.sha256((ROOT / 'generators/_block_scaffold.py').read_bytes()).hexdigest(),
               **graph.stats)
    (out / (name + '.json')).write_text(json.dumps(row, indent=2))
    centers = graph.cells.astype(float) + .5
    degree = np.bincount(graph.edges.ravel(), minlength=len(centers))
    colors = cell_colors(graph, True)
    colors[degree >= 3] = [1., .9, .35]
    colors[graph.roots] = [1., .25, .35]
    write_buffer(out / (name + '-blocks.bin'), centers, colors, np.ones((len(centers), 3)))
    # Axis-aligned thin beams display explicit graph edges using the same native
    # cube renderer. Root/junction markers are diagnostic, not emitters.
    pairs = centers[graph.edges]
    positions = pairs.mean(axis=1)
    shapes = np.maximum(np.abs(pairs[:, 1] - pairs[:, 0]), .13)
    edge_colors = (colors[graph.edges[:, 0]] + colors[graph.edges[:, 1]]) * .5
    marked = np.flatnonzero(degree >= 3)
    marked = np.unique(np.concatenate((marked, graph.roots)))
    write_buffer(out / (name + '-links.bin'), np.concatenate((positions, centers[marked])),
                 np.concatenate((edge_colors, colors[marked])),
                 np.concatenate((shapes, np.full((len(marked), 3), .65))))
    target = ((centers.min(axis=0) + centers.max(axis=0)) * .5).tolist()
    span = np.ptp(centers, axis=0) + 1
    distance = max(span.max() * 1.4, 25.)
    if fixed_camera:
        target, distance = [0., 0., 0.], 140.
    for view in views:
        pitch, yaw = {'oblique': (28., 35.), 'top': (89., 0.),
                      'side': (0., 0.), 'below': (-45., 35.), 'links': (28., 35.)}[view]
        if not fixed_camera:
            # Fit all eight corners of the unit-cell bounds in the actual 45deg
            # perspective frustum, including near-side depth. A single span
            # multiplier can crop below views of a wide shallow scaffold.
            bounds = np.stack((centers.min(axis=0) - .5, centers.max(axis=0) + .5))
            corners = np.asarray([(x, y, z) for x in bounds[:, 0] for y in bounds[:, 1]
                                  for z in bounds[:, 2]]) - np.asarray(target)
            p, y = np.deg2rad([pitch, yaw])
            forward = np.asarray([-np.cos(p) * np.sin(y), -np.sin(p), -np.cos(p) * np.cos(y)])
            right = np.asarray([np.cos(y), 0., -np.sin(y)])
            up = np.cross(right, forward)
            depth = corners @ forward
            tangent = np.tan(np.deg2rad(22.5))
            required = max(np.max(np.abs(corners @ right) / (tangent * 1.6) - depth),
                           np.max(np.abs(corners @ up) / tangent - depth))
            distance = max(25., required * 1.12 + 2.)
        camera = dict(background=[.075, .09, .115], size_scale=1.,
                      camera=dict(target=target, pitch=pitch, yaw=yaw, distance=distance,
                                  near_clip=.01, far_clip=10000.))
        camera_path = out / f'{name}-{view}-camera.json'
        camera_path.write_text(json.dumps(camera, indent=2))
        binary = out / f"{name}-{'links' if view == 'links' else 'blocks'}.bin"
        ppm = out / f'{name}-{view}.ppm'
        subprocess.run([str(ROOT / 'build/check_lighting.exe'), 'scene', str(binary),
                        str(camera_path), str(ppm)], check=True, capture_output=True, timeout=30)
        with Image.open(ppm) as im:
            im.save(out / f'{name}-{view}.png')
    print(json.dumps(row), flush=True)
    return row


def sheet(out, rows, name, views):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 23)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    im = Image.new('RGB', (800 * len(views), 560 * len(rows)), '#11151d')
    draw = ImageDraw.Draw(im)
    for i, row in enumerate(rows):
        title = f"{row['name']} | {row['cells']} cells, {row['forks']} junctions, {row['cycles']} cycles"
        draw.text((12, i * 560 + 5), title, font=font, fill='white')
        for j, view in enumerate(views):
            draw.text((j * 800 + 12, i * 560 + 33), view + ' / scaffold only', font=small, fill='#b9c7dd')
            with Image.open(out / f"{row['name']}-{view}.png") as tile:
                tile = tile.resize((800, 500))
                im.paste(tile, (j * 800, i * 560 + 60))
    im.save(out / name)


def reference_sheet(out):
    """Untraced reference context beside raw scaffold renders; no match claim."""
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 25)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    im = Image.new('RGB', (1920, 1420), '#11151d')
    draw = ImageDraw.Draw(im)
    rows = [
        ('REFERENCE: construction views (include access scaffolding and other objects)',
         [(ROOT / 'scar/vlcsnap-2026-10-11-19h54m55s953.png', 'Overview'),
          (ROOT / 'scar/vlcsnap-2026-10-11-19h55m43s259.png', 'Below')]),
        ('UNGUIDED TRIAL: seed 42, scaffold cells only; colors identify paths',
         [(out / 'canopy-42-oblique.png', 'Oblique'), (out / 'canopy-42-below.png', 'Below')]),
    ]
    for i, (title, tiles) in enumerate(rows):
        y = i * 690
        draw.text((16, y + 10), title, font=font, fill='white')
        for j, (path, label) in enumerate(tiles):
            draw.text((j * 960 + 16, y + 49), label, font=small, fill='#bbc8dc')
            with Image.open(path) as tile:
                tile.thumbnail((960, 600))
                im.paste(tile, (j * 960 + (960 - tile.width) // 2, y + 82 + (600 - tile.height) // 2))
    draw.text((16, 1390), 'Qualitative comparison. Reference camera and exact 3D scaffold have not been reconstructed.',
              font=small, fill='#bbc8dc')
    im.save(out / 'reference-comparison.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/block-scaffold')
    parser.add_argument('--phase', choices=('first', 'variants', 'verify'), default='first')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.phase == 'first':
        rows = [render_case(out, f'patch-{s}', s, dict(root_count=1, width=120, height=48))
                for s in [42, 1001, 763813, 1697566617, 1919363634]]
        sheet(out, rows, 'first-patches.png', ('oblique', 'top', 'links'))
        full = render_case(out, 'first-canopy', 42, dict(width=275, height=55, root_count=24),
                           ('oblique', 'top', 'side', 'below'))
        sheet(out, [full], 'first-canopy.png', ('oblique', 'top', 'side'))
        rows.append(full)
    elif args.phase == 'variants':
        variants = [('baseline', {}), ('long-runs', dict(run_length=14, turn_angle=35.)),
                    ('short-turns', dict(run_length=5, turn_angle=70.)),
                    ('fewer-forks', dict(branch_spacing=20)),
                    ('more-forks', dict(branch_spacing=7)),
                    ('short-children', dict(child_fraction=.45))]
        rows = [render_case(out, name, 42, dict(root_count=1, width=120, height=48, **changes),
                            ('oblique', 'top'), fixed_camera=True) for name, changes in variants]
        sheet(out, rows, 'variants.png', ('oblique', 'top'))
    else:
        rows = [render_case(out, f'canopy-{s}', s, dict(width=275, height=55, root_count=24),
                            ('oblique', 'top', 'side', 'below'))
                for s in [42, 1001, 763813, 1697566617, 1919363634]]
        sheet(out, rows, 'canopy-seeds.png', ('oblique', 'top'))
        reference_sheet(out)
    (out / f'{args.phase}-results.json').write_text(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
