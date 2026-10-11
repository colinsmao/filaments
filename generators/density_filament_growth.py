"""Symmetric branch density -> local stochastic strands -> shared stars."""
from colorsys import hsv_to_rgb
import numpy as np
import noise_filaments_branches as base
from _axis_controls import fade_density_axes, migrate_parameters as migrate_axes
from _density_curves import trace_density

NAME = 'Density-guided strands (previous growth)'
PRIMITIVE = 'lines'
NATIVE_AXIS_FADE = True
_DENSITY_KEYS = {'frequency', 'width', 'strand_continuity', 'octaves', 'roughness',
                 'clumping', 'density_low', 'density_mid', 'density_high',
                 'broad_strength', 'broad_scale'}
PARAMETERS = [dict(entry) for entry in base.PARAMETERS
              if entry['key'] not in ('star_size', 'size_variation')] + [
    dict(key='strand_count', label='Local strands', type='int', default=512, min=16, max=2048),
    dict(key='strand_length', label='Mean total strand length (units)', type='float', default=2., min=.2, max=30.),
    dict(key='direction_scale', label='Filament response length (units)', type='float', default=.3, min=.1, max=1.5),
    dict(key='density_pull', label='Pull toward assigned filament', type='float', default=.35, min=0., max=2.),
    dict(key='curve_wander', label='Curve Perlin steering', type='float', default=.15, min=0., max=1.),
    dict(key='join_reach', label='Strand joining reach (units)', type='float', default=.6, min=0., max=1.5),
    dict(key='join_strength', label='Strand joining strength (0 off)', type='float', default=1., min=0., max=4.),
    dict(key='join_radius', label='Strand contact radius (units)', type='float', default=.08, min=0., max=.3),
    dict(key='coverage_mode', label='Density coverage (0 off, 1 cap, 2 fill)', type='int', default=1, min=0, max=2),
    dict(key='coverage_radius', label='Coverage radius (units)', type='float', default=.5, min=.15, max=1.5),
    dict(key='capacity_scale', label='Curve capacity multiplier', type='float', default=1., min=.1, max=3.),
]
# Start this comparison at the user's 2026-10-10 reference density. These are
# fixed experiment defaults, not reads/writes of the live viewer settings.
_REFERENCE_DEFAULTS = dict(extent=9.458, y_extent=9.458*.234, frequency=2.505, width=.025,
                           roughness=.107, clumping=6.875, strand_continuity=1.)
for _entry in PARAMETERS:
    if _entry['key'] in _REFERENCE_DEFAULTS:
        _entry['default'] = _REFERENCE_DEFAULTS[_entry['key']]


def migrate_parameters(params):
    # This experiment's historical defaults differ from the direct sampler.
    supplied = dict(extent=9.458, y_scale=.234)
    supplied.update(params)
    return migrate_axes(supplied)


def generate_population_source(count, seed, extent=9.458, y_scale=.234, strand_count=512,
                               strand_length=2., direction_scale=.3, density_pull=.35,
                               curve_wander=.15, join_reach=.6, join_strength=1.,
                               join_radius=.08, coverage_mode=1, coverage_radius=.5,
                               capacity_scale=1., y_extent=None, **params):
    half_y = extent*y_scale if y_extent is None else y_extent
    density_params = {entry['key']: entry['default'] for entry in PARAMETERS
                      if entry['key'] in _DENSITY_KEYS}
    # Ignore retired controls if a caller supplies an old preset directly.
    density_params.update({k: v for k, v in params.items() if k in _DENSITY_KEYS})
    density, fields = base.build_density(seed, y_scale=half_y/extent, **density_params, _return_fields=True)
    fade = migrate_parameters(params)
    density = fade_density_axes(density, half_y, *[
        fade[key] for key in ('fade_xz', 'fade_xz_width', 'fade_xz_density_strength',
                              'fade_y', 'fade_y_width', 'fade_y_density_strength')])
    paths = trace_density(density, seed, [extent, half_y, extent],
                          strand_count, strand_length, direction_scale, density_pull, curve_wander,
                          join_reach, join_strength, join_radius,
                          coverage_mode, coverage_radius, capacity_scale,
                          pair_fields=fields, pair_width=density_params['width'])
    # Spread adjacent path hues apart without consuming the growth RNG stream.
    phase = np.random.default_rng(np.random.SeedSequence([seed, 82421])).random()
    hues = (phase + np.arange(len(paths)) * .618033988749895) % 1.
    colors = np.array([hsv_to_rgb(hue, .65, 1.) for hue in hues])
    vertices = [np.stack((p[:-1], p[1:]), axis=1).reshape(-1, 3) for p in paths]
    positions = np.concatenate(vertices).astype(np.float32)
    rgb = np.concatenate([np.broadcast_to(c, v.shape) for c, v in zip(colors, vertices)]).astype(np.float32)
    return (positions, rgb, .04), paths, colors


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
