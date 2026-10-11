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


def remap_density(density, low=1., middle=1., high=1.):
    """Continuous three-slope curve, before edge fading and star sampling.

    Breaks are at 1/3 and 2/3 of the input peak, not spatial regions or
    quantiles. Positive slopes preserve density ordering and exact zeros.
    All ones bypass exactly; the sampler normalizes the resulting weights.
    """
    if low == middle == high == 1.:
        return density
    peak = float(np.max(density))
    if peak <= 0:
        return density
    x = density / peak
    return peak * (low * np.minimum(x, 1/3)
                   + middle * np.clip(x - 1/3, 0, 1/3)
                   + high * np.maximum(x - 2/3, 0))


def edge_envelope(radius, width=0.8):
    """Smooth fade over the outer `width` fraction of the normalized half-extent."""
    t = np.clip((1 - np.asarray(radius)) / max(width, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def density_fade_weights(envelope, relative_density, strength=1.0):
    """Compress only density above the dense threshold near the boundary.

    r = rho / threshold, excess = max(r-1, 0), k = strength*(1-e).
    Output density / threshold = e*(min(r,1) + excess/(1+k*excess)).
    Below threshold the ordinary envelope is unchanged, at every strength.
    The shoulder is continuous with continuous first derivative and never
    reverses density ordering. At e=1 or strength=0, only positional fade applies.
    """
    e, r = np.broadcast_arrays(np.asarray(envelope), np.asarray(relative_density))
    excess = np.maximum(r - 1., 0.)
    k = strength * (1 - e)
    compressed = np.minimum(r, 1.) + excess / (1 + k * excess)
    ratio = np.divide(compressed, r, out=np.ones_like(compressed, dtype=float), where=r > 0)
    return np.where((r <= 1) | (k == 0), e, e * ratio)


def edge_dense_threshold(density):
    """Fixed knee at one quarter peak; empty volume cannot lower it."""
    return max(.25 * float(np.max(density)), np.finfo(float).tiny)


def fade_density(density, width=0.8, strength=1.0):
    axis = np.abs(np.linspace(-1, 1, density.shape[0], dtype=np.float32))
    radius = np.maximum(np.maximum(axis[:, None, None], axis[None, :, None]), axis[None, None, :])
    envelope = edge_envelope(radius, width)
    return density * density_fade_weights(envelope, density / edge_dense_threshold(density), strength)


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


def apply_to_stars(positions, colors, sizes, seed, params, bounds=None, allow_empty=False,
                   density_source=None, axis_fade=False):
    """Optional point-stage processors; masks always travel with star attributes.

    Bounds are (center, half_extents) in world coordinates. Without an explicit
    generator bound, use the cloud's bounding box. A collapsed axis contributes
    zero to radius. Appearance edits precede the optional point-stage fade.
    """
    if allow_empty and len(positions) == 0:
        return positions, colors, sizes
    fading = any(params.get('fade_'+axis, 0) for axis in ('xz', 'y')) if axis_fade else params.get('fade', 0)
    if not fading:
        return apply_appearance(positions, colors, sizes, seed, params, density_source)
    if bounds is None:
        low, high = positions.min(axis=0), positions.max(axis=0)
        center, half_extents = (low + high) * 0.5, (high - low) * 0.5
    else:
        center, half_extents = (np.asarray(value, dtype=np.float64) for value in bounds)
        if (center.shape != (3,) or half_extents.shape != (3,)
                or not np.isfinite(center).all() or not np.isfinite(half_extents).all()
                or (half_extents < 0).any()):
            raise ValueError("postprocess_bounds must return finite center and nonnegative half-extents")
    positions, colors, sizes = apply_appearance(positions, colors, sizes, seed, params, density_source)
    normalized = np.divide(positions - center, half_extents,
                           out=np.zeros_like(positions), where=half_extents > 0)
    if axis_fade:
        weights = np.ones(len(positions))
        relative = None
        for axis, indices in (('xz', [0, 2]), ('y', [1])):
            if not params.get('fade_'+axis, 0) or not np.any(half_extents[indices] > 0):
                continue
            radius = np.max(np.abs(normalized[:, indices]), axis=1)
            local = edge_envelope(radius, params.get('fade_'+axis+'_width', .8))
            strength = params.get('fade_'+axis+'_density_strength', 1.)
            if strength > 0:
                if relative is None:
                    density = relative_density_at_stars(normalized)
                    relative = density / edge_dense_threshold(density)
                local = density_fade_weights(local, relative, strength)
            weights = np.minimum(weights, local)
    else:
        weights = edge_envelope(np.max(np.abs(normalized), axis=1), params.get("fade_width", .8))
        strength = params.get("fade_density_strength", 1.)
        if strength > 0:
            density = relative_density_at_stars(normalized)
            weights = density_fade_weights(weights, density / edge_dense_threshold(density), strength)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9401]))
    keep = rng.random(len(positions)) < weights
    if not keep.any() and not allow_empty:
        # The current viewer protocol requires a nonempty buffer. Report this
        # explicitly rather than inventing a survivor outside the envelope.
        raise ValueError("Edge fade removed every star; increase the count or disable Fade edges")
    return positions[keep], colors[keep], sizes[keep]
