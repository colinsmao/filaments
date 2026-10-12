"""Independent rooted-branching experiment using the shared density and stars."""
from colorsys import hsv_to_rgb
import numpy as np
from density_filament_curves import PARAMETERS as CURVE_PARAMETERS, migrate_parameters, postprocess_bounds
from _grid_density_curves import PARAMETERS as SEED_PARAMETERS, block_seeds
from _field_curves import PARAMETERS as GROWTH_PARAMETERS
from _branching_field import PARAMETERS as BRANCH_PARAMETERS, grow_branches
from _density_field import PARAMETERS as FIELD_PARAMETERS, build_field
from _block_population import cell_uniform

NAME = 'Density filament branching'
PRIMITIVE = 'lines'
NATIVE_AXIS_FADE = True
POPULATION_AXIS_FADE = True
# Shared legacy schema conversion is applied once by the worker, just as for
# the original curve script. This script has its own preset and growth controls.
PARAMETERS = [dict(p) for p in CURVE_PARAMETERS if p['key'] not in ('seed_spacing', 'strand_length')]
GRID_PARAMETERS = ([dict(p) for p in SEED_PARAMETERS if p['key'] != 'seed_rate'] +
                   [dict(p) for p in GROWTH_PARAMETERS if not p['key'].startswith('growth_join')] +
                   [dict(p) for p in BRANCH_PARAMETERS])


def generate_population_source(count, seed, extent=9.458*16, y_extent=9.458*.234*16,
                               noise_scale=9.458/2.505*16, field_resolution=48,
                               seed_xz=.65, seed_y=.65, seed_y_pos=None, seed_y_neg=None,
                               branch_root_rate=.5, seed_density_power=1., branch_length=1200.,
                               length_variation=.5, growth_response=8., growth_pull=.35,
                               growth_wander=.15, branch_spacing=48., branch_angle=45.,
                               _return_density=False, **params):
    if y_extent <= 0:
        raise ValueError('Density filament branching needs positive Y extent')
    density_params = {p['key']: params.get(p['key'],p['default']) for p in FIELD_PARAMETERS
                      if p['key'] not in ('extent','y_extent','noise_scale','field_resolution')}
    density, _, half = build_field(seed, extent, y_extent, noise_scale,
                                   resolution=field_resolution, **density_params)
    cells = block_seeds(density, half, seed, branch_root_rate, seed_density_power,
                        seed_xz, seed_y, seed_y_pos, seed_y_neg)
    paths, owners = grow_branches(density, half, cells, seed, branch_length, length_variation,
                                 growth_response, growth_pull, growth_wander, branch_spacing, branch_angle)
    if not paths:
        raise ValueError('No branching roots in the seed region; increase root rate, enlarge the region, or change scene seed')
    colors = np.array([hsv_to_rgb(hue,.65,1.) for hue in cell_uniform(owners,seed,82421)])
    vertices = [np.stack((p[:-1],p[1:]),axis=1).reshape(-1,3) for p in paths]
    positions = np.concatenate(vertices).astype(np.float32)
    rgb = np.concatenate([np.broadcast_to(c,v.shape) for c,v in zip(colors,vertices)]).astype(np.float32)
    result = (positions,rgb,.04), paths, colors
    return (*result,(density,half)) if _return_density else result


def generate_population_density_source(count, seed, **params):
    return generate_population_source(count, seed, _return_density=True, **params)


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
