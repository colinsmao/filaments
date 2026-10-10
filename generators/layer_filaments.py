"""Noise-warped cellular strands in XZ, with independent height and Y spread.

Jittered lattice sites keep the network distributed across the plane. Density
peaks where the two nearest sites are equidistant (Voronoi cell boundaries).
Smooth coordinate warping bends those boundaries without drawing explicit links.
The planar density is sampled first; a smooth height field and Gaussian vertical
spread then lift it into 3D. Y controls never alter the XZ footprint.
"""
import numpy as np
from _noise import fractal_noise, sample_density, star_appearance

NAME = "Layer filaments"
PARAMETERS = [
    dict(key="extent", label="XZ extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="cells", label="Cells across XZ", type="int", default=6, min=2, max=14),
    dict(key="width", label="Strand width / cell", type="float", default=0.065, min=0.025, max=0.3),
    dict(key="warp", label="XZ warp / cell", type="float", default=0.65, min=0.0, max=1.5),
    dict(key="clumping", label="Clump contrast", type="float", default=1.5, min=0.0, max=8.0),
    dict(key="y_spread", label="Y spread (std dev, units)", type="float", default=0.12, min=0.0, max=3.0),
    dict(key="height", label="Layer waviness (units)", type="float", default=0.6, min=0.0, max=6.0),
    dict(key="height_frequency", label="Height frequency", type="float", default=1.5, min=0.25, max=6.0),
    dict(key="fade", label="Fade edges (0 off, 1 on)", type="int", default=1, min=0, max=1),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def _planar_density(seed, cells, width, warp, clumping, fade):
    resolution = 256
    axis = np.linspace(-1, 1, resolution, dtype=np.float32)
    points = np.stack(np.meshgrid(axis, axis, indexing="ij"), axis=-1).reshape(-1, 2)
    spacing = 2.0 / cells
    frequency = cells * 0.5
    displacement = np.column_stack([
        fractal_noise(points, np.random.SeedSequence([seed, salt]), frequency, 3, 0.4)
        for salt in (401, 402)
    ])
    warped = points + displacement * (warp * spacing)
    # Three extra rings cover the largest allowed warp and the domain boundaries.
    site_axis = (np.arange(-3, cells + 3) + 0.5) * spacing - 1
    sites = np.stack(np.meshgrid(site_axis, site_axis, indexing="ij"), axis=-1).reshape(-1, 2)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 403]))
    sites += rng.uniform(-0.4, 0.4, sites.shape) * spacing
    sites = sites.astype(np.float32)
    first = np.full(len(points), np.inf, dtype=np.float32)
    second = first.copy()
    first_id = np.zeros(len(points), dtype=np.int32)
    second_id = first_id.copy()
    # Loop over a small site set; each operation handles the whole 2D grid.
    # Keep only two distances per sample rather than a sites-by-grid tensor.
    for index, site in enumerate(sites):
        delta = warped - site
        distance = np.einsum("ij,ij->i", delta, delta)
        closer = distance < first
        runner_up = (~closer) & (distance < second)
        second = np.where(closer, first, np.where(runner_up, distance, second))
        second_id = np.where(closer, first_id, np.where(runner_up, index, second_id))
        first = np.minimum(first, distance)
        first_id = np.where(closer, index, first_id)
    separation = np.linalg.norm(sites[first_id] - sites[second_id], axis=1)
    # Distance to the bisector in warped coordinates; zero at cell boundaries.
    edge_distance = (second - first) / (2 * separation)
    knots = fractal_noise(points, np.random.SeedSequence([seed, 404]), frequency * 0.7, 2)
    log_density = -0.5 * (edge_distance / (width * spacing)) ** 2 + clumping * knots
    density = np.exp(log_density - log_density.max())
    if fade:
        radius = np.linalg.norm(points, axis=1)
        t = np.clip((1 - radius) / 0.3, 0, 1)
        density *= t * t * (3 - 2 * t)
    return density.reshape(resolution, resolution)


def generate(count, seed, extent=6.0, cells=6, width=0.065, warp=0.65,
             clumping=1.5, y_spread=0.12, height=0.6, height_frequency=1.5,
             fade=1, star_size=0.04, size_variation=0.4):
    density = _planar_density(seed, cells, width, warp, clumping, fade)
    xz, selected = sample_density(density, count, np.random.default_rng(seed))
    y = height * fractal_noise(xz, np.random.SeedSequence([seed, 405]), height_frequency, 2)
    vertical_rng = np.random.default_rng(np.random.SeedSequence([seed, 406]))
    y += y_spread * vertical_rng.standard_normal(count)
    positions = np.column_stack((xz[:, 0] * extent, y, xz[:, 1] * extent))
    colors, sizes = star_appearance(count, seed, density, selected, star_size, size_variation)
    return positions, colors, sizes
