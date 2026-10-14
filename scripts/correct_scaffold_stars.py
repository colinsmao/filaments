"""Frozen trials for crowding, luminous-block excess and right-angle paths."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'generators')]
from evaluate_scaffold_stars import case, CAMERAS, sheet

OUT = ROOT / 'build/scaffold-stars/correction'
VIEWS = ('close_match', 'wide_match', 'whole', 'oblique')
PLACEMENT = dict(pop_density=.65, pop_spread_xz=.1, pop_spread_y=.08,
                 block_fraction=.0006, pop_clumping=.5, pop_clump_scale=12.)


def diagnostics(name):
    data = np.fromfile(OUT / f'{name}.stars.bin', dtype='<f4', offset=16).reshape(-1, 10)
    full = np.all(data[:, 7:10] == 1, axis=1)
    views = {}
    for view in VIEWS:
        c = CAMERAS[view]
        pitch, yaw = np.deg2rad([c['pitch'], c['yaw']])
        forward = np.array([-np.cos(pitch)*np.sin(yaw), -np.sin(pitch), -np.cos(pitch)*np.cos(yaw)])
        right = np.array([np.cos(yaw), 0., -np.sin(yaw)])
        up = np.cross(right, forward)
        eye = np.array(c['target']) - forward*c['distance']
        p = data[:, :3] - eye
        depth = p @ forward
        slope = np.tan(np.deg2rad(45)/2)
        inside = ((depth > .01) & (np.abs(p @ right) < depth*slope*1.6)
                  & (np.abs(p @ up) < depth*slope))
        views[view] = dict(objects=int(inside.sum()), full_block_centers_in_frame=int((inside & full).sum()))
    graph = np.load(OUT / f'{name}-graph.npz')
    angles = []
    for start, stop in zip(graph['path_offsets'][:-1], graph['path_offsets'][1:]):
        p = graph['cells'][graph['path_nodes'][start:stop]].astype(float)
        if len(p) < 3:
            continue
        arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
        q = np.arange(0., arc[-1], 4.)
        sample = np.column_stack([np.interp(q, arc, p[:, i]) for i in range(3)])
        d = np.diff(sample, axis=0)
        if len(d) < 2:
            continue
        norm = np.linalg.norm(d, axis=1)
        cosine = np.einsum('ij,ij->i', d[:-1], d[1:]) / np.maximum(norm[:-1]*norm[1:], 1e-9)
        angles.extend(np.rad2deg(np.arccos(np.clip(cosine, -1, 1))).tolist())
    result = dict(views=views, four_block_chord_turn_median=float(np.median(angles)),
                  four_block_chord_turn_over60_fraction=float(np.mean(np.asarray(angles) > 60)),
                  note='Projected object centers before occlusion; chord turns measure model geometry, not reference accuracy.')
    (OUT / f'{name}-diagnostics.json').write_text(json.dumps(result, indent=2))
    print(name, result, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((ROOT / 'reference-match-requirements.json').read_text())
    prior = json.loads((ROOT / 'build/scaffold-stars/selected-42-request.json').read_text())['params']
    trials = [
        ('rejected-42', prior),
        ('placement-42', dict(prior, **PLACEMENT)),
        ('gentler-42', dict(prior, **PLACEMENT, axis_run=1, turn_angle=20.,
                          branch_spacing=24, child_fraction=.4, trunk_length=180)),
    ]
    if 'bend' in sys.argv[1:]:
        base = dict(prior, **PLACEMENT, axis_run=1, turn_angle=25.)
        trials = [('independent-42', dict(base, bend_memory=0.)),
                  ('bending-42', dict(base, bend_memory=.9)),
                  ('bending-long-42', dict(base, bend_memory=.9, trunk_length=180,
                                           branch_spacing=18, child_fraction=.6))]
        source = OUT / 'bend-source'
        source.mkdir(exist_ok=True)
        for path in ('generators/_block_scaffold.py', 'generators/block_scaffold_stars.py',
                     'scripts/correct_scaffold_stars.py'):
            (source / Path(path).name).write_bytes((ROOT / path).read_bytes())
        (source / 'trial-intent.json').write_text(json.dumps(dict(
            requirements_version=ledger['version'],
            requirements_sha256=hashlib.sha256((ROOT / 'reference-match-requirements.json').read_bytes()).hexdigest(),
            targets=['V01', 'V02', 'V03', 'V05', 'V06'],
            risks=['Curling can shorten reach or cause self-contact stops.',
                   'Longer trunks can also enlarge branches; this third trial is not an isolated memory comparison.',
                   'All material, scale, appearance and void requirements remain mandatory.'],
            basis='Local probability bias over successive discrete slopes; no density or field.'), indent=2))
    if 'periods' in sys.argv[1:]:
        base = dict(prior, **PLACEMENT, root_count=12, cells_per_root=1600,
                    axis_run=1, bend_memory=.8, turn_angle=20., run_length=12,
                    trunk_length=320, child_length_cap=40, branch_spacing=6)
        trials = [('continuous-42', base),
                  ('periods-42', dict(base, branch_active_length=24, branch_quiet_length=40)),
                  ('periods-short-42', dict(base, branch_active_length=24, branch_quiet_length=24))]
        source = OUT / 'periods-source'
        source.mkdir(exist_ok=True)
        for path in ('generators/_block_scaffold.py', 'generators/block_scaffold_stars.py',
                     'scripts/correct_scaffold_stars.py'):
            (source / Path(path).name).write_bytes((ROOT / path).read_bytes())
        (source / 'trial-intent.json').write_text(json.dumps(dict(
            requirements_version=ledger['version'],
            targets=['V03', 'V05', 'V06', 'V07', 'V08'],
            risks=['Repeated patch spacing or abrupt patch transitions.',
                   'Curved long trunks may self-contact before making useful connections.',
                   'Child cap can create conspicuous similar-length branches.'],
            basis='Separate child lifetime cap; local active/quiet tip state with random period lengths. No predetermined patches or destinations.'), indent=2))
    for name, params in trials:
        params.pop('_block_units', None)
        case(name, 42, params, views=VIEWS, out=OUT)
        diagnostics(name)
    for view in ('close_match', 'wide_match'):
        prefix = 'periods' if 'periods' in sys.argv[1:] else 'bend' if 'bend' in sys.argv[1:] else 'first'
        sheet([n for n, _ in trials], view, f'{prefix}-{view}.png', out=OUT)


if __name__ == '__main__':
    main()
