"""Existing density-guided curves -> overlap-aware subset -> shared stars."""
from colorsys import hsv_to_rgb
import numpy as np
from _density_field import PARAMETERS as FIELD_PARAMETERS
from _grid_density_curves import PARAMETERS as SEED_PARAMETERS
from _field_curves import PARAMETERS as GROWTH_PARAMETERS
from _axis_controls import FADE_PARAMETERS, SIGNED_Y_FADE_PARAMETERS
from _block_population import cell_uniform
from _curve_selection import build_pool, build_coverage, select_curves

NAME = 'Density filament curves (select coverage)'
PRIMITIVE = 'lines'
NATIVE_BLOCKS = True
SHARED_DENSITY_FIELD = True
NATIVE_AXIS_FADE = True
POPULATION_AXIS_FADE = True
LOCAL_PARAMETERS = [dict(p) for p in SEED_PARAMETERS]+[
    dict(key='strand_length', label='Mean candidate curve length (blocks)', type='float', default=300., min=1., max=3840.),
    dict(key='seed_xz', label='XZ seed region (fraction)', type='float', default=.8, min=.1, max=1.),
]+[dict(p) for p in GROWTH_PARAMETERS if not p['key'].startswith('growth_join')]
for p in LOCAL_PARAMETERS:
    if p['key'] == 'seed_rate':
        p.update(default=50., label='Candidate seeds per million blocks')
PARAMETERS = [dict(p) for p in FIELD_PARAMETERS]+LOCAL_PARAMETERS+[
    dict(key='selection_enabled', label='Select curves to reduce overlap', type='int', default=1, min=0, max=1, toggle=True),
    dict(key='selection_radius', label='Parallel overlap reach (blocks)', default=8., min=1., max=32.),
    dict(key='selection_angle', label='Parallel overlap angle (degrees)', default=30., min=0., max=90.),
    dict(key='selection_coverage', label='Retain candidate corridor coverage', default=.95, min=.5, max=1.),
    dict(key='selection_length_cost', label='Prefer less total curve length', default=.5, min=0., max=1.),
    dict(key='selection_density', label='Favor dense corridors (0 = equal)', default=0., min=0., max=3.),
]+[dict(p) for p in FADE_PARAMETERS if p['key'].startswith('fade_xz')]+[dict(p) for p in SIGNED_Y_FADE_PARAMETERS]
for p in PARAMETERS:
    p.setdefault('type', 'float')
    if p['key'].startswith('selection_') and p['key'] != 'selection_enabled':
        p['enabled_if'] = 'selection_enabled'


def postprocess_bounds(extent=9.458*16, y_extent=9.458*.234*16, **params):
    return np.zeros(3), np.array([extent, y_extent, extent])


def generate_population_source(count, seed, _return_density=False, **params):
    p = {entry['key']: params.get(entry['key'], entry['default']) for entry in PARAMETERS}
    field = tuple((e['key'], p[e['key']]) for e in FIELD_PARAMETERS)
    growth = tuple((e['key'], p[e['key']]) for e in LOCAL_PARAMETERS)
    pool = build_pool(seed, field, growth)
    if not pool.paths:
        raise ValueError('No candidate curves; increase candidate seed rate or enlarge the seed region')
    indices = (select_curves(pool, build_coverage(pool, p['selection_radius'], p['selection_angle']),
                            p['selection_coverage'], p['selection_length_cost'], p['selection_density'])
               if p['selection_enabled'] else np.arange(len(pool.paths)))
    paths = [pool.paths[i] for i in indices]
    if sum(2*(len(path)-1) for path in paths) > 1_000_000:
        raise ValueError('Selected preview exceeds 1 million vertices; reduce candidate rate/length')
    colors = np.array([hsv_to_rgb(h, .65, 1.) for h in cell_uniform(pool.owners[indices], seed, 82421)])
    vertices = [np.stack((path[:-1], path[1:]), axis=1).reshape(-1, 3) for path in paths]
    line = (np.concatenate(vertices).astype(np.float32),
            np.concatenate([np.broadcast_to(c, v.shape) for c, v in zip(colors, vertices)]).astype(np.float32), .04)
    result = line, paths, colors
    return (*result, (pool.density, pool.half)) if _return_density else result


def generate_population_density_source(count, seed, **params):
    return generate_population_source(count, seed, _return_density=True, **params)


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
