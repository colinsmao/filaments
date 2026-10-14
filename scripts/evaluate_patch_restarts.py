"""Compare patch restarts across seeds on a frozen preset; no live settings edits."""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'python'),str(ROOT/'generators'),str(ROOT/'scripts')]
from evaluate_population_selection import defaults,prepare
from _population_selection import select_population,population_proximity


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings',type=Path,default=ROOT/'config/plot.json')
    parser.add_argument('--output',type=Path,default=ROOT/'build/patch-restarts')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(args.settings.read_text());g=cfg['generator']
    (args.output/'settings.json').write_text(json.dumps(cfg,indent=2))
    p=defaults(cfg);p.update(g['parameters']['density_population_selection']);p.update(g['density_field'])
    seeds=list(dict.fromkeys([g['seed'],1213151058,1697566617,42,137,555,1001,8712,29117,91037,328461,763813]))
    rows=[]
    for seed in seeds:
        pool,sketch,_=prepare(seed,p)
        # XZ coverage of 16-block bins with >1 expected candidate candle.
        cells,inverse=np.unique(np.floor(sketch.points[:,[0,2]]/16).astype(int),axis=0,return_inverse=True)
        potential=np.bincount(inverse,weights=sketch.weights,minlength=len(cells));active=potential>1.
        for enabled in (0,1):
            # Warm cache before reporting selection-only timing.
            values=dict(p,select_restart_patches=enabled)
            select_population(pool,sketch,values)
            started=time.perf_counter();ids,roles,stats=select_population(pool,sketch,values)
            elapsed=1000*(time.perf_counter()-started)
            candles=ids[roles==0];selected=np.isin(sketch.owners,candles)
            filled=np.bincount(inverse[selected],weights=sketch.weights[selected],minlength=len(cells))
            near=population_proximity(sketch,p['select_isolation_distance'])[candles][:,candles].max(axis=1).toarray().ravel()
            row=dict(seed=seed,restarts_enabled=enabled,**stats,warm_ms=elapsed,
                     bin_coverage=float(np.mean(filled[active]>1.)),
                     isolated_short=int(np.count_nonzero(pool.short_mask[candles]&(near<np.exp(-1.)))))
            rows.append(row)
            print(json.dumps({k:row[k] for k in ('seed','restarts_enabled','candles','rods','patch_restarts','bin_coverage','isolated_short','warm_ms')}),flush=True)
    (args.output/'results.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':main()
