"""Two-field noise strands with a density floor along existing strands.

Strand continuity reduces gaps caused by clump modulation without introducing
extra strand families. Layer continuity adapts the field to thin Y regions.
"""
import numpy as np
from _postprocess import remap_density, FADE_PARAMETER, FADE_WIDTH_PARAMETER, FADE_DENSITY_PARAMETER
from _noise import fractal_noise, grid, sample_density, star_appearance, fade_density
from _axis_controls import EXTENT_PARAMETERS, FADE_PARAMETERS, migrate_parameters, fade_density_axes

NAME = "Noise filaments"
NATIVE_AXIS_FADE = True
PARAMETERS = [
    *(dict(entry) for entry in EXTENT_PARAMETERS),
    dict(key="layer_continuity", label="Layer continuity", type="float", default=1.0, min=0.0, max=1.0),
    dict(key="frequency", label="Noise frequency", type="float", default=2.0, min=0.5, max=6.0),
    dict(key="width", label="Strand thickness", type="float", default=0.065, min=0.025, max=0.25),
    dict(key="strand_continuity", label="Strand continuity", type="float", default=0.5, min=0.0, max=1.0),
    dict(key="octaves", label="Detail octaves", type="int", default=2, min=1, max=4),
    dict(key="roughness", label="Detail strength", type="float", default=0.22, min=0.0, max=0.6),
    dict(key="clumping", label="Clump contrast", type="float", default=3.0, min=0.0, max=12.0),
    dict(key="density_low", label="Density curve: low slope", type="float", default=1.0, min=0.05, max=3.0),
    dict(key="density_mid", label="Density curve: middle slope", type="float", default=1.0, min=0.05, max=3.0),
    dict(key="density_high", label="Density curve: high slope", type="float", default=1.0, min=0.05, max=3.0),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
    *(dict(entry) for entry in FADE_PARAMETERS),
]

# Comparison generators retain the older interface they actually implement.
LEGACY_PARAMETERS = [dict(entry) for entry in PARAMETERS
                     if entry['key'] != 'y_extent' and not entry['key'].startswith(('fade_', 'density_'))]
LEGACY_PARAMETERS[0]['label'] = 'Extent'
LEGACY_PARAMETERS.insert(1, dict(key='y_scale', label='Y thickness fraction', type='float',
                                 default=1., min=0., max=1.))
LEGACY_PARAMETERS.extend(dict(entry) for entry in (FADE_PARAMETER, FADE_WIDTH_PARAMETER, FADE_DENSITY_PARAMETER))


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


def build_strand_fields(points, seed, frequency=2.0, octaves=2, roughness=0.22):
    """Shared implicit geometry for density sampling and curve extraction."""
    a = fractal_noise(points, np.random.SeedSequence([seed, 101]), frequency, octaves, roughness)
    b = fractal_noise(points, np.random.SeedSequence([seed, 202]), frequency, octaves, roughness)
    return a, b


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
    a, b = build_strand_fields(points, seed, frequency, octaves, roughness)
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
             y_scale=1.0, fade=0, layer_continuity=1.0, strand_continuity=0.5, fade_width=0.8, fade_density_strength=1.0,
             density_low=1.0, density_mid=1.0, density_high=1.0, _return_density=False,
             y_extent=None, fade_xz=None, fade_xz_width=None, fade_xz_density_strength=None,
             fade_y=None, fade_y_width=None, fade_y_density_strength=None):
    half_y = extent*y_scale if y_extent is None else y_extent
    y_scale = half_y / extent
    density = build_density(seed, frequency, width, octaves, roughness, clumping,
                            y_scale, layer_continuity, strand_continuity)
    density = remap_density(density, density_low, density_mid, density_high)
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
