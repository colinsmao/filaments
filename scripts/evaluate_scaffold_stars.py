"""Frozen native star renders; never edits presets or opens the visible viewer."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'python'), str(ROOT / 'generators'), str(ROOT / 'scripts')]
import worker
from _block_scaffold import grow
from evaluate_block_scaffold import freeze_graph

OUT = ROOT / 'build/scaffold-stars'
BASELINE = dict(mixed_materials=0, pop_density=.9, pop_curve_density_variation=.35,
                pop_spread_xz=.2, pop_spread_y=.1, pop_taper=0., pop_clumping=0.,
                pop_clump_scale=16., pop_rod_density=.2, pop_light_sky=.1,
                pop_light_ambient=.02, pop_light_brightness=1., rod_fraction=.1, block_fraction=.01)
CAMERAS = {
    'whole': dict(target=[0., 0., 0.], pitch=-75., yaw=35., distance=350.),
    'below': dict(target=[0., 0., 0.], pitch=-65., yaw=35., distance=160.),
    'close': dict(target=[0., 0., 0.], pitch=-75., yaw=35., distance=60.),
    'oblique': dict(target=[0., 0., 0.], pitch=-18., yaw=35., distance=260.),
    'close_match': dict(target=[0., 0., 0.], pitch=-75., yaw=35., distance=75.),
    'wide_match': dict(target=[0., 0., 0.], pitch=-75., yaw=35., distance=220.),
    # Apparent-size correction: two identifiable reference cubes are 20-28 px
    # in the 1200px comparison tile. Distance55 gives ~23x26px at target depth.
    # This is not a recovered reference camera or world-density calibration.
    'close_scale55': dict(target=[0., 0., 0.], pitch=-75., yaw=35., distance=55.),
}


def render(name, view, out=OUT):
    config = dict(background=[0., 0., 0.], size_scale=1.,
                  camera=dict(**CAMERAS[view], near_clip=.01, far_clip=10000.))
    camera = out / f'{name}-{view}-camera.json'
    camera.write_text(json.dumps(config, indent=2))
    ppm = out / f'{name}-{view}.ppm'
    subprocess.run([str(ROOT / 'build/check_lighting.exe'), 'scene',
                    str(out / f'{name}.stars.bin'), str(camera), str(ppm)],
                   check=True, capture_output=True, timeout=30)
    with Image.open(ppm) as image:
        image.save(ppm.with_suffix('.png'))


def case(name, seed, changes=None, views=('whole', 'below', 'close', 'oblique'), out=OUT):
    ledger_path = ROOT / 'reference-match-requirements.json'
    ledger = json.loads(ledger_path.read_text())
    # A regeneration invalidates previous judgments even if its name is reused.
    # Never silently carry forward a visual pass onto newly generated buffers.
    (out / f'{name}-requirements.json').write_bytes(ledger_path.read_bytes())
    pending = dict(candidate=name, verdict='not reviewed', requirements_version=ledger['version'],
                   checks={r['id']: dict(status='not_evaluated', reason='New generation requires visual review.', evidence=[])
                           for group in ('design_requirements', 'visual_requirements') for r in ledger[group]})
    (out / f'{name}-review.json').write_text(json.dumps(pending, indent=2))
    catalog, _, errors = worker.load_catalog(ROOT / 'generators', block_units=True)
    if errors:
        raise RuntimeError(errors)
    schema = next(s for s in catalog if s['id'] == 'block_scaffold_stars')
    params = {p['key']: p['default'] for p in schema['parameters']}
    unknown = set(changes or {}) - params.keys()
    if unknown:
        raise ValueError(f'Unknown trial controls: {unknown}')
    params.update(changes or {})
    request = dict(generator='block_scaffold_stars', world_units='blocks', seed=seed,
                   count=100000, params=params)
    (out / f'{name}-request.json').write_text(json.dumps(request, indent=2))
    response = worker.generate_request(request, ROOT / 'generators', out / f'{name}.bin')
    response.pop('catalog', None)
    (out / f'{name}-response.json').write_text(json.dumps(response, indent=2))
    if not response['ok']:
        raise RuntimeError(response)
    from block_scaffold_stars import GROWTH_KEYS
    graph = grow(seed, **{k: params[k] for k in GROWTH_KEYS})
    freeze_graph(graph, out / f'{name}-graph.npz')
    packed = np.fromfile(out / f'{name}.stars.bin', dtype='<f4', offset=16).reshape(-1, 10)
    shape = packed[:, 7:10]
    full = np.all(shape == 1, axis=1)
    rods = np.any(shape == 1, axis=1) & ~full
    pos = packed[:, :3]
    counts, _ = np.histogramdd(pos[:, [0, 2]], bins=[np.arange(-144, 145, 16)] * 2)
    row = dict(name=name, seed=seed, scaffold=graph.stats,
               objects=len(pos), candles=int((~full & ~rods).sum()), rods=int(rods.sum()),
               blocks=int(full.sum()), xz_16block_bin_counts=counts.astype(int).tolist(),
               source_sha256={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in
                              ('generators/_block_scaffold.py', 'generators/block_scaffold_stars.py',
                               'generators/_block_population.py')},
               integration_limited=response['block_integration_limited'], generation_ms=response['generation_ms'])
    (out / f'{name}-metrics.json').write_text(json.dumps(row, indent=2))
    for view in views:
        render(name, view, out)
    print(f"{name}: {len(pos)} stars ({row['candles']} candles, {row['rods']} rods, {row['blocks']} blocks); "
          f"{graph.stats['components']} scaffold components; {response['generation_ms']:.0f} ms", flush=True)
    return row


def sheet(names, view, filename, out=OUT):
    w, h = 800, 500
    canvas = Image.new('RGB', (w * len(names), h + 42), '#10151d')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    for i, name in enumerate(names):
        draw.text((i*w+12, 10), f'{name} / {view}', font=font, fill='white')
        with Image.open(out / f'{name}-{view}.png') as tile:
            canvas.paste(tile.resize((w, h), Image.Resampling.LANCZOS), (i*w, 42))
    canvas.save(out / filename)


def comparisons(out=OUT):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 26)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    manifest = {'reference_cameras_recovered': False, 'renderer': 'native cuboid proxies; black background; no exposure adjustment',
                'note': 'Crops/resizes only. Apparent scale is approximate; these do not establish physical reference density.', 'comparisons': []}
    for name in ['baseline-42'] + [f'selected-{s}' for s in (42, 1001, 763813, 1697566617, 1919363634)]:
        for view in ('close_match', 'wide_match'):
            render(name, view, out)
    for scale, ref, crop, model, model_crop in [
        ('close', 'Screenshot 2026-10-10 232941.png', (0, 200, 3600, 1800), 'close_match', (0, 145, 1600, 855)),
        ('wide', 'vlcsnap-2026-10-10-23h46m47s809.png', (0, 0, 2560, 1440), 'wide_match', (0, 50, 1600, 950)),
    ]:
        width, height = (1200, 533) if scale == 'close' else (1200, 675)
        canvas = Image.new('RGB', (2*width, height+130), '#10151d')
        draw = ImageDraw.Draw(canvas)
        draw.text((15, 12), f'{scale.upper()} / finished reference and populated unguided scaffold', font=font, fill='white')
        draw.text((15, 52), 'REFERENCE / '+ref, font=small, fill='#d1daea')
        draw.text((width+15, 52), 'GENERATED / selected population / unchanged scaffold / seed 42', font=small, fill='#d1daea')
        with Image.open(ROOT / 'scar' / ref) as im:
            canvas.paste(im.crop(crop).resize((width, height), Image.Resampling.LANCZOS), (0, 90))
        with Image.open(out / f'selected-42-{model}.png') as im:
            canvas.paste(im.crop(model_crop).resize((width, height), Image.Resampling.LANCZOS), (width, 90))
        draw.text((15, height+98), 'Different scenes and cameras. No brightness adjustment. Candle meshes, textures, planets and glow are absent from generated proxies.', font=small, fill='#d1daea')
        canvas.save(out / f'reference-{scale}-comparison.png')
        manifest['comparisons'].append(dict(scale=scale, reference=ref, reference_crop=crop,
                                              model=f'selected-42-{model}.png', model_crop=model_crop,
                                              tile_size=[width, height]))
    sheet(['baseline-42', 'selected-42'], 'close', 'population-before-after-close.png')
    sheet(['moderate-42', 'longer-42', 'longer-room-42'], 'below', 'growth-trial-comparison.png')
    seeds = (42, 1001, 763813, 1697566617, 1919363634)
    canvas = Image.new('RGB', (2400, 1120), '#10151d')
    draw = ImageDraw.Draw(canvas)
    for i, name in enumerate(['baseline-42'] + [f'selected-{s}' for s in seeds]):
        x, y = (i % 3)*800, (i // 3)*560
        draw.text((x+12, y+14), name+' / whole canopy / fixed camera', font=small, fill='white')
        with Image.open(out / f'{name}-whole.png') as im:
            canvas.paste(im.resize((800, 500), Image.Resampling.LANCZOS), (x, y+50))
    canvas.save(out / 'five-seed-whole-canopies.png')
    (out / 'comparison-manifest.json').write_text(json.dumps(manifest, indent=2))


def audit(out=OUT):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    import _block_population
    result = dict(scaffold_equivalence=[], legacy_population_equivalence=[], integration=[])
    previous = ROOT / 'build/block-scaffold/assessment/selected'
    for seed in (42, 1001, 763813, 1697566617, 1919363634):
        new = np.load(out / f'selected-{seed}-graph.npz')
        old = np.load(previous / f'verify-axis2-{seed}.npz')
        equal = all(np.array_equal(new[k], old[k]) for k in old.files)
        assert equal
        edges, cells = new['edges'], new['cells']
        sparse = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(cells),)*2)
        n, labels = connected_components(sparse, directed=False)
        stars = np.fromfile(out / f'selected-{seed}.stars.bin', dtype='<f4', offset=16).reshape(-1, 10)
        distance = cKDTree(cells+.5).query(stars[:, :3])[0]
        result['scaffold_equivalence'].append(dict(seed=seed, all_arrays_equal=equal, components=int(n),
            component_sizes=sorted(np.bincount(labels).tolist(), reverse=True),
            star_distance_to_scaffold_p99=float(np.quantile(distance, .99)), star_distance_max=float(distance.max())))
    for seed in (42, 1001, 1919363634):
        request = json.loads((out / f'baseline-{seed}-request.json').read_text())
        request['params']['mixed_materials'] = 0
        path = out / f'legacy-recheck-{seed}.bin'
        response = worker.generate_request(request, ROOT / 'generators', path)
        assert response['ok'], response
        equal = path.with_suffix('.stars.bin').read_bytes() == (out / f'baseline-{seed}.stars.bin').read_bytes()
        assert equal
        result['legacy_population_equivalence'].append(dict(seed=seed, star_buffer_equal=equal))
    original_budget = _block_population.MAX_PROBES
    try:
        _block_population.MAX_PROBES = 8_388_608
        for seed in (42, 1001):
            request = json.loads((out / f'selected-{seed}-request.json').read_text())
            output = out / f'probe-audit-{seed}.bin'
            response = worker.generate_request(request, ROOT / 'generators', output)
            assert response['ok'], response
            ordinary = np.fromfile(out / f'selected-{seed}.stars.bin', dtype='<f4', offset=16).reshape(-1, 10)
            fine = np.fromfile(output.with_suffix('.stars.bin'), dtype='<f4', offset=16).reshape(-1, 10)
            a, b = set(map(tuple, ordinary[:, :3])), set(map(tuple, fine[:, :3]))
            result['integration'].append(dict(seed=seed, normal_objects=len(a), higher_budget_objects=len(b),
                probes=response['block_probes'], integration_limited=response['block_integration_limited'],
                count_difference_fraction=(len(b)-len(a))/len(a),
                changed_cell_fraction=len(a ^ b)/len(a | b)))
    finally:
        _block_population.MAX_PROBES = original_budget
    result['scope'] = 'All geometry arrays unchanged; comparison is qualitative, not reference-camera recovery or a physical density measurement.'
    (out / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result['integration']), flush=True)
    source_dir = out / 'selected-source'
    source_dir.mkdir(exist_ok=True)
    for filename in ('generators/block_scaffold_stars.py', 'generators/_block_scaffold.py',
                     'generators/_block_population.py', 'scripts/evaluate_scaffold_stars.py'):
        shutil.copy2(ROOT / filename, source_dir / Path(filename).name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['baseline', 'sweep', 'materials', 'refine', 'verify', 'compare', 'audit'], default='baseline')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.phase == 'baseline':
        for seed in (42, 1001, 1919363634):
            case(f'baseline-{seed}', seed, BASELINE)
    elif args.phase == 'sweep':
        for name, params in [
            ('dense', dict(pop_density=2.)),
            ('wide', dict(pop_density=2., pop_spread_xz=.7, pop_spread_y=.35)),
            ('clumped', dict(pop_density=1.5, pop_clumping=1.5, pop_clump_scale=12.)),
            ('material-weights', dict(pop_density=1.3, pop_candle_weight=70., pop_rod_weight=23.,
                              pop_full_block_weight=7., pop_full_block_density=.2)),
        ]:
            case(f'{name}-42', 42, dict(BASELINE, **params))
        sheet(['baseline-42', 'dense-42', 'wide-42', 'clumped-42'], 'below', 'sweep-below.png')
    elif args.phase == 'materials':
        for name, params in [
            ('mixed', dict(mixed_materials=1)),
            ('mixed-thicker', dict(mixed_materials=1, pop_density=1.3,
                                   pop_spread_xz=.45, pop_spread_y=.25)),
            ('mixed-varied', dict(mixed_materials=1, pop_density=1.3,
                                  pop_spread_xz=.45, pop_spread_y=.25,
                                  pop_clumping=1., pop_clump_scale=12.)),
        ]:
            case(f'{name}-42', 42, dict(BASELINE, **params))
        sheet(['baseline-42', 'mixed-42', 'mixed-thicker-42', 'mixed-varied-42'], 'below', 'materials-below.png')
    elif args.phase == 'refine':
        selected = dict(mixed_materials=1, pop_density=1.1, pop_spread_xz=.35,
                        pop_spread_y=.2, pop_clumping=1.5, pop_clump_scale=12.,
                        rod_fraction=.075, block_fraction=.006)
        for name, delta in [
            ('moderate', {}),
            ('sparser', dict(pop_density=.75)),
            ('longer', dict(trunk_length=180)),
            ('longer-room', dict(trunk_length=180, cells_per_root=1200)),
        ]:
            case(f'{name}-42', 42, dict(selected, **delta))
        sheet(['moderate-42', 'sparser-42', 'longer-42', 'longer-room-42'], 'whole', 'refine-whole.png')
    elif args.phase == 'compare':
        comparisons()
    elif args.phase == 'audit':
        audit()
    else:
        for seed in (42, 1001, 763813, 1697566617, 1919363634):
            case(f'selected-{seed}', seed)


if __name__ == '__main__':
    main()
