"""Scale-controlled, scaffold-only native comparisons from fixed random seeds.

No viewer settings or star population are used. Reference crops are inspection
evidence, never generator inputs. Cameras and crops are recorded next to images.
"""
from pathlib import Path
import argparse
import hashlib
import inspect
import json
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'generators'), str(ROOT / 'scripts')]
from _block_scaffold import grow
from evaluate_block_scaffold import freeze_graph, write_buffer

SEEDS = [42, 1001, 763813, 1697566617, 1919363634]
CAMERAS = {
    'patch': dict(target=[0., 0., 0.], pitch=12., yaw=35., distance=65.),
    'detail': dict(target=[0., 0., 0.], pitch=12., yaw=35., distance=50.),
    'overview': dict(target=[0., 0., 0.], pitch=28., yaw=35., distance=440.),
    'top': dict(target=[0., 0., 0.], pitch=89., yaw=0., distance=370.),
    'side': dict(target=[0., 0., 0.], pitch=0., yaw=0., distance=370.),
    'near': dict(target=[0., 0., 0.], pitch=-12., yaw=35., distance=170.),
}


def axis_runs(cells, paths):
    runs = [[], [], []]
    for path in paths:
        steps = np.diff(cells[path], axis=0)
        if not len(steps):
            continue
        cuts = np.r_[0, np.flatnonzero(np.any(steps[1:] != steps[:-1], axis=1)) + 1, len(steps)]
        for a, b in zip(cuts[:-1], cuts[1:]):
            runs[int(np.argmax(np.abs(steps[a])))].append(int(b - a))
    return {axis: dict(count=len(r), median=float(np.median(r)),
                       p90=float(np.quantile(r, .9)), maximum=max(r),
                       at_least_four=sum(n >= 4 for n in r)) if r else {}
            for axis, r in zip('XYZ', runs)}


def metrics(graph):
    # Geometry diagnostics only: no reference-derived density or occupancy target.
    terminal = [s for p, s in zip(graph.paths, graph.stops) if len(p) > 1]
    return dict(axis_runs=axis_runs(graph.cells, graph.paths),
                grown_tips=len(terminal), cap_stopped_grown_tips=terminal.count('cell_cap'),
                cap_stopped_fraction=terminal.count('cell_cap') / max(1, len(terminal)))


def render(out, name, binary, view):
    camera = dict(background=[.12, .15, .19], size_scale=1.,
                  camera=dict(**CAMERAS[view], near_clip=.01, far_clip=10000.))
    camera_path = out / f'{name}-{view}-camera.json'
    camera_path.write_text(json.dumps(camera, indent=2))
    ppm = out / f'{name}-{view}.ppm'
    subprocess.run([str(ROOT / 'build/check_lighting.exe'), 'scene', str(binary),
                    str(camera_path), str(ppm)], check=True, capture_output=True, timeout=30)
    with Image.open(ppm) as image:
        image.save(ppm.with_suffix('.png'))


def case(out, name, seed, changes, views):
    params = {k: v.default for k, v in inspect.signature(grow).parameters.items() if k != 'seed'}
    params.update(changes)
    graph = grow(seed, **params)
    freeze_graph(graph, out / f'{name}.npz')
    row = dict(name=name, seed=seed, params=params, stats=graph.stats, metrics=metrics(graph),
               source_sha256=hashlib.sha256((ROOT / 'generators/_block_scaffold.py').read_bytes()).hexdigest())
    (out / f'{name}.json').write_text(json.dumps(row, indent=2))
    binary = out / f'{name}.bin'
    write_buffer(binary, graph.cells + .5, np.full((len(graph.cells), 3), [.68, .72, .76]),
                 np.ones((len(graph.cells), 3)))
    for view in views:
        render(out, name, binary, view)
    print(f"{name}: {len(graph.cells)} cells, {graph.stats['components']} components; "
          f"vertical runs >=4: {row['metrics']['axis_runs']['Y'].get('at_least_four', 0)}", flush=True)
    return row


def sheet(out, names, views, filename, title):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 25)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    w, h = 800, 500
    image = Image.new('RGB', (w * len(views), 68 + 556 * len(names)), '#11151d')
    draw = ImageDraw.Draw(image)
    draw.text((14, 12), title, font=font, fill='white')
    draw.text((14, 40), 'Same camera and block size within each column; colors do not mark branches.', font=small, fill='#bbc8dc')
    for i, name in enumerate(names):
        row = json.loads((out / f'{name}.json').read_text())
        for j, view in enumerate(views):
            x, y = j * w, 68 + i * 556
            label = f"{name} / {view} / {row['stats']['cells']} cells"
            draw.text((x + 12, y + 12), label, font=small, fill='white')
            with Image.open(out / f'{name}-{view}.png') as tile:
                image.paste(tile.resize((w, h), Image.Resampling.LANCZOS), (x, y + 48))
    image.save(out / filename)


def comparisons(out, axis):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 27)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    reference = ROOT / 'scar/vlcsnap-2026-10-11-19h55m59s233.png'
    reference_crop = (1300, 440, 1900, 1040)
    generated_crop = (500, 200, 1100, 800)
    rows = []
    for a in (1, axis):
        rows.append(case(out, f'detail-axis{a}-1001', 1001,
                         dict(root_count=1, width=120, height=48, axis_run=a), ('detail',)))
    image = Image.new('RGB', (1860, 790), '#11151d')
    draw = ImageDraw.Draw(image)
    draw.text((20, 14), 'Local scaffold / reference, original stepping, revised stepping', font=font, fill='white')
    tiles = [(reference, reference_crop, 'REFERENCE / 19:55:59'),
             (out / 'detail-axis1-1001-detail.png', generated_crop, 'BEFORE / seed 1001 / axis mean 1'),
             (out / f'detail-axis{axis}-1001-detail.png', generated_crop, f'AFTER / seed 1001 / axis mean {axis}')]
    for i, (path, crop, label) in enumerate(tiles):
        x = 20 + i * 620
        draw.text((x, 60), label, font=small, fill='#d0d8e4')
        with Image.open(path) as tile:
            image.paste(tile.crop(crop), (x, 100))
    draw.text((20, 712), 'Similar apparent block size: reference post is about 24 px wide; a generated vertical edge at target depth is about 24 px.', font=small, fill='#d0d8e4')
    draw.text((20, 740), 'Before/after cameras and crops are identical. Reference camera differs. Only the reference contains candles.', font=small, fill='#d0d8e4')
    image.save(out / 'reference-before-after.png')
    manifest = dict(reference=str(reference.relative_to(ROOT)), reference_crop=reference_crop,
                    generated_crop=generated_crop, generated_camera=CAMERAS['detail'],
                    reference_post_scan_rows=[695, 710, 725], reference_post_width_pixels=[24, 24, 24],
                    note='Approximate local apparent scale, not camera recovery or a physical density calibration.')

    # All five scene views have the same camera, including the first (selection)
    # seed. No rescaling to each individual bounding box or omission of gaps.
    names = [f'verify-axis{axis}-{seed}' for seed in SEEDS]
    for name in names:
        render(out, name, out / f'{name}.bin', 'overview')
    overview_ref = ROOT / 'scar/vlcsnap-2026-10-11-19h54m55s953.png'
    overview_crop = (450, 180, 2210, 1050)
    image = Image.new('RGB', (1640, 1700), '#11151d')
    draw = ImageDraw.Draw(image)
    draw.text((20, 14), 'Whole scaffold / reference and five fixed seeds', font=font, fill='white')
    draw.text((20, 51), 'Generated views share one camera. Reference view is qualitative; construction access paths remain visible.', font=small, fill='#d0d8e4')
    tiles = [(overview_ref, overview_crop, 'REFERENCE / 19:54:55')]
    for name in names:
        row = json.loads((out / f'{name}.json').read_text())
        tiles.append((out / f'{name}-overview.png', (180, 210, 1420, 985),
                      f"SEED {row['seed']} / {row['stats']['cells']} cells / {row['stats']['components']} components"))
    for i, (path, crop, label) in enumerate(tiles):
        x, y = 20 + (i % 2) * 810, 90 + (i // 2) * 530
        draw.text((x, y), label, font=small, fill='white')
        with Image.open(path) as tile:
            tile = tile.crop(crop)
            tile.thumbnail((790, 490), Image.Resampling.LANCZOS)
            image.paste(tile, (x + (790 - tile.width) // 2, y + 31 + (490 - tile.height) // 2))
    image.save(out / 'reference-five-seeds.png')
    manifest.update(overview_reference=str(overview_ref.relative_to(ROOT)),
                    overview_reference_crop=overview_crop, overview_generated_crop=(180, 210, 1420, 985))
    (out / 'comparison-manifest.json').write_text(json.dumps(manifest, indent=2))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('sweep', 'verify', 'compare'), default='sweep')
    parser.add_argument('--axis-run', type=int, default=2)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/block-scaffold/assessment')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    if args.phase == 'sweep':
        for axis in [1, 2, 3, 4]:
            for seed in SEEDS[:3]:
                rows.append(case(out, f'axis{axis}-patch-{seed}', seed,
                                 dict(root_count=1, width=120, height=48, axis_run=axis), ('patch',)))
            rows.append(case(out, f'axis{axis}-canopy-42', 42, dict(axis_run=axis),
                             ('overview', 'top', 'near')))
        for seed in SEEDS[:3]:
            sheet(out, [f'axis{a}-patch-{seed}' for a in [1, 2, 3, 4]], ('patch',),
                  f'axis-sweep-patch-{seed}.png', f'Axis hold sweep / seed {seed}')
        sheet(out, [f'axis{a}-canopy-42' for a in [1, 2, 3, 4]], ('overview', 'near'),
              'axis-sweep-canopy.png', 'Axis hold sweep / seed 42')
    elif args.phase == 'verify':
        for seed in SEEDS:
            for axis in [1, args.axis_run]:
                rows.append(case(out, f'verify-axis{axis}-{seed}', seed, dict(axis_run=axis),
                                 ('overview', 'top', 'side', 'near')))
        for view in ('overview', 'near'):
            # Each row compares exactly the same seed and camera.
            names = [f'verify-axis{a}-{s}' for s in SEEDS for a in [1, args.axis_run]]
            sheet(out, names, (view,), f'verify-{view}.png', 'Baseline / revised, five fixed seeds')
    else:
        rows = comparisons(out, args.axis_run)
    (out / f'{args.phase}-results.json').write_text(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
