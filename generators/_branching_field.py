"""Rooted, budget-conserving branches in the shared density field."""
import numpy as np
from scipy.special import betaincinv
from _block_population import cell_uniform
from _density_curves import DensityShape
from _guided_walk import VectorNoise, unit

PARAMETERS = [
    dict(key='branch_root_rate', label='Mean roots per million blocks', type='float', default=.5, min=0., max=100., slider_max=5.),
    dict(key='branch_length', label='Mean total length per root (blocks)', type='float', default=1200., min=1., max=10000.),
    dict(key='branch_spacing', label='Branch opportunity spacing (blocks)', type='float', default=48., min=4., max=256.),
    dict(key='branch_angle', label='Branch departure angle (degrees)', type='float', default=45., min=15., max=80.),
]


def grow_branches(density, half, cells, seed, length=1200., variation=.5,
                  response=8., pull=.35, wandering=.15, spacing=48., angle=45., report=None):
    """Every child begins on its parent and receives 35% of its remaining budget.

    Independent roots never merge. Spatial hashing only rejects crowded births;
    field sampling is batched, with no deposited-segment searches or guide paths.
    """
    if not len(cells):
        return [], np.empty((0, 3), dtype=np.int64)
    half = np.asarray(half, dtype=float)
    field = DensityShape(density, half, response)
    noise = VectorNoise(seed, 4*response, 0, 2, .35) if wandering else None
    step = min(response/2, spacing/8)
    budgets = length*(1+variation*(2*betaincinv(2, 2, cell_uniform(cells, seed, 17612))-1))
    if budgets.sum()/step > 2_000_000:
        raise ValueError('Branch growth exceeds 2 million steps; reduce roots or total length')
    roots = cells.astype(float)+.5
    preferred = unit(np.column_stack([cell_uniform(cells, seed, 17620+i)-.5 for i in range(3)]))
    launches, _, _ = field.sample(roots, preferred)
    missing = np.linalg.norm(launches, axis=1) < 1e-8
    launches[missing] = preferred[missing]
    paths, tips, root_ids, parents, keys = [], [], [], [], []
    occupied = set()
    cell_size = max(response, spacing/4)
    def cell(point):
        return tuple(np.floor(point/cell_size).astype(int))
    def new_tip(root, parent, point, heading, budget, key, child=False):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 29113, *map(lambda v: int(v) & 0xffffffff, cells[root]), key]))
        index = len(paths)
        paths.append([point.copy()]); root_ids.append(root); parents.append(parent); keys.append(key)
        tips.append(dict(index=index, p=point.copy(), h=heading.copy(), budget=budget,
                         travel=0., next=spacing*rng.uniform(.75,1.25), rng=rng,
                         offset=rng.uniform(0,128,3), child=child,
                         visited={cell(point)}, last=cell(point), forks=0))
        occupied.add(cell(point))
    for root in range(len(cells)):
        new_tip(root, -1, roots[root], launches[root], budgets[root]/2, 1)
        new_tip(root, -1, roots[root], -launches[root], budgets[root]/2, 2)
    active = list(tips)
    rejected = 0
    while active:
        points = np.array([t['p'] for t in active])
        headings = np.array([t['h'] for t in active])
        tangent, gradient, confidence = field.sample(points)
        tangent *= np.where(np.sum(tangent*headings,axis=1) < 0, -1., 1.)[:,None]
        sideways = gradient-headings*np.sum(gradient*headings,axis=1)[:,None]
        attraction = sideways*response
        attraction /= np.maximum(1.,np.linalg.norm(attraction,axis=1)[:,None])
        # Children first leave their trunk; then smoothly regain normal guidance.
        freedom = np.array([min(1., t['travel']/spacing)**2 if t['child'] else 1. for t in active])
        desired = headings + freedom[:,None]*(confidence[:,None]*(tangent-headings)+pull*attraction)
        if noise is not None:
            perturbation = noise.sample(points, np.array([t['offset'] for t in active]))
            perturbation[:, np.setdiff1d(np.arange(3), field.axes)] = 0
            desired += wandering*perturbation
        ds = np.array([min(step,t['budget']) for t in active])
        heading = unit(headings + (-np.expm1(-ds/response))[:,None]*(unit(desired)-headings))
        delta = ds[:,None]*heading
        distances = np.full_like(delta,np.inf)
        np.divide(half-np.sign(delta)*points,np.abs(delta),out=distances,where=np.abs(delta)>1e-12)
        fraction = np.clip(distances.min(axis=1),0,1)
        next_active = []
        for row,t in enumerate(active):
            travel = ds[row]*fraction[row]
            if travel <= 1e-9:
                continue
            point = points[row]+fraction[row]*delta[row]
            voxel = cell(point)
            # Stop a tip before it loops back through its own earlier route.
            if voxel != t['last'] and voxel in t['visited']:
                continue
            t['visited'].add(voxel); t['last'] = voxel; occupied.add(voxel)
            paths[t['index']].append(point.copy())
            t.update(p=point, h=heading[row], budget=t['budget']-travel, travel=t['travel']+travel)
            if fraction[row] < 1 or t['budget'] <= 1e-9:
                continue
            if t['travel'] >= t['next']:
                t['next'] += spacing*t['rng'].uniform(.75,1.25)
                if .35*t['budget'] >= spacing:
                    # Explore a cone around the heading. Prefer density-supported
                    # departures, but sample rather than always choosing one side.
                    h = t['h']
                    normal = unit(np.cross(h, np.eye(3)[np.argmin(np.abs(h))]))
                    other = np.cross(h,normal)
                    phi = t['rng'].uniform(0,2*np.pi)+np.arange(8)*np.pi/4
                    directions = np.cos(np.deg2rad(angle))*h + np.sin(np.deg2rad(angle))*(np.cos(phi)[:,None]*normal+np.sin(phi)[:,None]*other)
                    if len(field.axes) == 2:
                        directions[:,1] = 0
                        directions = unit(directions)
                    probes = point+directions*(spacing*.75)
                    available = np.array([cell(p) not in occupied for p in probes]) & (np.abs(probes)<half).all(axis=1)
                    candidates = np.flatnonzero(available)
                    if len(candidates):
                        values = field.log_value(probes[candidates])
                        weights = np.exp(np.clip(values-values.max(),-20,0))
                        chosen = t['rng'].choice(candidates,p=weights/weights.sum())
                        child_budget = .35*t['budget']; t['budget'] -= child_budget
                        t['forks'] += 1
                        # Local identity does not depend on other roots' growth.
                        key = int(np.random.SeedSequence([keys[t['index']],t['forks']]).generate_state(1)[0])
                        new_tip(root_ids[t['index']], t['index'], point, directions[chosen], child_budget, key, True)
                        next_active.append(tips[-1])
                    else:
                        rejected += 1
            next_active.append(t)
        active = next_active
    # Keep a root's two halves as one population path: no artificial material
    # seam or tip taper at the middle of the trunk.
    result, output_roots, output_parents, remap = [], [], [], {}
    for root in range(len(cells)):
        a,b = 2*root,2*root+1
        trunk = np.asarray(paths[b][::-1]+paths[a][1:])
        if len(trunk)>1:
            remap[a] = remap[b] = len(result)
            result.append(trunk); output_roots.append(root); output_parents.append(-1)
    for i in range(2*len(cells), len(paths)):
        if len(paths[i])>1:
            remap[i] = len(result)
            result.append(np.asarray(paths[i])); output_roots.append(root_ids[i])
            output_parents.append(remap[parents[i]])
    owners = np.asarray([cells[root] for root in output_roots], dtype=np.int64).reshape(-1,3)
    if report is not None:
        report.update(root_count=len(cells), branch_count=sum(p>=0 for p in output_parents),
                      parents=output_parents, root_ids=output_roots,
                      root_budgets=budgets, rejected_births=rejected)
    return result, owners
