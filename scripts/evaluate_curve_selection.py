"""Frozen-scene comparison of existing field curves and whole-curve selection."""
from pathlib import Path
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'python'), str(ROOT/'generators')]
import worker
import density_filament_selection as generator
from _curve_selection import build_pool, build_coverage, select_curves


def timed(function):
    start = time.perf_counter()
    result = function()
    return result, time.perf_counter()-start


def overlap(coverage, indices, run_length=24.):
    count = np.asarray(coverage.matrix[indices].sum(axis=0)).ravel()
    redundant = count >= 2
    total = 0.
    for i in indices:
        own = coverage.owner == i
        flags, arc = redundant[own], coverage.arc[own]
        cuts = np.r_[0, np.flatnonzero(np.diff(flags.astype(int)))+1, len(flags)]
        for a, b in zip(cuts[:-1], cuts[1:]):
            length = arc[a:b].sum()
            if flags[a] and length >= run_length:
                total += length
    return total


def main():
    out = ROOT/'build'
    cfg = json.loads((out/'selection-evaluation-settings.json').read_text())
    request = json.loads((out/'selection-evaluation-request.json').read_text())
    p = {e['key']: e['default'] for e in generator.PARAMETERS}
    p.update(request['params'])
    p.update(request['density_field'])
    field = tuple((e['key'], p[e['key']]) for e in generator.FIELD_PARAMETERS)
    growth = tuple((e['key'], p[e['key']]) for e in generator.LOCAL_PARAMETERS)
    build_pool.cache_clear()
    pool, growth_seconds = timed(lambda: build_pool(request['seed'], field, growth))
    coverage, coverage_seconds = timed(lambda: build_coverage(pool, 8., 30.))
    report = dict(seed=request['seed'], candidate_seed_rate=p['seed_rate'],
                  candidate_count=len(pool.paths), growth_seconds=growth_seconds,
                  coverage_seconds=coverage_seconds, coverage_pairs=coverage.matrix.nnz,
                  curve_controls={k:v for k,v in growth}, trials=[])
    rows = [('All candidates', np.arange(len(pool.paths)))]
    all_overlap = overlap(coverage, rows[0][1])
    report['all_parallel_arc_24'] = all_overlap
    report['all_arc'] = float(coverage.lengths.sum())
    for fraction in (.90, .95, .99, 1.):
        trial = {}
        indices, elapsed = timed(lambda: select_curves(pool, coverage, fraction, .5, 0., report=trial))
        trial.update(target=fraction, selection_seconds=elapsed,
                     parallel_arc_24=overlap(coverage, indices))
        report['trials'].append(trial)
        rows.append((f'{fraction:.0%} corridor coverage', indices))
    # Check byte identity against the actual old generator, with contacts off.
    plain = dict(request, generator='density_filament_curves', params=dict(request['params'], growth_join=0))
    off = dict(request, params=dict(request['params'], selection_enabled=0))
    for name, req in (('original', plain), ('off', off)):
        response = worker.generate_request(req, ROOT/'generators', out/f'selection-{name}.bin')
        if not response['ok']:
            raise RuntimeError(response['error'])
    report['off_curve_bytes_identical'] = (out/'selection-original.bin').read_bytes() == (out/'selection-off.bin').read_bytes()
    report['off_star_bytes_identical'] = (out/'selection-original.stars.bin').read_bytes() == (out/'selection-off.stars.bin').read_bytes()
    if not report['off_curve_bytes_identical'] or not report['off_star_bytes_identical']:
        raise AssertionError('Selection off must reproduce the original generator exactly')
    report['worker_runs'] = []
    for i in range(3):
        result, seconds = timed(lambda: worker.generate_request(request, ROOT/'generators', out/'selection-evaluation.bin'))
        if not result['ok']:
            raise RuntimeError(result['error'])
        report['worker_runs'].append(dict(seconds=seconds, stars=result['star_count'], vertices=result['count'], warnings=result['warnings']))
    (out/'selection-evaluation.json').write_text(json.dumps(report, indent=2))
    draw(cfg, pool, rows, out)
    print(json.dumps(report, indent=2), flush=True)


def draw(cfg, pool, rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from colorsys import hsv_to_rgb
    from _block_population import cell_uniform
    cam = cfg['camera']
    yaw, pitch = np.deg2rad([cam['yaw'], cam['pitch']])
    forward = np.array([-np.cos(pitch)*np.sin(yaw), -np.sin(pitch), -np.cos(pitch)*np.cos(yaw)])
    right = np.cross(forward, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    eye = np.array(cam['target'])-forward*cam['distance']
    colors = np.array([hsv_to_rgb(h,.65,1.) for h in cell_uniform(pool.owners,cfg['generator']['seed'],82421)])
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor='#070c11')
    for ax, (title, indices) in zip(axes.ravel(), rows[:4]):
        lines, rgb = [], []
        for i in indices:
            rel = pool.paths[i]-eye
            depth = rel@forward
            xy = np.column_stack((rel@right, rel@up))/np.maximum(depth[:,None], .001)/np.tan(np.deg2rad(45/2))
            xy[:,0] /= 1.6
            pairs = np.stack((xy[:-1],xy[1:]),axis=1)
            keep = np.minimum(depth[:-1],depth[1:]) > .16
            lines.extend(pairs[keep]); rgb.extend(np.tile(colors[i], (int(keep.sum()),1)))
        ax.set_facecolor('#070c11')
        ax.add_collection(LineCollection(lines, colors=rgb, linewidths=.6))
        ax.set(xlim=(-1,1), ylim=(-1,1)); ax.axis('off')
        ax.set_title(f'{title} | {len(indices)} curves', color='white')
    fig.suptitle('Existing density-guided curves: select whole paths, preserve their geometry\nSame saved camera and source-curve colors', color='white')
    fig.tight_layout()
    fig.savefig(out/'selection-camera-comparison.png', dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    main()
