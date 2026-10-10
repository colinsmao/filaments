"""Organic strands joining at shared intersections of noise zero-surfaces.

The original A/B strands can be joined by A/C and B/C strands. All three
families meet where A=B=C=0. A separate field modulates density along the web.
Layer continuity reduces beta in thin Y bands, transitioning toward 2D strands.
There are no junction lists, line segments, or precomputed curve paths.
"""
import numpy as np
from _noise import fractal_noise, grid, sample_density, star_appearance, fade_density

NAME = "Noise filaments with branches"
PARAMETERS = [
    dict(key="extent", label="Extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="y_scale", label="Y thickness fraction", type="float", default=1.0, min=0.0, max=1.0),
    dict(key="layer_continuity", label="Layer continuity", type="float", default=1.0, min=0.0, max=1.0),
    dict(key="fade", label="Fade edges (0 off, 1 on)", type="int", default=0, min=0, max=1),
    dict(key="frequency", label="Noise frequency", type="float", default=2.0, min=0.5, max=6.0),
    dict(key="width", label="Strand thickness", type="float", default=0.065, min=0.025, max=0.25),
    dict(key="connectivity", label="Connectivity", type="float", default=1.0, min=0.0, max=1.0),
    dict(key="octaves", label="Detail octaves", type="int", default=2, min=1, max=4),
    dict(key="roughness", label="Detail strength", type="float", default=0.22, min=0.0, max=0.6),
    dict(key="clumping", label="Clump contrast", type="float", default=3.0, min=0.0, max=12.0),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def _strand_log_density(a, b, c, width, beta, connectivity):
    denominator = 2 * width * width
    original = -(a * a + beta * b * b) / denominator
    if connectivity <= 0:
        return original
    # Weighted union: new strands share A or B with the original family and
    # join it at triple-zero junctions. Log space avoids underflow in voids.
    ac = -(a * a + beta * c * c) / denominator
    bc = -(b * b + beta * c * c) / denominator
    return np.logaddexp(original, np.log(connectivity) + np.logaddexp(ac, bc))


def generate(count, seed, extent=6.0, frequency=2.0, width=0.065,
             octaves=2, roughness=0.22, clumping=3.0, star_size=0.04, size_variation=0.4,
             y_scale=1.0, fade=0, layer_continuity=1.0, connectivity=1.0):
    resolution = 96
    points = grid(resolution, y_scale)
    a = fractal_noise(points, np.random.SeedSequence([seed, 101]), frequency, octaves, roughness)
    b = fractal_noise(points, np.random.SeedSequence([seed, 202]), frequency, octaves, roughness)
    c = (fractal_noise(points, np.random.SeedSequence([seed, 404]), frequency, octaves, roughness)
         if connectivity > 0 else None)
    knots = fractal_noise(points, np.random.SeedSequence([seed, 303]), frequency * 0.6, 2)
    # A literal thin slice cuts 3D strands into isolated spots. Relaxing B's
    # constraint approaches A=0 contours across the layer without stretching
    # either noise field. At full thickness the original density is unchanged.
    beta = (1 - layer_continuity) + layer_continuity * y_scale * y_scale
    log_density = _strand_log_density(a, b, c, width, beta, connectivity) + clumping * knots
    density = np.exp(log_density - log_density.max()).reshape((resolution,) * 3)
    if fade:
        density = fade_density(density)
    positions, selected = sample_density(density, count, np.random.default_rng(seed))
    colors, sizes = star_appearance(count, seed, density, selected, star_size, size_variation)
    positions[:, 1] *= y_scale
    return positions * extent, colors, sizes
