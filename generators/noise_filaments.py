"""Organic strands from the intersection of two independent noise zero-surfaces.

Density = exp(-(a*a + b*b)/(2*width*width)), modulated by a third noise field.
There are no junction lists, line segments, or precomputed curve paths.
"""
import numpy as np
from _noise import fractal_noise, grid, sample_density, star_appearance

NAME = "Noise filaments"
PARAMETERS = [
    dict(key="extent", label="Extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="frequency", label="Noise frequency", type="float", default=2.0, min=0.5, max=6.0),
    dict(key="width", label="Strand thickness", type="float", default=0.065, min=0.025, max=0.25),
    dict(key="octaves", label="Detail octaves", type="int", default=2, min=1, max=4),
    dict(key="roughness", label="Detail strength", type="float", default=0.22, min=0.0, max=0.6),
    dict(key="clumping", label="Clump contrast", type="float", default=3.0, min=0.0, max=12.0),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def generate(count, seed, extent=6.0, frequency=2.0, width=0.065,
             octaves=2, roughness=0.22, clumping=3.0, star_size=0.04, size_variation=0.4):
    resolution = 96
    points = grid(resolution)
    a = fractal_noise(points, np.random.SeedSequence([seed, 101]), frequency, octaves, roughness)
    b = fractal_noise(points, np.random.SeedSequence([seed, 202]), frequency, octaves, roughness)
    knots = fractal_noise(points, np.random.SeedSequence([seed, 303]), frequency * 0.6, 2)
    log_density = -(a * a + b * b) / (2 * width * width) + clumping * knots
    density = np.exp(log_density - log_density.max()).reshape((resolution,) * 3)
    positions, selected = sample_density(density, count, np.random.default_rng(seed))
    colors, sizes = star_appearance(count, seed, density, selected, star_size, size_variation)
    return positions * extent, colors, sizes
