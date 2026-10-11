"""Remove whole redundant curves, retaining geometry and unique extensions."""
import numpy as np
from scipy.spatial import cKDTree


def thin_parallel_curves(paths, radius=.5, parallel_limit=1, redundant_fraction=.85):
    """Return retained original indices in original order, deterministically.

    Longest paths get first choice. A path is redundant only when the requested
    number of distinct retained curves covers enough of its arc length within
    radius and 25 degrees (orientation independent). Crossing segments are not
    counted. This is sampled coverage, not a connectivity guarantee or hard
    local cap: paths with enough unique length survive in their entirety.
    """
    if radius <= 0 or len(paths) < 2:
        return np.arange(len(paths), dtype=int)
    starts, deltas, owners, lengths, distances = [], [], [], [], []
    for i, path in enumerate(paths):
        delta = np.diff(path, axis=0)
        segment_lengths = np.linalg.norm(delta, axis=1)
        valid = segment_lengths > 1e-10
        starts.append(np.asarray(path[:-1])[valid])
        deltas.append(delta[valid])
        owners.append(np.full(np.count_nonzero(valid), i, dtype=int))
        distance = np.r_[0., np.cumsum(segment_lengths)]
        distances.append(distance)
        lengths.append(distance[-1])
    start, delta, owner = map(np.concatenate, (starts, deltas, owners))
    if not len(start):
        return np.arange(len(paths), dtype=int)
    length2 = np.sum(delta*delta, axis=1)
    segment_length = np.sqrt(length2)
    tangent = delta/segment_length[:, None]
    tree = cKDTree(start + delta*.5)
    # A segment within r has its midpoint within r + half its length.
    # This broad phase cannot lose long segments merely due to vertex spacing.
    query_radius = radius + .5*segment_length.max()
    retained = np.zeros(len(paths), dtype=bool)
    parallel_cos = np.cos(np.deg2rad(25.))
    # Ignore accumulation roundoff so equal-length reversed/tessellated paths
    # retain the original-order tie break.
    for identity in np.argsort(-np.round(lengths, 10), kind='stable'):
        path, distance = paths[identity], distances[identity]
        if lengths[identity] <= 1e-10:
            retained[identity] = True
            continue
        # Equal arc-length quadrature makes decisions insensitive to tessellation.
        count = max(2, int(np.ceil(lengths[identity]/min(radius*.5, .12))))
        s = (np.arange(count)+.5)*lengths[identity]/count
        segment = np.minimum(np.searchsorted(distance, s, side='right')-1, len(path)-2)
        direction = path[segment+1]-path[segment]
        direction /= np.maximum(np.linalg.norm(direction, axis=1, keepdims=True), 1e-12)
        points = path[segment] + direction*(s-distance[segment])[:, None]
        covered = 0
        if np.count_nonzero(retained) >= parallel_limit:
            for lo in range(0, count, 128):
                p, t = points[lo:lo+128], direction[lo:lo+128]
                nearby = tree.query_ball_point(p, query_radius)
                # Exclude unvisited/rejected curves before allocating pair arrays.
                nearby = [np.asarray(ids, dtype=int)[retained[owner[ids]]] for ids in nearby]
                sizes = np.array([len(ids) for ids in nearby])
                if not sizes.sum():
                    continue
                rows = np.repeat(np.arange(len(p)), sizes)
                ids = np.concatenate(nearby)
                aligned = np.abs(np.sum(t[rows]*tangent[ids], axis=1)) >= parallel_cos
                rows, ids = rows[aligned], ids[aligned]
                offset = p[rows]-start[ids]
                fraction = np.clip(np.sum(offset*delta[ids], axis=1)/length2[ids], 0., 1.)
                distance2 = np.sum((offset-fraction[:, None]*delta[ids])**2, axis=1)
                close = distance2 <= radius*radius
                # One winding/densely tessellated curve must only count once
                # toward the parallel bundle allowance at each probe.
                pairs = np.unique(rows[close]*len(paths) + owner[ids[close]])
                multiplicity = np.bincount(pairs//len(paths), minlength=len(p))
                covered += np.count_nonzero(multiplicity >= parallel_limit)
        if covered/count + 1e-12 < redundant_fraction:
            retained[identity] = True
    return np.flatnonzero(retained)
