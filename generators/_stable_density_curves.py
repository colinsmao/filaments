"""Fixed pair-zero paths, fixed arc-length roots, smoothly varying travel budgets."""
from itertools import combinations
import numpy as np
from scipy.ndimage import map_coordinates
from _curves import intersect_fields


def extract_paths(fields, half):
    """Same tetrahedral interpolation for all pairs; no stochastic tracing."""
    return [path for a, b in combinations(range(len(fields)), 2)
            for path in intersect_fields(fields[a], fields[b], np.asarray(half))]


def clip_path(path, arc, start, end):
    inner = (arc > start) & (arc < end)
    endpoints = np.array([[np.interp(s, arc, path[:, axis]) for axis in range(3)]
                          for s in (start, end)])
    return np.vstack((endpoints[0], path[inner], endpoints[1]))


def root_samples(path, spacing):
    arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    roots = np.arange(spacing*.5, arc[-1], spacing)
    if not len(roots):
        roots = np.array([arc[-1]*.5])
    points = np.column_stack([np.interp(roots, arc, path[:, a]) for a in range(3)])
    return arc, roots, points


def sample_support(density, points, half):
    coords = ((points/half + 1)*.5*(np.array(density.shape)-1)).T
    return map_coordinates(density, coords, order=1, mode='nearest')


def support_scale(paths, density, half, spacing):
    """Typical unfaded density ON the filaments, including outer candidate roots."""
    points = [root_samples(path, spacing)[2] for path in paths]
    return max(float(sample_support(density, np.concatenate(points), half).mean()), 1e-30) if points else 1.


def seeded_paths(paths, density, half, seed, spacing=1., length=2.,
                 seed_xz=.65, seed_y=.65, reference_scale=None, return_intervals=False):
    """Union finite two-way intervals on each original path, without moving it.

    Density is already edge-faded, but its normalization MUST be the pre-fade
    scale. Otherwise an edge edit could increase growth elsewhere. There is no
    random accept/reject threshold: only endpoint positions change with density.
    Root lattice, Beta lifetime draws and source IDs depend on geometry/seed only.
    """
    half = np.asarray(half, dtype=float)
    scale = support_scale(paths, density, half, spacing) if reference_scale is None else max(reference_scale, 1e-30)
    result, owners, records = [], [], []
    for owner, path in enumerate(paths):
        arc, roots, points = root_samples(path, spacing)
        total = arc[-1]
        if total <= 1e-9:
            continue
        normalized = np.abs(points / half)
        inside = ((np.maximum(normalized[:, 0], normalized[:, 2]) <= seed_xz)
                  & (normalized[:, 1] <= seed_y))
        support = np.clip(sample_support(density, points, half)/scale, 0, 1)
        rng = np.random.default_rng(np.random.SeedSequence([seed, 92617, owner]))
        reach = .5*length*(.5+rng.beta(2., 2., len(roots)))*support
        closed = np.linalg.norm(path[0]-path[-1]) < 1e-8
        intervals = []
        for root, radius in zip(roots[inside], reach[inside]):
            if radius <= 1e-9:
                continue
            a, b = root-radius, root+radius
            if closed and b-a >= total:
                intervals.append((0., total))
            else:
                intervals.append((max(0., a), min(total, b)))
                if closed and a < 0:
                    intervals.append((total+a, total))
                if closed and b > total:
                    intervals.append((0., b-total))
        merged = []
        for a, b in sorted(intervals):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        records.extend((owner, a, b) for a, b in merged)
        pieces = [clip_path(path, arc, a, b) for a, b in merged]
        # A loop's arbitrary indexing seam must not create two artificial tips.
        if closed and len(pieces) > 1 and merged[0][0] == 0 and merged[-1][1] == total:
            pieces = [np.vstack((pieces[-1], pieces[0][1:]))] + pieces[1:-1]
        result.extend(pieces)
        owners.extend([owner]*len(pieces))
    if return_intervals:
        return result, np.asarray(owners, dtype=int), records
    return result, np.asarray(owners, dtype=int)
