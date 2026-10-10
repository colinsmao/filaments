"""Shared spatial envelopes for density fields and already-sampled stars."""
import numpy as np
from _appearance import PARAMETERS as APPEARANCE_PARAMETERS, apply_appearance


FADE_PARAMETER = dict(key="fade", label="Fade edges (0 off, 1 on)",
                      type="int", default=0, min=0, max=1, group="Edge fade", toggle=True)
FADE_WIDTH_PARAMETER = dict(key="fade_width", label="Fade width (fraction of half-extent)",
                            type="float", default=0.8, min=0.05, max=1.0,
                            group="Edge fade", enabled_if="fade")
FADE_DENSITY_PARAMETER = dict(key="fade_density_strength", label="Edge clump suppression",
                              type="float", default=1.0, min=0.0, max=4.0,
                              group="Edge fade", enabled_if="fade")


def edge_envelope(radius, width=0.8):
    """Smooth fade over the outer `width` fraction of the normalized half-extent."""
    t = np.clip((1 - np.asarray(radius)) / max(width, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def density_fade_weights(envelope, relative_density, strength=1.0):
    """Lower the permitted density toward the boundary, preserving the core.

    rho_out = rho*e / (1 + strength*(1-e)*rho/mean_rho).
    Dense peaks saturate at mean_rho*e/(strength*(1-e)) rather than remaining
    arbitrarily dense after a positional fade. At e=1 all densities are unchanged.
    """
    return envelope / (1 + strength * (1 - envelope) * relative_density)


def fade_density(density, width=0.8, strength=1.0):
    axis = np.abs(np.linspace(-1, 1, density.shape[0], dtype=np.float32))
    radius = np.maximum(np.maximum(axis[:, None, None], axis[None, :, None]), axis[None, None, :])
    envelope = edge_envelope(radius, width)
    mean = max(float(np.mean(density)), np.finfo(float).tiny)
    return density * density_fade_weights(envelope, density / mean, strength)


def relative_density_at_stars(normalized, resolution=48):
    """Smoothed occupancy density relative to its box-volume mean.

    Ignore collapsed axes, retain anisotropy through normalized coordinates,
    and compensate kernel truncation at the box faces. No wraparound: opposite
    edges do not influence each other's clump estimates.
    """
    from scipy.ndimage import gaussian_filter, map_coordinates
    active = np.ptp(normalized, axis=0) > 1e-8
    dimensions = np.count_nonzero(active)
    if dimensions == 0:
        return np.ones(len(normalized))
    points = normalized[:, active]
    mass, _ = np.histogramdd(points, bins=resolution, range=[(-1, 1)] * dimensions)
    mean = float(mass.mean())
    if mean <= 0:
        return np.zeros(len(normalized))
    density = gaussian_filter(mass, 1.25, mode="constant")
    support = gaussian_filter(np.ones_like(mass), 1.25, mode="constant")
    density /= support * mean
    coordinates = (points.T + 1) * (resolution / 2) - .5
    return map_coordinates(density, coordinates, order=1, mode="nearest", prefilter=False)


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
    zero to radius. Appearance edits precede the optional point-stage fade.
    """
    if not params.get("fade", 0):
        return apply_appearance(positions, colors, sizes, seed, params)
    if bounds is None:
        low, high = positions.min(axis=0), positions.max(axis=0)
        center, half_extents = (low + high) * 0.5, (high - low) * 0.5
    else:
        center, half_extents = (np.asarray(value, dtype=np.float64) for value in bounds)
        if (center.shape != (3,) or half_extents.shape != (3,)
                or not np.isfinite(center).all() or not np.isfinite(half_extents).all()
                or (half_extents < 0).any()):
            raise ValueError("postprocess_bounds must return finite center and nonnegative half-extents")
    positions, colors, sizes = apply_appearance(positions, colors, sizes, seed, params)
    normalized = np.divide(positions - center, half_extents,
                           out=np.zeros_like(positions), where=half_extents > 0)
    weights = edge_envelope(np.max(np.abs(normalized), axis=1), params.get("fade_width", .8))
    strength = params.get("fade_density_strength", 1.)
    if strength > 0:
        weights = density_fade_weights(weights, relative_density_at_stars(normalized), strength)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9401]))
    keep = rng.random(len(positions)) < weights
    if not keep.any():
        # The current viewer protocol requires a nonempty buffer. Report this
        # explicitly rather than inventing a survivor outside the envelope.
        raise ValueError("Edge fade removed every star; increase the count or disable Fade edges")
    return positions[keep], colors[keep], sizes[keep]
