"""Frozen isolation-penalty sweeps; never writes live viewer settings."""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'python'),str(ROOT/'generators'),str(ROOT/'scripts')]
import worker
import density_population_selection as generator
from evaluate_population_selection import defaults,prepare
from _population_selection import select_population,population_proximity
from _curve_selection import short_candidates


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings',type=Path,default=ROOT/'config/plot.json')
    parser.add_argument('--output',type=Path,default=ROOT/'build/isolation-evaluation')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(args.settings.read_text())
    (args.output/'settings.json').write_text(json.dumps(cfg,indent=2))
    p=defaults(cfg)
    p.update(cfg['generator']['parameters']['density_population_selection'])
    p.update(cfg['generator']['density_field'])
    seed=cfg['generator']['seed']
    pool,sketch,timing=prepare(seed,p)
    print(json.dumps(dict(preparation=timing,candidates=len(pool.paths))),flush=True)
    short=short_candidates(pool.owners,seed,p['short_curve_fraction'])
    # Fixed 8-block diagnostic graph so reach sweeps use the same isolation test.
    diagnostic=population_proximity(sketch,8.)
    rows=[]
    for reach in (4.,8.,12.):
        for strength in (0.,.5,.75,.9,1.,1.1):
            if strength==0. and reach!=4.:
                continue
            values=dict(p,select_isolation=strength,select_isolation_distance=reach)
            ids,kinds,stats=select_population(pool,sketch,values)
            candles=ids[kinds==0]
            near=diagnostic[candles][:,candles].max(axis=1).toarray().ravel()
            is_short=short[candles]
            row=dict(strength=strength,reach=reach,**stats,
                     short_candles=int(is_short.sum()),
                     isolated_short_4=int(np.count_nonzero(is_short&(near<np.exp(-.25)))),
                     isolated_short_8=int(np.count_nonzero(is_short&(near<np.exp(-1.)))))
            rows.append(row)
            print(json.dumps(row),flush=True)
    (args.output/'sweep.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':
    main()
