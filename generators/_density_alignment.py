"""Concentrate sampled stars onto nearby ridges of a fixed density field."""
import numpy as np
from _density_curves import DensityShape


def ridge_targets(points, field, reach):
    """Bounded transverse Newton steps; no along-ridge density ascent.

    The two most negative Hessian directions span a tube's normal plane.
    In a flat XZ field only one normal is used. Never infer directions from
    the sampled stars, and never step outside the source field's box.
    """
    result = np.asarray(points, dtype=float).copy()
    step_limit = min(reach, .5 * max(float(field.spacing.max()), field.radius))
    tolerance = float(field.spacing.max()) * 1e-3
    remaining = np.full(len(points), reach)
    active = np.ones(len(points), dtype=bool)
    for _ in range(min(32, int(np.ceil(reach / step_limit)) + 8)):
        ids = np.flatnonzero(active)
        if not len(ids):
            break
        current = result[ids]
        grad, values, vectors = field.eigensystem(current)
        # Round peaks lack a distinguished tangent; fade their movement out.
        confidence = np.clip((values[:, -1] - values[:, -2]) /
                             np.maximum(np.abs(values[:, -2]), 1e-9), 0, 1)
        normal = vectors[:, :, :-1]
        curvature = values[:, :-1]
        components = np.einsum('nij,ni->nj', normal, grad)
        coefficient = np.divide(-components, curvature, out=np.zeros_like(components),
                                where=curvature < -1e-9)
        correction = np.zeros_like(current)
        correction[:, field.axes] = np.einsum('nij,nj->ni', normal, coefficient)
        confidence *= values[:, -2] < -1e-9
        correction *= confidence[:, None]
        length = np.linalg.norm(correction, axis=1)
        correction *= (np.minimum(np.minimum(length, step_limit), remaining[ids]) /
                       np.maximum(length, 1e-30))[:, None]
        # Backtrack instead of crossing a density valley into a different ridge.
        before = field.log_value(current)
        accepted = np.zeros(len(ids), dtype=bool)
        proposal = current.copy()
        for _ in range(5):
            candidate = np.clip(current + correction, -field.half, field.half)
            uphill = field.log_value(candidate) >= before - 1e-10
            take = uphill & ~accepted
            proposal[take] = candidate[take]
            accepted |= uphill
            if accepted.all():
                break
            correction[~accepted] *= .5
        travel = np.linalg.norm(proposal - current, axis=1)
        result[ids] = proposal
        remaining[ids] -= travel
        active[ids] = accepted & (travel > tolerance) & (remaining[ids] > tolerance)
    return result


def align_to_density(positions, source, spacing, cutoff, reach, radius, strength):
    """Preserve count/order; only the caller's unmerged stars are supplied."""
    if not len(positions) or strength <= 0 or reach <= 0:
        return positions
    blend = np.clip((spacing - cutoff) / max(cutoff * .5, 1e-12), 0, 1)
    if np.ptp(spacing) < 1e-12:
        blend[:] = 1
    eligible = np.flatnonzero((spacing >= cutoff) & (blend > 0))
    if not len(eligible):
        return positions
    density, half_extents = source
    field = DensityShape(density, half_extents, radius)
    result = positions.copy()
    # Bound eigensystem scratch memory even for a million-star cloud.
    for start in range(0, len(eligible), 8192):
        ids = eligible[start:start+8192]
        targets = ridge_targets(positions[ids], field, reach)
        result[ids] += (strength * blend[ids])[:, None] * (targets - positions[ids])
    return result
