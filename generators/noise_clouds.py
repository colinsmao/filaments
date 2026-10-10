"""Clumpy star clouds sampled from a fractal gradient-noise density field.

Frequency changes the size/number of clouds, contrast deepens the voids, and
octaves/roughness add small-scale detail. FastNoiseLite computes the noise in C++.
"""
import numpy as np
from _noise import fractal_noise, grid, sample_density, star_appearance

NAME = "Noise clouds"
PARAMETERS = [
    dict(key="extent", label="Extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="frequency", label="Noise frequency", type="float", default=2.0, min=0.5, max=6.0),
    dict(key="contrast", label="Density contrast", type="float", default=12.0, min=0.0, max=24.0),
    dict(key="octaves", label="Detail octaves", type="int", default=3, min=1, max=5),
    dict(key="roughness", label="Detail strength", type="float", default=0.4, min=0.0, max=0.7),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def generate(count, seed, extent=6.0, frequency=2.0, contrast=12.0,
             octaves=3, roughness=0.4, star_size=0.04, size_variation=0.4):
    resolution = 96
    field = fractal_noise(grid(resolution), seed, frequency, octaves, roughness)
    # Subtracting the maximum keeps exponentials bounded without changing the PDF.
    density = np.exp((field - field.max()) * contrast).reshape((resolution,) * 3)
    positions, selected = sample_density(density, count, np.random.default_rng(seed))
    colors, sizes = star_appearance(count, seed, density, selected, star_size, size_variation)
    return positions * extent, colors, sizes
