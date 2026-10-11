"""Original noise-filament density -> local stochastic strands -> shared stars."""
import numpy as np
import noise_filaments as base
from _density_curves import trace_density

NAME = 'Density-guided local strands'
PRIMITIVE = 'lines'
_DENSITY_KEYS = {'extent', 'y_scale', 'layer_continuity', 'frequency', 'width',
                 'strand_continuity', 'octaves', 'roughness', 'clumping'}
PARAMETERS = [dict(entry) for entry in base.PARAMETERS if entry['key'] in _DENSITY_KEYS] + [
    dict(key='strand_count', label='Local strands', type='int', default=512, min=16, max=2048),
    dict(key='strand_length', label='Mean strand length (units)', type='float', default=2., min=.2, max=6.),
    dict(key='direction_scale', label='Density direction radius (units)', type='float', default=.3, min=.1, max=1.5),
    dict(key='density_pull', label='Transverse density pull', type='float', default=.35, min=0., max=2.),
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
_REFERENCE_DEFAULTS = dict(extent=9.458, y_scale=.234, frequency=2.505, width=.025,
                           roughness=.107, clumping=6.875, strand_continuity=1.)
for _entry in PARAMETERS:
    if _entry['key'] in _REFERENCE_DEFAULTS:
        _entry['default'] = _REFERENCE_DEFAULTS[_entry['key']]


def generate_population_source(count, seed, extent=9.458, y_scale=.234, strand_count=512,
                               strand_length=2., direction_scale=.3, density_pull=.35,
                               curve_wander=.15, join_reach=.6, join_strength=1.,
                               join_radius=.08, coverage_mode=1, coverage_radius=.5,
                               capacity_scale=1., **params):
    density_params = {entry['key']: entry['default'] for entry in PARAMETERS
                      if entry['key'] in _DENSITY_KEYS-{'extent', 'y_scale'}}
    # Ignore retired controls if a caller supplies an old preset directly.
    density_params.update({k: v for k, v in params.items() if k in _DENSITY_KEYS})
    density = base.build_density(seed, y_scale=y_scale, **density_params)
    paths = trace_density(density, seed, [extent, extent*y_scale, extent],
                          strand_count, strand_length, direction_scale, density_pull, curve_wander,
                          join_reach, join_strength, join_radius,
                          coverage_mode, coverage_radius, capacity_scale)
    colors = np.tile([.65, .8, 1.], (len(paths), 1))
    vertices = [np.stack((p[:-1], p[1:]), axis=1).reshape(-1, 3) for p in paths]
    positions = np.concatenate(vertices).astype(np.float32)
    rgb = np.concatenate([np.broadcast_to(c, v.shape) for c, v in zip(colors, vertices)]).astype(np.float32)
    return (positions, rgb, .04), paths, colors


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
