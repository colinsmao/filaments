"""Frozen user-preset sweeps; no viewer settings writes or visible app launch."""
from pathlib import Path
import argparse
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'python'), str(ROOT/'generators')]
import worker
import density_population_selection as generator
from _curve_selection import build_pool
from _population_selection import build_sketch, select_population, sketch_parameters


def prepare(seed, p):
    start = time.perf_counter()
    pool = build_pool(seed, tuple((e['key'], p[e['key']]) for e in generator.FIELD_PARAMETERS),
                     tuple((e['key'], p[e['key']]) for e in generator.LOCAL_PARAMETERS), max_candidates=2048)
    pool_ms = 1000*(time.perf_counter()-start)
    start = time.perf_counter()
    sketch = build_sketch(pool, seed, sketch_parameters(p), p['select_samples'])
    return pool, sketch, dict(pool_ms=pool_ms, sketch_ms=1000*(time.perf_counter()-start))


def defaults(cfg):
    catalog, _, errors = worker.load_catalog(ROOT/'generators', block_units=True, density_graph=True)
    if errors:
        raise ValueError(errors)
    schema = next(e for e in catalog if e['id'] == 'density_population_selection')
    p = {e['key']:e['default'] for e in schema['parameters']}
    p.update(cfg['generator']['density_field'])
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, default=ROOT/'config/plot.json')
    parser.add_argument('--output', type=Path, default=ROOT/'build/incremental-evaluation')
    args = parser.parse_args()
    out = args.output
    cfg = json.loads(args.settings.read_text())
    out.mkdir(parents=True, exist_ok=True)
    (out/'settings.json').write_text(json.dumps(cfg, indent=2))
    seed = cfg['generator']['seed']
    base = defaults(cfg)
    trials = []
    for length in (120., 180., 240., 320.):
        for rate in (16., 32., 48., 64.):
            p = dict(base, strand_length=length, seed_rate=rate)
            pool, sketch, timing = prepare(seed, p)
            ids, kinds, stats = select_population(pool, sketch, p)
            row = dict(length=length, rate=rate, **stats, **timing)
            trials.append(row)
            print(json.dumps(row), flush=True)
    (out/'pool-sweep.json').write_text(json.dumps(trials, indent=2))
    pool, sketch, _ = prepare(seed, base)
    trials = []
    for ratio in (.036, .1, .2):
        for attraction in (.5, 1., 2.):
            for repulsion in (5., 15., 30.):
                p = dict(base, pop_rod_density=ratio, select_rod_attraction=attraction, select_rod_repulsion=repulsion)
                ids, kinds, stats = select_population(pool, sketch, p)
                trials.append(dict(ratio=ratio, attraction=attraction, repulsion=repulsion, **stats))
    (out/'rod-sweep.json').write_text(json.dumps(trials, indent=2))


if __name__ == '__main__':
    main()
