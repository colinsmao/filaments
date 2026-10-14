"""Stars on the existing unguided block graph; no upstream density field."""
from functools import lru_cache

import numpy as np

from _block_scaffold import grow, preview
from block_scaffold import PARAMETERS as SCAFFOLD_PARAMETERS, control

NAME = 'Stars on unguided block scaffold'
PRIMITIVE = 'lines'
NATIVE_BLOCKS = True
PARAMETERS = [dict(p) for p in SCAFFOLD_PARAMETERS if p['group'] != 'Preview']
PARAMETERS += [
    control('bend_memory', 'Turn continuation', 'float', 0., 0., 1.,
            'Experimental dimensionless bias toward continuing the previous bend, 0-1. Zero retains independent turns exactly. Changes integer scaffold geometry and resulting star count; no spatial guidance field.',
            'Local growth'),
    control('child_length_cap', 'Maximum child lifetime', 'int', 0, 0, 512,
            'Blocks per child path, after the existing random lifetime draw. Zero disables. Separates branch length from trunk reach; descendants still share the root cell cap. Changes scaffold and star count.',
            'Local growth'),
    control('branch_active_length', 'Mean branching period', 'int', 0, 0, 512,
            'Blocks traveled with fork opportunities before a quiet period. Each period draws 0.5-1.5 times the mean in its own random stream. Both period lengths must be positive; either zero preserves continuous branching. Changes scaffold and star count.',
            'Local growth'),
    control('branch_quiet_length', 'Mean quiet period', 'int', 0, 0, 512,
            'Blocks traveled without new forks between branching periods, with independent 0.5-1.5 variation. Existing tips continue. Local state only, no patch centers or destinations. Changes scaffold and star count.',
            'Local growth'),
]
GROWTH_KEYS = tuple(p['key'] for p in PARAMETERS)
PARAMETERS += [
    control('mixed_materials', 'Mix materials within branches', 'int', 1, 0, 1,
            'Block mode: place every branch at candle density, then assign a material to each occupied cell. Curve material weights and rod/block density multipliers below apply only when off. Never changes the scaffold.',
            'Scaffold population', toggle=True),
    control('rod_fraction', 'Rod fraction of occupied cells', 'float', .075, 0., .8,
            'Used only with mixed materials. Changes material, light and shape, but not occupied cells or scaffold.',
            'Scaffold population', enabled_if='mixed_materials'),
    control('block_fraction', 'Luminous block fraction', 'float', .006, 0., .2,
            'Used only with mixed materials. Remaining occupied cells are candles. Changes material, light and shape, but not occupied cells or scaffold.',
            'Scaffold population', enabled_if='mixed_materials'),
]
PARAMETER_DEFAULTS = dict(pop_density=1.1, pop_curve_density_variation=.35,
                          pop_spread_xz=.35, pop_spread_y=.2, pop_taper=0.,
                          pop_clumping=1.5, pop_clump_scale=12., pop_rod_density=.2,
                          pop_light_sky=.1, pop_light_ambient=.02,
                          pop_light_brightness=1.)


@lru_cache(maxsize=2)
def _graph(seed, growth):
    return grow(seed, **dict(growth))


def population_paths(graph):
    """Retain grown paths and any extra contact edges, with stable identities.

    Some steps touch several neighbors. Only one contact continues the path;
    the other explicit graph edges must also be available to population.
    Failed zero-length paths contribute no population mass.
    """
    paths, ids, represented = [], [], set()
    for pid, nodes in enumerate(graph.paths):
        if len(nodes) < 2:
            continue
        paths.append(graph.cells[nodes].astype(float) + .5)
        ids.append(pid)
        represented.update(tuple(sorted((int(a), int(b)))) for a, b in zip(nodes, nodes[1:]))
    for eid, (a, b) in enumerate(graph.edges):
        if (int(a), int(b)) not in represented:
            paths.append(graph.cells[[a, b]].astype(float) + .5)
            ids.append(len(graph.paths) + eid)
    colors = np.full((len(paths), 3), [.78, .80, .85])
    return paths, colors, np.asarray(ids, dtype=np.int64)


def generate_population_plan(count, seed, **params):
    graph = _graph(seed, tuple((k, params[k]) for k in GROWTH_KEYS if k in params))
    paths, colors, ids = population_paths(graph)
    population = dict(_curve_ids=ids)
    if params.get('mixed_materials', 1):
        rods, blocks = params.get('rod_fraction', .075), params.get('block_fraction', .006)
        population.update(_curve_kinds=np.zeros(len(paths), dtype=np.int8),
                          _cell_material_fractions=[1. - rods - blocks, rods, blocks])
    return dict(source=(preview(graph, mark_junctions=False), paths, colors, None),
                population=population,
                stats={f'scaffold_{k}': graph.stats[k] for k in ('cells', 'edges', 'components', 'cycles')})


def generate_population_source(count, seed, **params):
    return generate_population_plan(count, seed, **params)['source'][:3]


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]


def postprocess_bounds(width=275, height=55, **params):
    return np.zeros(3), np.asarray([width, height, width], dtype=float) / 2
