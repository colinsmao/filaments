"""Shared spatial envelopes for density fields and already-sampled stars."""
import numpy as np


FADE_PARAMETER = dict(key="fade", label="Fade edges (0 off, 1 on)",
                      type="int", default=0, min=0, max=1)


def edge_envelope(radius):
    """Full strength to 70% of an ellipsoid, smoothly zero at its surface."""
    t = np.clip((1 - np.asarray(radius)) / 0.3, 0, 1)
    return t * t * (3 - 2 * t)


def fade_density(density):
    axis2 = np.linspace(-1, 1, density.shape[0], dtype=np.float32) ** 2
    radius = np.sqrt(axis2[:, None, None] + axis2[None, :, None] + axis2[None, None, :])
    return density * edge_envelope(radius)


def suppress_voids(density, threshold):
    """Bounded soft cutoff; threshold is relative to the volume-mean density.

    Multiply by rho²/(rho² + tau²), not an unbounded density power. The
    multiplier tends to one in peaks, retaining their original density ratios.
    """
    if threshold <= 0:
        return density
    density = np.asarray(density, dtype=np.float64)
    mean = float(density.mean())
    if mean <= 0:
        return density
    relative = density / mean
    squared = relative * relative
    return density * squared / (squared + threshold * threshold)


def apply_to_stars(positions, colors, sizes, seed, params, bounds=None):
    """Optional point-stage processors; masks always travel with star attributes.

    Bounds are (center, half_extents) in world coordinates. Without an explicit
    generator bound, use the cloud's bounding box. A collapsed axis contributes
    zero to radius. No replacement particles or changed positions are introduced.
    """
    if not params.get("fade", 0):
        return positions, colors, sizes
    if bounds is None:
        low, high = positions.min(axis=0), positions.max(axis=0)
        center, half_extents = (low + high) * 0.5, (high - low) * 0.5
    else:
        center, half_extents = (np.asarray(value, dtype=np.float64) for value in bounds)
        if (center.shape != (3,) or half_extents.shape != (3,)
                or not np.isfinite(center).all() or not np.isfinite(half_extents).all()
                or (half_extents < 0).any()):
            raise ValueError("postprocess_bounds must return finite center and nonnegative half-extents")
    normalized = np.divide(positions - center, half_extents,
                           out=np.zeros_like(positions), where=half_extents > 0)
    weights = edge_envelope(np.linalg.norm(normalized, axis=1))
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9401]))
    keep = rng.random(len(positions)) < weights
    if not keep.any():
        # The current viewer protocol requires a nonempty buffer. Report this
        # explicitly rather than inventing a survivor outside the envelope.
        raise ValueError("Edge fade removed every star; increase the count or disable Fade edges")
    return positions[keep], colors[keep], sizes[keep]
