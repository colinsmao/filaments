"""A full 3D cellular web with separate XZ and Y spatial scales.

Density peaks where the three nearest jittered sites are nearly equidistant:
the edges of 3D Voronoi cells, rather than their sheet-like faces. Independent
3D noise fields bend the coordinates. Axis scales transform both the extent
and cell wavelengths; equal scales restore the isotropic construction.
"""
import numpy as np
from _postprocess import FADE_WIDTH_PARAMETER, FADE_DENSITY_PARAMETER
from scipy.spatial import cKDTree
from _noise import fractal_noise, grid, fade_density, sample_density, star_appearance

NAME = "Layer filaments"
PARAMETERS = [
    dict(key="extent", label="XZ scale (units)", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="y_scale", label="Y scale (units)", type="float", default=0.9, min=0.05, max=30.0),
    dict(key="cells", label="Cells across each axis", type="int", default=6, min=2, max=14),
    dict(key="width", label="Strand width / cell", type="float", default=0.065, min=0.025, max=0.3),
    dict(key="warp", label="3D warp / cell", type="float", default=0.65, min=0.0, max=1.5),
    dict(key="clumping", label="Clump contrast", type="float", default=1.5, min=0.0, max=8.0),
    dict(key="fade", label="Fade edges (0 off, 1 on)", type="int", default=1, min=0, max=1),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
    dict(FADE_WIDTH_PARAMETER),
    dict(FADE_DENSITY_PARAMETER),
]


def _cellular_density(seed, cells, width, warp, clumping, fade, resolution=96, fade_width=0.8, fade_density_strength=1.0):
    # Coordinates measured in cell spacings make all three axes interchangeable.
    points = grid(resolution) * (cells * 0.5)
    displacement = np.column_stack([
        fractal_noise(points, np.random.SeedSequence([seed, salt]), 1, 3, 0.4)
        for salt in (401, 402, 405)
    ])
    warped = points + displacement * warp
    # Three extra rings cover coordinate warp and nearest neighbors at boundaries.
    axis = np.arange(-3, cells + 3, dtype=np.float32) + 0.5 - cells * 0.5
    sites = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1).reshape(-1, 3)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 403]))
    sites += rng.uniform(-0.4, 0.4, sites.shape).astype(np.float32)
    # The compiled spatial index avoids comparing every site to every grid point.
    # Limit threads so the live viewer retains CPU time during generation.
    distances, _ = cKDTree(sites).query(warped, k=3, workers=2)
    edge_gap = distances[:, 2] - distances[:, 0]
    knots = fractal_noise(points, np.random.SeedSequence([seed, 404]), 0.7, 2)
    log_density = -0.5 * (edge_gap / width) ** 2 + clumping * knots
    density = np.exp(log_density - log_density.max()).astype(np.float32).reshape((resolution,) * 3)
    return fade_density(density, fade_width, fade_density_strength) if fade else density


def generate(count, seed, extent=6.0, y_scale=0.9, cells=6, width=0.065,
             warp=0.65, clumping=1.5, fade=1, star_size=0.04, size_variation=0.4, fade_width=0.8, fade_density_strength=1.0):
    density = _cellular_density(seed, cells, width, warp, clumping, fade, fade_width=fade_width, fade_density_strength=fade_density_strength)
    positions, selected = sample_density(density, count, np.random.default_rng(seed))
    positions *= np.array([extent, y_scale, extent], dtype=np.float32)
    colors, sizes = star_appearance(count, seed, density, selected, star_size, size_variation)
    return positions, colors, sizes
