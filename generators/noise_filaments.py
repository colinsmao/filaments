"""Two-field noise strands with a density floor along existing strands.

Strand continuity reduces gaps caused by clump modulation without introducing
extra strand families. Layer continuity adapts the field to thin Y regions.
"""
import numpy as np
from _noise import fractal_noise, grid, sample_density, star_appearance, fade_density

NAME = "Noise filaments"
PARAMETERS = [
    dict(key="extent", label="Extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="y_scale", label="Y thickness fraction", type="float", default=1.0, min=0.0, max=1.0),
    dict(key="layer_continuity", label="Layer continuity", type="float", default=1.0, min=0.0, max=1.0),
    dict(key="fade", label="Fade edges (0 off, 1 on)", type="int", default=0, min=0, max=1),
    dict(key="frequency", label="Noise frequency", type="float", default=2.0, min=0.5, max=6.0),
    dict(key="width", label="Strand thickness", type="float", default=0.065, min=0.025, max=0.25),
    dict(key="strand_continuity", label="Strand continuity", type="float", default=0.5, min=0.0, max=1.0),
    dict(key="octaves", label="Detail octaves", type="int", default=2, min=1, max=4),
    dict(key="roughness", label="Detail strength", type="float", default=0.22, min=0.0, max=0.6),
    dict(key="clumping", label="Clump contrast", type="float", default=3.0, min=0.0, max=12.0),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def _clump_log_weight(knots, clumping, continuity):
    log_weight = clumping * knots
    if continuity <= 0:
        return log_weight
    if continuity >= 1:
        return np.zeros_like(log_weight)
    # Blend clump modulation with a constant floor, measured relative to its
    # peak. This changes density along existing strands, not their geometry.
    return np.logaddexp(np.log1p(-continuity) + log_weight,
                        np.log(continuity) + log_weight.max())


def build_density(seed, frequency=2.0, width=0.065, octaves=2, roughness=0.22,
                  clumping=3.0, y_scale=1.0, layer_continuity=1.0,
                  strand_continuity=0.5, resolution=96):
    """Construct the density independently of edge fade and star sampling.

    Grid axes are XYZ, spanning [-1, 1], [-y_scale, y_scale], [-1, 1].
    Density postprocessing belongs after this stage and before edge fade, so
    cleanup does not undo the final boundary envelope. It must preserve finite,
    nonnegative values and leave nonzero total density for the sampler.
    """
    points = grid(resolution, y_scale)
    a = fractal_noise(points, np.random.SeedSequence([seed, 101]), frequency, octaves, roughness)
    b = fractal_noise(points, np.random.SeedSequence([seed, 202]), frequency, octaves, roughness)
    knots = fractal_noise(points, np.random.SeedSequence([seed, 303]), frequency * 0.6, 2)
    # A literal thin slice cuts 3D strands into isolated spots. Relaxing B's
    # constraint approaches A=0 contours across the layer without stretching
    # either noise field. At full thickness the original density is unchanged.
    beta = (1 - layer_continuity) + layer_continuity * y_scale * y_scale
    log_density = -(a * a + beta * b * b) / (2 * width * width)
    log_density += _clump_log_weight(knots, clumping, strand_continuity)
    return np.exp(log_density - log_density.max()).reshape((resolution,) * 3)


def generate(count, seed, extent=6.0, frequency=2.0, width=0.065,
             octaves=2, roughness=0.22, clumping=3.0, star_size=0.04, size_variation=0.4,
             y_scale=1.0, fade=0, layer_continuity=1.0, strand_continuity=0.5):
    density = build_density(seed, frequency, width, octaves, roughness, clumping,
                            y_scale, layer_continuity, strand_continuity)
    if fade:
        density = fade_density(density)
    positions, selected = sample_density(density, count, np.random.default_rng(seed))
    colors, sizes = star_appearance(count, seed, density, selected, star_size, size_variation)
    positions[:, 1] *= y_scale
    return positions * extent, colors, sizes
