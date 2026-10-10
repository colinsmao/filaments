"""Compiled FastNoiseLite fields and continuous sampling of a 3D density grid.

Helpers start with '_' so the viewer does not list them as patterns. The grid
approximates a continuous density; stars are not restricted to grid vertices.
"""
from pathlib import Path
import sys
import numpy as np
from _postprocess import fade_density

# A project-local wheel keeps the existing Conda environment unchanged. A normal
# installation from python/requirements.txt works too, including custom script dirs.
_local_packages = Path(__file__).resolve().parents[1] / ".tools" / "noise-python"
if _local_packages.is_dir():
    sys.path.insert(0, str(_local_packages))
from pyfastnoiselite.pyfastnoiselite import FastNoiseLite, NoiseType, FractalType


def fractal_noise(points, seed, frequency, octaves, roughness=0.5):
    """One native batch call computes all points and octaves; no per-point Python."""
    rng = np.random.default_rng(seed)
    noise = FastNoiseLite(seed=int(rng.integers(0, 2147483647)))
    noise.noise_type = NoiseType.NoiseType_Perlin
    noise.frequency = 1.0
    noise.fractal_type = FractalType.FractalType_FBm
    noise.fractal_octaves = int(octaves)
    noise.fractal_gain = float(roughness)
    noise.fractal_lacunarity = 2.0
    offset = rng.uniform(0, 128, points.shape[1]).astype(np.float32)
    coords = np.ascontiguousarray((points * frequency + offset).T, dtype=np.float32)
    return noise.gen_from_coords(coords)


def grid(resolution=96, y_scale=1.0):
    """Evaluate the same noise in a thinner region, preserving spatial wavelengths."""
    axis = np.linspace(-1, 1, resolution, dtype=np.float32)
    return np.stack(np.meshgrid(axis, axis * y_scale, axis, indexing="ij"), axis=-1).reshape(-1, 3)


def sample_density(density, count, rng):
    """Sample a bilinear/trilinear density inside a 2D/3D [-1, 1] domain.

    Each grid vertex contributes a separable triangular tent. Boundary tents
    have half the mass on each boundary axis. Selecting a tent by mass, then
    sampling its axes, avoids blocky cell jitter and rejection loops.
    """
    resolution = density.shape[0]
    mass = np.asarray(density, dtype=np.float64).copy()
    dimensions = density.ndim
    for axis in range(dimensions):
        for boundary in (0, -1):
            slices = [slice(None)] * dimensions
            slices[axis] = boundary
            mass[tuple(slices)] *= 0.5
    total = mass.sum()
    if not np.isfinite(total) or total <= 0 or (mass < 0).any():
        raise ValueError("Noise density must be finite, nonnegative and nonempty")
    selected = rng.choice(mass.size, size=count, p=mass.ravel() / total)
    indices = np.column_stack(np.unravel_index(selected, density.shape))
    jitter = rng.random((count, dimensions)) - rng.random((count, dimensions))
    for axis in range(dimensions):
        lower = indices[:, axis] == 0
        upper = indices[:, axis] == resolution - 1
        jitter[lower, axis] = 1 - np.sqrt(rng.random(np.count_nonzero(lower)))
        jitter[upper, axis] = np.sqrt(rng.random(np.count_nonzero(upper))) - 1
    positions = ((indices + jitter) * (2.0 / (resolution - 1)) - 1).astype(np.float32)
    return positions, selected


def star_appearance(count, seed, density, selected, star_size, size_variation):
    # A separate stream means size edits cannot rearrange the cloud.
    rng = np.random.default_rng(np.random.SeedSequence([seed, 9127]))
    value = np.asarray(density).ravel()[selected]
    t = np.clip(value / max(float(np.max(density)), 1e-12), 0, 1)[:, None]
    colors = (1 - t) * np.array([0.48, 0.70, 1.0]) + t * np.array([1.0, 0.85, 0.58])
    sizes = star_size * rng.uniform(1 - size_variation, 1 + size_variation, count)
    return colors, sizes
