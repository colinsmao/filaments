"""Hashed block seeds -> direct density-field growth -> shared stars."""
from colorsys import hsv_to_rgb
import numpy as np
import noise_filaments_branches as base
from _axis_controls import migrate_signed_y as migrate_axes, SIGNED_Y_FADE_PARAMETERS
from _stable_density_curves import extract_paths, seeded_paths, support_scale
from _density_field import build_field
from _grid_density_curves import PARAMETERS as SEED_PARAMETERS, block_seeds
from _field_curves import PARAMETERS as GROWTH_PARAMETERS, grow_field
from _block_population import cell_uniform

NAME = 'Density filament curves (field growth)'
GRID_PARAMETERS = SEED_PARAMETERS + GROWTH_PARAMETERS
PRIMITIVE = 'lines'
NATIVE_AXIS_FADE = True
POPULATION_AXIS_FADE = True
_DEFAULT_NOISE_SCALE = 9.458 / 2.505
_DENSITY_KEYS = {'width', 'strand_continuity', 'octaves', 'roughness',
                 'clumping', 'density_low', 'density_mid', 'density_high',
                 'broad_strength', 'broad_scale'}
PARAMETERS = [dict(entry) for entry in base.PARAMETERS
              if entry['key'] not in ('star_size', 'size_variation', 'frequency')
              and not entry['key'].startswith('fade_y')] + [
    *(dict(entry) for entry in SIGNED_Y_FADE_PARAMETERS),
    dict(key='noise_scale', label='Noise scale (units)', type='float', default=_DEFAULT_NOISE_SCALE, min=.1, max=60.),
    dict(key='curve_resolution', label='Zero-surface grid resolution', type='int', default=48, min=24, max=96),
    dict(key='seed_spacing', label='Curve seed spacing (units)', type='float', default=1., min=.2, max=5.),
    dict(key='strand_length', label='Mean travel at full density (units)', type='float', default=2., min=.2, max=30.),
    dict(key='seed_xz', label='XZ seed region (fraction)', type='float', default=.65, min=.1, max=1.),
    dict(key='seed_y', label='Y seed region (fraction)', type='float', default=.65, min=.1, max=1.),
]
# Start this comparison at the user's 2026-10-10 reference density. These are
# fixed experiment defaults, not reads/writes of the live viewer settings.
_REFERENCE_DEFAULTS = dict(extent=9.458, y_extent=9.458*.234, width=.025,
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
    migrated = migrate_axes(supplied)
    for side in ('pos', 'neg'):
        migrated.setdefault(f'seed_y_{side}', migrated.get('seed_y', .65))
    if 'noise_scale' not in migrated:
        # Freeze the old preset's physical wavelength once. The worker returns
        # the new key, and subsequent extent edits leave it unchanged.
        migrated['noise_scale'] = (migrated['extent'] / migrated['frequency']
                                   if 'frequency' in migrated else _DEFAULT_NOISE_SCALE)
    return migrated


def postprocess_bounds(extent=9.458, y_scale=.234, y_extent=None, **params):
    half_y = extent*y_scale if y_extent is None else y_extent
    return np.zeros(3), np.array([extent, half_y, extent])


def generate_population_source(count, seed, extent=9.458, y_scale=.234, y_extent=None,
                               curve_resolution=48, seed_spacing=1., strand_length=2.,
                               seed_xz=.65, seed_y=.65, noise_scale=None, field_resolution=None,
                               seed_y_pos=None, seed_y_neg=None,
                               _return_density=False, seed_rate=None, seed_density_power=1.,
                               length_variation=.5, growth_response=8., growth_pull=.35,
                               growth_wander=.15, growth_join=1, growth_join_angle=30., growth_join_distance=16., **params):
    half_y = extent*y_scale if y_extent is None else y_extent
    if half_y <= 0:
        raise ValueError('Density filament curves need positive Y extent; use previous growth for a flat slice')
    half = np.array([extent, half_y, extent])
    density_params = {entry['key']: entry['default'] for entry in PARAMETERS
                      if entry['key'] in _DENSITY_KEYS}
    # Ignore retired controls if a caller supplies an old preset directly.
    density_params.update({k: v for k, v in params.items() if k in _DENSITY_KEYS})
    if noise_scale is None:
        # Explicit legacy Python calls keep their original frequency meaning.
        # Ordinary calls/defaults use the new physical scale independently of bounds.
        noise_scale = extent/params['frequency'] if 'frequency' in params else _DEFAULT_NOISE_SCALE
    if not np.isfinite(noise_scale) or noise_scale <= 0:
        raise ValueError('Noise scale must be finite and positive')
    # The shared builder takes normalized coordinates: compensate its box
    # normalization so a fixed world position always sees x/noise_scale.
    density, fields, half = build_field(seed, extent, half_y, noise_scale,
                                        resolution=curve_resolution if field_resolution is None else field_resolution, **density_params)
    cells = (block_seeds(density, half, seed, seed_rate, seed_density_power, seed_xz, seed_y,
                         seed_y_pos, seed_y_neg)
             if seed_rate is not None else None)
    if cells is not None:
        paths, owners = grow_field(density, half, cells, seed, strand_length, length_variation,
                                  growth_response, growth_pull, growth_wander,
                                  bool(growth_join), growth_join_angle, join_distance=growth_join_distance)
    else:
        # Preserve the earlier arc-root experiment for legacy Python callers.
        source_paths = extract_paths(fields, half)
        scale = support_scale(source_paths, density, half, seed_spacing)
        paths, owners = seeded_paths(source_paths, density, half, seed, seed_spacing,
                                    strand_length, seed_xz, seed_y, reference_scale=scale)
    if not paths:
        raise ValueError('No curves from the seed region; increase root/seed rate, enlarge the region, or try another scene seed')
    # Field-grown curves retain their seed block identity; legacy curves
    # retain their original guide colors.
    phase = np.random.default_rng(np.random.SeedSequence([seed, 82421])).random()
    hues = (cell_uniform(owners, seed, stream=82421) if cells is not None
            else (phase + owners * .618033988749895) % 1.)
    colors = np.array([hsv_to_rgb(hue, .65, 1.) for hue in hues])
    vertices = [np.stack((p[:-1], p[1:]), axis=1).reshape(-1, 3) for p in paths]
    positions = np.concatenate(vertices).astype(np.float32)
    rgb = np.concatenate([np.broadcast_to(c, v.shape) for c, v in zip(colors, vertices)]).astype(np.float32)
    result = (positions, rgb, .04), paths, colors
    return (*result, (density, half)) if _return_density else result


def generate_population_density_source(count, seed, **params):
    return generate_population_source(count, seed, _return_density=True, **params)


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
