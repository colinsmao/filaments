"""Organic strands joining at shared intersections of noise zero-surfaces.

The A/B, A/C and B/C families contribute equally and meet where A=B=C=0.
A separate field modulates density along the web. Thin Y samples a slice of
the same three-dimensional field without weakening any constraint.
There are no junction lists, line segments, or precomputed curve paths.
"""
import numpy as np
from _postprocess import remap_density
from _noise import fractal_noise, grid, sample_density, star_appearance, fade_density
from noise_filaments import _clump_log_weight, PARAMETERS as FILAMENT_PARAMETERS
from _axis_controls import EXTENT_PARAMETERS, FADE_PARAMETERS, migrate_parameters, fade_density_axes

NAME = "Noise filaments with branches"
NATIVE_AXIS_FADE = True
PARAMETERS = [
    *(dict(entry) for entry in EXTENT_PARAMETERS),
    dict(key="frequency", label="Noise frequency", type="float", default=2.0, min=0.5, max=6.0),
    dict(key="width", label="Strand thickness", type="float", default=0.065, min=0.025, max=0.25),
    dict(key="octaves", label="Detail octaves", type="int", default=2, min=1, max=4),
    dict(key="roughness", label="Detail strength", type="float", default=0.22, min=0.0, max=0.6),
    dict(key="clumping", label="Clump contrast", type="float", default=3.0, min=0.0, max=12.0),
    # Keep the historical clump modulation unless a copied preset requests a floor.
    dict(key="strand_continuity", label="Strand continuity", type="float", default=0.0, min=0.0, max=1.0),
    *(dict(entry) for entry in FILAMENT_PARAMETERS if entry["key"].startswith("density_")),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
    *(dict(entry) for entry in FADE_PARAMETERS),
]


def _strand_log_density(a, b, c, width):
    denominator = 2 * width * width
    # Symmetric union of all three pairs. Log space avoids underflow in voids.
    ab = -(a * a + b * b) / denominator
    ac = -(a * a + c * c) / denominator
    bc = -(b * b + c * c) / denominator
    return np.logaddexp(ab, np.logaddexp(ac, bc))


def build_density(seed, frequency=2.0, width=0.065, octaves=2, roughness=0.22,
                  clumping=3.0, y_scale=1.0, strand_continuity=0.0,
                  density_low=1.0, density_mid=1.0, density_high=1.0):
    """Shared symmetric three-field density, remapped but not edge-faded."""
    resolution = 96
    points = grid(resolution, y_scale)
    a = fractal_noise(points, np.random.SeedSequence([seed, 101]), frequency, octaves, roughness)
    b = fractal_noise(points, np.random.SeedSequence([seed, 202]), frequency, octaves, roughness)
    c = fractal_noise(points, np.random.SeedSequence([seed, 404]), frequency, octaves, roughness)
    knots = fractal_noise(points, np.random.SeedSequence([seed, 303]), frequency * 0.6, 2)
    log_density = (_strand_log_density(a, b, c, width)
                   + _clump_log_weight(knots, clumping, strand_continuity))
    density = np.exp(log_density - log_density.max()).reshape((resolution,) * 3)
    return remap_density(density, density_low, density_mid, density_high)


def generate(count, seed, extent=6.0, frequency=2.0, width=0.065,
             octaves=2, roughness=0.22, clumping=3.0, star_size=0.04, size_variation=0.4,
             y_scale=1.0, fade=0, fade_width=0.8, fade_density_strength=1.0,
             strand_continuity=0.0, density_low=1.0, density_mid=1.0, density_high=1.0,
             _return_density=False, y_extent=None,
             fade_xz=None, fade_xz_width=None, fade_xz_density_strength=None,
             fade_y=None, fade_y_width=None, fade_y_density_strength=None):
    half_y = extent*y_scale if y_extent is None else y_extent
    y_scale = half_y / extent
    density = build_density(seed, frequency, width, octaves, roughness, clumping,
                            y_scale, strand_continuity, density_low, density_mid, density_high)
    guidance = density
    if fade_xz is None and fade_y is None and fade:
        density = fade_density(density, fade_width, fade_density_strength)
    else:
        density = fade_density_axes(density, half_y,
            fade if fade_xz is None else fade_xz, fade_width if fade_xz_width is None else fade_xz_width,
            fade_density_strength if fade_xz_density_strength is None else fade_xz_density_strength,
            fade if fade_y is None else fade_y, fade_width if fade_y_width is None else fade_y_width,
            fade_density_strength if fade_y_density_strength is None else fade_y_density_strength)
    positions, selected = sample_density(density, count, np.random.default_rng(seed))
    colors, sizes = star_appearance(count, seed, density, selected, star_size, size_variation)
    positions[:, 1] *= y_scale
    generated = (positions * extent, colors, sizes)
    if _return_density:
        return generated, guidance, np.array([extent, half_y, extent])
    return generated


def generate_density_source(count, seed, **params):
    """Share the pre-fade sampling field with the worker's alignment stage."""
    return generate(count, seed, **params, _return_density=True)
