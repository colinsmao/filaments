"""Stable pair-zero curves -> centrally seeded finite intervals -> shared stars."""
from colorsys import hsv_to_rgb
import numpy as np
import noise_filaments_branches as base
from _axis_controls import migrate_parameters as migrate_axes
from _stable_density_curves import extract_paths, seeded_paths, support_scale

NAME = 'Density filament curves (stable seeds)'
PRIMITIVE = 'lines'
NATIVE_AXIS_FADE = True
POPULATION_AXIS_FADE = True
_DENSITY_KEYS = {'frequency', 'width', 'strand_continuity', 'octaves', 'roughness',
                 'clumping', 'density_low', 'density_mid', 'density_high',
                 'broad_strength', 'broad_scale'}
PARAMETERS = [dict(entry) for entry in base.PARAMETERS
              if entry['key'] not in ('star_size', 'size_variation')] + [
    dict(key='curve_resolution', label='Zero-surface grid resolution', type='int', default=48, min=24, max=96),
    dict(key='seed_spacing', label='Curve seed spacing (units)', type='float', default=1., min=.2, max=5.),
    dict(key='strand_length', label='Mean travel at full density (units)', type='float', default=2., min=.2, max=30.),
    dict(key='seed_xz', label='XZ seed region (fraction)', type='float', default=.65, min=.1, max=1.),
    dict(key='seed_y', label='Y seed region (fraction)', type='float', default=.65, min=.1, max=1.),
]
# Start this comparison at the user's 2026-10-10 reference density. These are
# fixed experiment defaults, not reads/writes of the live viewer settings.
_REFERENCE_DEFAULTS = dict(extent=9.458, y_extent=9.458*.234, frequency=2.505, width=.025,
                           roughness=.107, clumping=6.875, strand_continuity=1.)
for _entry in PARAMETERS:
    if _entry['key'] in _REFERENCE_DEFAULTS:
        _entry['default'] = _REFERENCE_DEFAULTS[_entry['key']]
    if _entry['key'] == 'y_extent':
        _entry['min'] = .01
    if _entry['key'] == 'width':
        _entry['label'] = 'Density support width (noise units)'


def migrate_parameters(params):
    # This experiment's historical defaults differ from the direct sampler.
    supplied = dict(extent=9.458, y_scale=.234)
    supplied.update(params)
    return migrate_axes(supplied)


def postprocess_bounds(extent=9.458, y_scale=.234, y_extent=None, **params):
    half_y = extent*y_scale if y_extent is None else y_extent
    return np.zeros(3), np.array([extent, half_y, extent])


def generate_population_source(count, seed, extent=9.458, y_scale=.234, y_extent=None,
                               curve_resolution=48, seed_spacing=1., strand_length=2.,
                               seed_xz=.65, seed_y=.65, **params):
    half_y = extent*y_scale if y_extent is None else y_extent
    if half_y <= 0:
        raise ValueError('Exact pair-zero curves need positive Y extent; use previous growth for a flat slice')
    half = np.array([extent, half_y, extent])
    density_params = {entry['key']: entry['default'] for entry in PARAMETERS
                      if entry['key'] in _DENSITY_KEYS}
    # Ignore retired controls if a caller supplies an old preset directly.
    density_params.update({k: v for k, v in params.items() if k in _DENSITY_KEYS})
    density, fields = base.build_density(seed, y_scale=half_y/extent, **density_params,
                                        _return_fields=True, _resolution=curve_resolution)
    source_paths = extract_paths(fields, half)
    scale = support_scale(source_paths, density, half, seed_spacing)
    paths, owners = seeded_paths(source_paths, density, half, seed, seed_spacing,
                                strand_length, seed_xz, seed_y, reference_scale=scale)
    if not paths:
        raise ValueError('No curves in the seed region; enlarge it or try another noise seed')
    # Colors follow the original path, even when density splits visible intervals.
    phase = np.random.default_rng(np.random.SeedSequence([seed, 82421])).random()
    hues = (phase + owners * .618033988749895) % 1.
    colors = np.array([hsv_to_rgb(hue, .65, 1.) for hue in hues])
    vertices = [np.stack((p[:-1], p[1:]), axis=1).reshape(-1, 3) for p in paths]
    positions = np.concatenate(vertices).astype(np.float32)
    rgb = np.concatenate([np.broadcast_to(c, v.shape) for c, v in zip(colors, vertices)]).astype(np.float32)
    return (positions, rgb, .04), paths, colors


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
