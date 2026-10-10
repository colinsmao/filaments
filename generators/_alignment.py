"""Local, bounded attraction of an existing point cloud toward guide curves."""
import numpy as np
from scipy.spatial import cKDTree


def attract_to_curves(positions, curves, strength, radius):
    """Return moved points, attraction weights and curve IDs, preserving order.

    Project onto nearby segments, then softly pull toward that projection. The
    influence has zero value and slope at its radius. No stars are resampled or
    redistributed along a path. Query batches bound temporary memory usage.
    """
    moved = positions.copy()
    weights = np.zeros(len(positions), dtype=np.float32)
    selected_curves = np.zeros(len(positions), dtype=np.int32)
    if strength <= 0 or radius <= 0 or not curves:
        return moved, weights, selected_curves
    start = np.concatenate([curve[:-1] for curve in curves])
    end = np.concatenate([curve[1:] for curve in curves])
    ids = np.concatenate([np.full(len(curve)-1, i, dtype=np.int32) for i, curve in enumerate(curves)])
    open_start = np.zeros(len(start), dtype=bool)
    open_end = np.zeros(len(start), dtype=bool)
    cursor = 0
    for curve in curves:
        if np.linalg.norm(curve[0] - curve[-1]) > 1e-8:
            open_start[cursor] = True
            open_end[cursor + len(curve) - 2] = True
        cursor += len(curve) - 1
    delta = end - start
    length2 = np.einsum("ij,ij->i", delta, delta)
    valid = length2 > 1e-16
    start, delta, length2, ids = start[valid], delta[valid], length2[valid], ids[valid]
    open_start, open_end = open_start[valid], open_end[valid]
    if not len(start):
        return moved, weights, selected_curves
    tree = cKDTree(start + delta * 0.5)
    neighbors = list(range(1, min(8, len(start)) + 1))
    for lo in range(0, len(positions), 32768):
        hi = min(lo + 32768, len(positions))
        points = positions[lo:hi].astype(np.float64)
        _, indices = tree.query(points, k=neighbors, workers=2)
        displacement = points[:, None, :] - start[indices]
        raw_t = np.einsum("nki,nki->nk", displacement, delta[indices]) / length2[indices]
        t = np.clip(raw_t, 0, 1)
        targets = start[indices] + t[..., None] * delta[indices]
        distance2 = np.sum((targets - points[:, None, :]) ** 2, axis=-1)
        best = np.argmin(distance2, axis=1)
        rows = np.arange(len(points))
        distance = np.sqrt(distance2[rows, best])
        r = np.clip(distance / radius, 0, 1)
        weight = strength * (1 - r) ** 2 * (1 + 2 * r)
        chosen = indices[rows, best]
        # Open endpoints must not act as point attractors and collect knots.
        beyond_end = ((open_start[chosen] & (raw_t[rows, best] < 0))
                      | (open_end[chosen] & (raw_t[rows, best] > 1)))
        weight[beyond_end] = 0
        target = targets[rows, best]
        moved[lo:hi] = points + weight[:, None] * (target - points)
        weights[lo:hi] = weight
        selected_curves[lo:hi] = ids[indices[rows, best]]
    return moved, weights, selected_curves
