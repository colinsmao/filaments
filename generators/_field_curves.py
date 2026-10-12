"""Batched finite field growth with local contacts, without neighbor forces."""
import numpy as np
from scipy.special import betaincinv
from _block_population import cell_uniform
from _density_curves import DensityShape
from _guided_walk import VectorNoise, unit
from _block_contacts import BlockContacts
from _proximity_contacts import ProximityContacts

PARAMETERS = [
    dict(key='growth_response', label='Growth response length (blocks)', type='float', default=8., min=1., max=128.),
    dict(key='growth_pull', label='Transverse density attraction', type='float', default=.35, min=0., max=2.),
    dict(key='growth_wander', label='Growth wandering', type='float', default=.15, min=0., max=1.),
    dict(key='growth_join', label='Join nearby curves', type='int', default=1, min=0, max=1, toggle=True),
    dict(key='growth_join_distance', label='Join distance (blocks; 0 = shared block)', type='float', default=16., min=0., max=64., enabled_if='growth_join'),
    dict(key='growth_join_angle', label='Join alignment angle (degrees)', type='float', default=30., min=0., max=90., enabled_if='growth_join'),
]


def grow_field(density, half, cells, seed, mean_length, variation=.5,
               response=8., pull=.35, wandering=.15, joining=True, join_angle=30., report=None,
               join_distance=0.):
    """Each accepted block starts one two-way curve, with a coordinate-keyed budget.

    The density Hessian supplies a local preferred axis where one is clear;
    a bounded transverse gradient bends toward density. Neither creates a
    centerline or projects a root. Contacts stop arriving tips without forces,
    budget transfer, moving old geometry or spawning children.
    """
    if not len(cells):
        return [], np.empty((0, 3), dtype=np.int64)
    half = np.asarray(half, dtype=float)
    roots = cells.astype(float)+.5
    field = DensityShape(density, half, response)
    offsets = np.column_stack([128*cell_uniform(cells, seed, 17620+i) for i in range(3)])
    preferred = unit(offsets-64.)
    launch, _, _ = field.sample(roots, preferred)
    missing = np.linalg.norm(launch, axis=1) < 1e-8
    launch[missing] = preferred[missing]
    budgets = mean_length*(1+variation*(2*betaincinv(2, 2, cell_uniform(cells, seed, 17612))-1))
    positions = np.repeat(roots, 2, axis=0)
    headings = np.repeat(launch, 2, axis=0)*np.tile([1., -1.], len(cells))[:, None]
    remaining = np.repeat(budgets/2, 2)
    offsets = np.repeat(offsets, 2, axis=0)
    noise = VectorNoise(seed, 4*response, 0, 2, .35) if wandering else None
    step = response/2
    # Keep geometric sampling independent of seed count. Fail clearly rather
    # than silently shorten paths or change their step when extra seeds appear.
    max_steps = int(np.ceil(remaining.max()/step))
    if max_steps*len(positions) > 8_000_000:
        raise ValueError('Growth exceeds 8 million tip steps; reduce seed rate or length, or increase response length')
    history = np.empty((max_steps+1, len(positions), 3), dtype=np.float64)
    history[0] = positions
    counts = np.ones(len(positions), dtype=int)
    active = remaining > 1e-9
    contacts = ((ProximityContacts(join_distance, join_angle, half) if join_distance > 0 else BlockContacts(join_angle))
                if joining else None)
    join_count = 0
    bridges = {}
    for iteration in range(max_steps):
        ids = np.flatnonzero(active)
        if not len(ids):
            break
        p, h = positions[ids], headings[ids]
        tangent, gradient, confidence = field.sample(p)
        tangent *= np.where(np.sum(tangent*h, axis=1) < 0, -1., 1.)[:, None]
        sideways = gradient-h*np.sum(gradient*h, axis=1)[:, None]
        attraction = sideways*response
        attraction /= np.maximum(1., np.linalg.norm(attraction, axis=1)[:, None])
        desired = h + confidence[:, None]*(tangent-h) + pull*attraction
        if noise is not None:
            perturbation = noise.sample(p, offsets[ids])
            perturbation[:, np.setdiff1d(np.arange(3), field.axes)] = 0
            desired += wandering*perturbation
        ds = np.minimum(step, remaining[ids])
        heading = unit(h + (-np.expm1(-ds/response))[:, None]*(unit(desired)-h))
        delta = ds[:, None]*heading
        # Clip the last segment at the actual domain boundary.
        distances = np.full_like(delta, np.inf)
        np.divide(half-np.sign(delta)*p, np.abs(delta), out=distances, where=np.abs(delta)>1e-12)
        fraction = np.clip(distances.min(axis=1), 0., 1.)
        updated = p + fraction[:, None]*delta
        valid = fraction*ds > 1e-9
        joined = np.zeros(len(ids), dtype=bool)
        if contacts is not None:
            # Coordinate-sorted roots break ties between fresh parallel fronts.
            # Proximity queries use accepted geometry from previous batches.
            if join_distance > 0:
                rows = np.flatnonzero(valid)
                updated[rows], joined[rows] = contacts.advance_batch(p[rows], updated[rows], ids[rows]//2, remaining[ids[rows]])
                for row, bridge in contacts.bridges.items():
                    if np.linalg.norm(bridge[-1]-bridge[0]) > 1e-9:
                        bridges[int(ids[rows[row]])] = bridge
            else:
                for row in np.flatnonzero(valid):
                    updated[row], joined[row] = contacts.advance(p[row], updated[row], int(ids[row]//2), remaining[ids[row]])
            join_count += int(joined.sum())
            valid &= np.linalg.norm(updated-p, axis=1) > 1e-9
        kept = ids[valid]
        history[iteration+1, kept] = updated[valid]
        counts[kept] += 1
        positions[ids], headings[ids] = updated, heading
        remaining[ids] -= ds
        active[ids] = valid & ~joined & (fraction >= 1.) & (remaining[ids] > 1e-9)
    paths, owners = [], []
    for i, cell in enumerate(cells):
        a, b = 2*i, 2*i+1
        tips = []
        for tip in (b, a):
            polyline = history[:counts[tip], tip]
            if tip in bridges:
                polyline = np.concatenate((polyline[:-1], bridges[tip][1:]))
            tips.append(polyline)
        path = np.concatenate((tips[0][::-1], tips[1][1:]))
        if len(path) > 1:
            paths.append(path)
            owners.append(cell)
    if report is not None:
        report.update(joined_tips=join_count, occupied_blocks=len(contacts.cells) if isinstance(contacts, BlockContacts) else 0)
    return paths, np.asarray(owners, dtype=np.int64)
