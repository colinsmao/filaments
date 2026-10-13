"""Density-grown candidate curves selected by candle mass and rod proximity."""
from colorsys import hsv_to_rgb
import time
import numpy as np
from _density_field import PARAMETERS as FIELD_PARAMETERS
from density_filament_selection import LOCAL_PARAMETERS as GROWTH_PARAMETERS
from _axis_controls import FADE_PARAMETERS, SIGNED_Y_FADE_PARAMETERS
from _curve_selection import build_pool
from _population_selection import build_sketch, select_population, sketch_parameters
from _block_population import cell_uniform
from _selection_defaults import DEFAULTS

NAME = 'Incremental candle / rod curve selection'
PRIMITIVE = 'lines'
NATIVE_BLOCKS = SHARED_DENSITY_FIELD = NATIVE_AXIS_FADE = POPULATION_AXIS_FADE = True
PARAMETER_DEFAULTS = dict(DEFAULTS, seed_rate=96., seed_density_power=1., strand_length=120.,
    seed_y_neg=-0.09090912342071533, seed_y_pos=0.7222222089767456,
    growth_response=8.276000022888184, growth_pull=.35, growth_wander=.15, length_variation=.6,
    pop_density=.9, pop_source_density=.35, pop_curve_density_variation=.25,
    pop_spread_xz=.2, pop_spread_y=.1, pop_rod_density=.2,
    pop_light_sky=.1, pop_light_ambient=.02)
SHORT_PARAMETERS = [
    dict(key='short_curve_fraction', label='Short candidate fraction', type='float', default=.75, min=0., max=1.,
         description='Fraction of candidate roots assigned the short length below, using a stable per-root hash. 0 restores a single length population; 1 makes all candidates short. Changes lengths, selection and star count, not root locations.'),
    dict(key='short_curve_length', label='Mean short curve length (blocks)', type='float', default=24., min=1., max=384.,
         description='Mean total arc budget for the short candidates, before the same length variation and domain clipping. Adds local strands without broadening their star scatter. Changes geometry and star count, not the length-class random draw.'),
    dict(key='short_growth_response', label='Short response length (blocks)', type='float', default=2., min=1., max=128.,
         description='Response length for short candidates only. Smaller follows direction changes sooner, smooths density over a smaller area and shortens the wandering wavelength (4 times this value). Step length is half this value, so smaller costs more. Changes short geometry, selection and star count; root draws and length budgets stay fixed.'),
    dict(key='short_growth_wander', label='Short wandering strength', type='float', default=.8, min=0., max=2.,
         description='Dimensionless strength of coherent two-octave noise for short candidates only. Higher bends them more; 0 removes wandering but keeps density steering. Changes geometry, selection and star count, not root locations or length budgets. Shares the existing noise seed; this is curve bending, not star scatter.'),
]
LOCAL_PARAMETERS = []
for p in GROWTH_PARAMETERS:
    LOCAL_PARAMETERS.append(dict(p))
    if p['key'] == 'strand_length':
        LOCAL_PARAMETERS.extend(SHORT_PARAMETERS)
# Selection assigns material roles. Random material lottery weights have no
# meaning here; other experiments continue to expose and use them unchanged.
OMIT_POPULATION_PARAMETERS = ('pop_candle_weight', 'pop_rod_weight', 'pop_full_block_weight', 'pop_full_block_density')
PARAMETERS = [dict(p) for p in FIELD_PARAMETERS]+[dict(p) for p in LOCAL_PARAMETERS]+[
    dict(key='select_enabled', label='Apply incremental selection', type='int', default=1, min=0, max=1, toggle=True,
         description='On: select whole candle/rod curves. Off: populate all candidates as candles for comparison. Changes star count; no new random draws.'),
    dict(key='select_budget', label='Density budget multiplier', default=5., min=.05, max=16.,
         description='Dimensionless target population multiplier. Higher usually retains more candle curves and stars. This is a soft density target, not a fixed curve count.'),
    dict(key='select_density', label='Density contrast (0 = uniform)', default=.5, min=0., max=2.,
         description='Exponent of the upstream density in the selection target. Higher concentrates curves into dense patches and leaves larger gaps. Changes selected curves and star count; 0 allows sparse excursions.'),
    dict(key='select_scale', label='Candle overlap scale (blocks)', default=8., min=2., max=32.,
         description='Spacing of the trilinear population comparison grid. Nearby stars interact smoothly over roughly twice this distance per axis. Larger values treat more routes as redundant; changes counts and spatial detail.'),
    dict(key='select_isolation', label='Candle isolation penalty', default=.9, min=0., max=2.,
         description='Dimensionless penalty for a candle candidate far from already selected candle population. Higher discourages floating strands; 0 restores the previous selector. The first candle curve is exempt; high values may leave only one cluster. Changes selected curves and star count, with no new random draws.'),
    dict(key='select_isolation_distance', label='Isolation distance (blocks)', default=8., min=1., max=32.,
         description='Distance scale for the closest pair of positive-mass population samples. Larger permits wider gaps; at this distance the penalty is 63% of its maximum. One nearby approach is enough. Samples approximate stars, so final visible attachment is not guaranteed. Changes selection/counts, not candidate geometry.'),
    dict(key='select_rods', label='Select rod curves', type='int', default=1, min=0, max=1, toggle=True,
         description='Assign some candidates to rods using candle attraction and rod repulsion. Requires Block population and Minecraft material proxies. Off selects candles only.'),
    dict(key='select_rod_scale', label='Rod proximity scale (blocks)', default=12., min=2., max=32.,
         description='Grid spacing for both rod-candle attraction and rod-rod repulsion. A soft proximity approximation, not a lighting calculation. Larger values connect more distant populations.'),
    dict(key='select_rod_attraction', label='Rod attraction to candles', default=.75, min=0., max=4.,
         description='Dimensionless reward for rod population near selected candle population. Higher usually selects more rod curves and rods; 0 selects no rods.'),
    dict(key='select_rod_repulsion', label='Rod repulsion from rods', default=5., min=1., max=200.,
         description='Dimensionless penalty for overlapping rod populations. Higher usually selects fewer, more separated rod curves. Includes each candidate\'s own footprint so isolated rods need candle support.'),
    dict(key='select_short_rod_penalty', label='Short-curve rod penalty', default=.5, min=0., max=2.,
         description='Dimensionless extra cost for assigning a short candidate to rods. Higher leaves more shorts available to fill candle density; 0 gives both length classes the same rod rules. Soft preference, not a ban: a short may still become a rod or be rejected. Changes roles and star count, not candidate geometry or random draws.'),
    dict(key='select_samples', label='Population samples per curve', type='int', default=128, min=32, max=512,
         description='Integration quality, rounded up to a power of two. Higher resolves scatter and density better but costs memory/time; may change selection/counts. Deterministic samples, not rendered stars.'),
]+[dict(p) for p in FADE_PARAMETERS if p['key'].startswith('fade_xz')]+[dict(p) for p in SIGNED_Y_FADE_PARAMETERS]
for p in PARAMETERS:
    p.setdefault('type', 'float')
    if p['key'] in PARAMETER_DEFAULTS:
        p['default'] = PARAMETER_DEFAULTS[p['key']]
    if p['key'] == 'seed_rate':
        p['description'] = 'Mean candidate roots per million seed-region blocks. Higher offers more choices and costs more. Seed locations remain nested when only this rate increases; final selected curves and star count may change.'
    if p['key'] == 'strand_length':
        p['label'] = 'Mean long curve length (blocks)'
        p['description'] = 'Mean total arc budget in blocks for the long candidate class, before length variation and domain clipping. Changes geometry and star count, not root locations. With Short candidate fraction 0, this applies to all candidates.'
    if p['key'] == 'growth_response':
        p['label'] = 'Long response length (blocks)'
        p['description'] = 'Density smoothing and heading response length for long candidates only, in blocks. Smaller follows finer direction changes; step length is half this value. Changes geometry, selection and star count. Short candidates have their own response length above.'
    if p['key'] == 'growth_wander':
        p['label'] = 'Long wandering strength'
        p['description'] = 'Dimensionless coherent noise strength for long candidates only. Higher adds more wandering; 0 keeps density steering alone. Changes geometry, selection and star count without resampling roots. Short candidates have their own wandering strength above.'
    if p['key'].startswith('select_'):
        p.update(section='selection', group='Curve selection')
        if p['key'] != 'select_enabled':
            p['enabled_if'] = 'select_enabled'


def postprocess_bounds(extent=9.458*16, y_extent=9.458*.234*16, **params):
    return np.zeros(3), np.array([extent, y_extent, extent])


def generate_population_plan(count, seed, **params):
    p = dict(PARAMETER_DEFAULTS)
    p.update({entry['key']: entry['default'] for entry in PARAMETERS})
    p.update(params)
    started = time.perf_counter()
    pool = build_pool(seed, tuple((e['key'], p[e['key']]) for e in FIELD_PARAMETERS),
                      tuple((e['key'], p[e['key']]) for e in LOCAL_PARAMETERS), max_candidates=2048)
    if not pool.paths:
        raise ValueError('No candidate curves; increase Candidate seeds per million blocks')
    pool_ms = 1000*(time.perf_counter()-started)
    started = time.perf_counter()
    sketch = build_sketch(pool, seed, sketch_parameters(p), p['select_samples'])
    sketch_ms = 1000*(time.perf_counter()-started)
    indices, kinds, stats = select_population(pool, sketch, p)
    stats.update(pool_ms=pool_ms, sketch_ms=sketch_ms)
    short = pool.short_mask
    stats.update(short_candidates=int(short.sum()),
                 short_candles=int(np.count_nonzero(short[indices] & (kinds == 0))),
                 short_rods=int(np.count_nonzero(short[indices] & (kinds == 1))))
    paths = [pool.paths[i] for i in indices]
    if sum(2*(len(path)-1) for path in paths) > 1_000_000:
        raise ValueError('Selected preview exceeds 1 million vertices; reduce candidate rate or length')
    colors = np.array([hsv_to_rgb(h, .65, 1.) for h in cell_uniform(pool.owners[indices], seed, 82421)])
    colors[kinds == 1] = [1., .78, .25]
    vertices = [np.stack((path[:-1], path[1:]), axis=1).reshape(-1, 3) for path in paths]
    lines = (np.concatenate(vertices).astype(np.float32),
             np.concatenate([np.broadcast_to(c, v.shape) for c, v in zip(colors, vertices)]).astype(np.float32), .04)
    context = dict(_curve_ids=sketch.identities[indices], _curve_kinds=kinds,
                   _population_profiles=None if sketch.profiles is None else [sketch.profiles[i] for i in indices],
                   _warp_spread=sketch.warp_spread)
    return dict(source=(lines, paths, colors, (pool.density, pool.half)), population=context, stats=stats)


def generate_population_density_source(count, seed, **params):
    return generate_population_plan(count, seed, **params)['source']


def generate_population_source(count, seed, **params):
    return generate_population_density_source(count, seed, **params)[:3]


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
