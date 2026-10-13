"""Reproducible saved-density ablation; writes only under build/, no viewer.

Run with the configured project Python. The first run snapshots plot.json;
subsequent runs reuse that snapshot. Matplotlib views are diagnostic projections,
not native material renders. Metrics use unfaded curves before population.
"""
from pathlib import Path
import json
import sys
import time
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'python'), str(ROOT/'generators'), str(ROOT/'.tools/noise-python')]
import worker
from _density_field import build_field
from _curve_corpus import build_corpus, score_corpus, select_candidates, footprints, unpack_paths


def timed(call):
    start = time.perf_counter()
    value = call()
    return value, time.perf_counter()-start


def main():
    out = ROOT/'build'
    snapshot = out/'corpus-evaluation-settings.json'
    if not snapshot.exists():
        snapshot.write_bytes((ROOT/'config/plot.json').read_bytes())
    cfg = json.loads(snapshot.read_text())
    scene = cfg['generator']
    field = dict(scene['density_field'])
    resolution = field.pop('field_resolution')
    (rho, _, half), field_time = timed(lambda: build_field(scene['seed'], resolution=resolution, **field))
    saved = scene['parameters']['density_filament_curves']
    # Evaluate the same anchor region as the saved growth scene, while retaining
    # an independent corpus seed and parametric octave-noise formula.
    region = {k: saved[k] for k in ('seed_xz', 'seed_y_pos', 'seed_y_neg')}
    kwargs = dict(corpus_seed=173, cell_size=64., per_cell=32, span=128., bend=.8,
                  vertical=.15, axis_bias=0., wavelength=96., octaves=3, roughness=.25, **region)
    build_corpus.cache_clear()
    (points, ids), corpus_time = timed(lambda: build_corpus(tuple(half), **kwargs))
    (_, samples), scoring_time = timed(lambda: score_corpus(points, rho, half, .5, 1.))
    footprint, footprint_time = timed(lambda: footprints(samples, half, 32.))
    coords = np.indices(rho.shape).reshape(3, -1).T/(np.array(rho.shape)-1)*2*half-half
    domain = np.all((coords >= -half*[region['seed_xz'], region['seed_y_neg'], region['seed_xz']]) &
                    (coords <= half*[region['seed_xz'], region['seed_y_pos'], region['seed_xz']]), axis=1)
    targets, target_mass = coords[domain], rho.ravel()[domain]
    target_mass = target_mass/target_mass.sum()
    variants = [('Uniform', 0., 0., 0.), ('Mean density', 1., 0., 0.),
                ('Sustained', 1., 1., 0.), ('Tight sustained', 2., 1., 0.),
                ('Sustained + spread', 1., 1., 2.), ('Tight + spread', 2., 1., 2.)]
    report = dict(seed=scene['seed'], field=scene['density_field'], corpus=kwargs,
                  candidate_count=len(points), candidate_segments=int(np.count_nonzero(np.linalg.norm(np.diff(points, axis=1), axis=2))),
                  density_seconds=field_time, corpus_seconds=corpus_time,
                  scoring_seconds=scoring_time, footprint_seconds=footprint_time, trials=[])
    paths_by_name = {}
    selections = {}
    for name, binding, continuity, diversity in variants:
        score = samples['mean']*samples['support']**continuity
        selected, elapsed = timed(lambda: select_candidates(score, ids, 128, 173, binding, diversity, footprint))
        selections[name] = selected
        paths = unpack_paths(points, selected)
        paths_by_name[name] = paths
        mask = np.isin(samples['owner'], selected)
        q, arc, density = samples['points'][mask], samples['arc'][mask], samples['density'][mask]
        distance = cKDTree(q).query(targets)[0]
        length = arc.sum()
        entry = dict(name=name, binding=binding, continuity=continuity, diversity=diversity,
                     selected=len(selected), length=float(length), selection_seconds=elapsed,
                     mean_density=float(np.sum(arc*density)/length/rho.max()),
                     void_arc_fraction=float(arc[density < .01*rho.max()].sum()/length),
                     effective_support=float(np.average(samples['support'][selected], weights=samples['lengths'][selected])),
                     density_mass_within_12=float(target_mass[distance <= 12].sum()),
                     density_mass_within_24=float(target_mass[distance <= 24].sum()))
        report['trials'].append(entry)
        print(json.dumps(entry), flush=True)
    # Same selection heuristics over larger prefix corpora. Recompute scores so
    # these timings include the actual added candidates, not a scaled estimate.
    report['pool_sizes'] = []
    for copies in (8, 64):
        (p, key), geom = timed(lambda: build_corpus(tuple(half), **dict(kwargs, per_cell=copies)))
        (score, data), cost = timed(lambda: score_corpus(p, rho, half, .5, 1.))
        selected = select_candidates(score, key, 128, 173, binding=2.)
        mask = np.isin(data['owner'], selected)
        distance = cKDTree(data['points'][mask]).query(targets)[0]
        report['pool_sizes'].append(dict(copies=copies, candidates=len(p), geometry_seconds=geom, scoring_seconds=cost,
            mean_density=float(np.average(data['density'][mask], weights=data['arc'][mask])/rho.max()),
            density_mass_within_12=float(target_mass[distance<=12].sum())))
    # Actual shared population, proxy shapes, postprocessing and accepted lighting.
    local = {k: v for k, v in saved.items() if k.startswith(('pop_', 'pp_', 'fade_'))}
    local.update(region, corpus_seed=173, corpus_cell=64., corpus_copies=32, corpus_span=128.,
                 corpus_bend=.8, corpus_vertical=.15, corpus_axis_bias=0., corpus_wavelength=96.,
                 corpus_octaves=3, corpus_roughness=.25, select_count=128,
                 select_power=.5, select_continuity=1., select_binding=1., select_diversity=0.)
    request = dict(generator='density_curve_corpus', count=scene['count'], seed=scene['seed'],
        world_units='blocks', density_graph=True, density_field=scene['density_field'], params=local)
    (out/'corpus-evaluation-request.json').write_text(json.dumps(request, indent=2))
    report['worker_runs'] = []
    for i in range(3):
        response, elapsed = timed(lambda: worker.generate_request(request, ROOT/'generators', out/'corpus-evaluation.bin'))
        if not response.get('ok'):
            raise RuntimeError(response.get('error'))
        report['worker_runs'].append(dict(seconds=elapsed, count=response['count'], stars=response['star_count'], warnings=response['warnings']))
    # Independent target: synthetic tube through an otherwise empty box.
    small_half = np.array([96., 24., 96.])
    axis = [np.linspace(-h, h, 49) for h in small_half]
    tube = np.exp(-(axis[1][None,:,None]**2+axis[2][None,None,:]**2)/(2*6**2))*np.ones((49,1,1))
    tube_points, tube_ids = build_corpus(tuple(small_half), per_cell=64, cell_size=32., span=80.)
    _, data = score_corpus(tube_points, tube, small_half, .5, 1.)
    report['tube'] = []
    for name, binding, continuity, _ in variants[:4]:
        selected = select_candidates(data['mean']*data['support']**continuity, tube_ids, 24, 173, binding)
        p = unpack_paths(tube_points, selected)
        delta = np.concatenate([np.diff(x, axis=0) for x in p])
        length = np.linalg.norm(delta, axis=1)
        report['tube'].append(dict(name=name, axial_alignment=float(np.sum(np.abs(delta[:,0]))/length.sum()),
                                  effective_support=float(np.mean(data['support'][selected]))))
    (out/'corpus-evaluation.json').write_text(json.dumps(report, indent=2))
    draw(out, rho, half, paths_by_name, samples, selections, cfg)
    print(json.dumps({k:v for k,v in report.items() if k not in ('trials','field')}, indent=2), flush=True)


def draw(out, rho, half, paths_by_name, samples, selections, cfg):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), facecolor='#090f16')
    image = np.sqrt(rho.mean(axis=1)/rho.mean(axis=1).max()).T
    for ax, (name, paths) in zip(axes.ravel(), paths_by_name.items()):
        ax.set_facecolor('#090f16')
        ax.imshow(image, origin='lower', extent=[-half[0],half[0],-half[2],half[2]], cmap='magma', vmin=0, vmax=1, alpha=.75)
        ax.add_collection(LineCollection([p[:,[0,2]] for p in paths], colors='#a0e5fa', linewidths=.65, alpha=.8))
        ax.set(xlim=(-half[0], half[0]), ylim=(-half[2], half[2]), aspect='equal')
        ax.set_title(name, color='white')
        ax.tick_params(colors='#b0c0d0')
    fig.suptitle('Same independent octave-noise curves, 128 selected | XZ projection over mean density\nSelection changes membership only; line colors are diagnostic', color='white')
    fig.tight_layout()
    fig.savefig(out/'corpus-selection-comparison.png', dpi=135)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor='#090f16')
    name = 'Sustained'
    ax = axes[0]
    ax.set_title('Selected curves | side view XY', color='white')
    ax.add_collection(LineCollection([p[:, :2] for p in paths_by_name[name]], colors='#a0e5fa', linewidths=.65))
    ax.set(xlim=(-half[0],half[0]), ylim=(-half[1],half[1]), aspect='equal')
    raw = (out/'corpus-evaluation.stars.bin').read_bytes()
    stride = 10 if raw[:8] == b'FSTAR003' else 7
    stars = np.frombuffer(raw, dtype='<f4', offset=16).reshape(-1,stride)
    axes[1].scatter(stars[:,0], stars[:,2], c=np.clip(stars[:,3:6],0,1), s=2., linewidths=0)
    axes[1].set(xlim=(-half[0],half[0]), ylim=(-half[2],half[2]), aspect='equal')
    axes[1].set_title(f'Shared population | XZ, {len(stars):,} objects', color='white')
    for ax in axes:
        ax.set_facecolor('#090f16')
        ax.tick_params(colors='#b0c0d0')
    fig.suptitle('Diagnostic projections (not native perspective/material rendering)', color='white')
    fig.tight_layout()
    fig.savefig(out/'corpus-population.png', dpi=135)
    plt.close(fig)


if __name__ == '__main__':
    main()
