"""Unobstructed, scalar block lighting for material proxies after survival fades.

Evaluate at cell centers in blocks. Equal-strength sources reduce to a nearest
Manhattan-neighbor query, so two trees avoid all-pairs work or a dense light grid.
"""
import numpy as np
from scipy.spatial import cKDTree


PARAMETERS = [
    dict(key='pop_lighting', label='Block lighting', type='int', default=1,
         min=0, max=1, toggle=True, enabled_if='pop_block_proxies', group='Block lighting'),
    dict(key='pop_light_ambient', label='Ambient brightness', type='float', default=.03,
         min=0., max=1., enabled_if='pop_lighting', group='Block lighting'),
    dict(key='pop_light_sky', label='Night sky illumination', type='float', default=.35,
         min=0., max=1., enabled_if='pop_lighting', group='Block lighting'),
    dict(key='pop_light_brightness', label='Shadow brightness lift', type='float', default=1.,
         min=0., max=1., enabled_if='pop_lighting', group='Block lighting'),
]


def migrate_parameters(params):
    """Replace only the previous trial's untouched lighting preset on reload.

    The worker returns these values to normal viewer autosave. Custom settings
    remain literal; no files are edited here. Repeated migration is a no-op.
    """
    params = dict(params)
    keys = ('pop_light_ambient', 'pop_light_sky', 'pop_light_brightness')
    values = [params.get(k) for k in keys]
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        ambient, sky, lift = values
        if (any(abs(ambient-v) < 1e-6 for v in (.03, .08))
                and abs(sky-.2) < 1e-6 and abs(lift-.5) < 1e-6):
            params.update(pop_light_ambient=.03, pop_light_sky=.35, pop_light_brightness=1.)
    return params


def light_levels(positions, kinds):
    """Max(E - L1 distance, 0); candles=0, rods=14, full blocks=15.

    Inputs contain only surviving cells. Obstacles are deliberately ignored;
    candles receive light but never relay or emit it. No colored light or RNG.
    """
    positions = np.asarray(positions, dtype=float)
    kinds = np.asarray(kinds)
    levels = np.zeros(len(positions), dtype=float)
    for kind, emission in ((1, 14), (2, 15)):
        sources = positions[kinds == kind]
        if not len(sources):
            continue
        tree = cKDTree(sources)
        # Bounded batches keep temporary memory independent of cloud size.
        for start in range(0, len(positions), 65536):
            end = start + 65536
            distance, _ = tree.query(positions[start:end], k=1, p=1,
                                     distance_upper_bound=float(emission))
            levels[start:end] = np.maximum(levels[start:end], emission-distance)
    return levels


def light_colors(levels, params):
    """Java 1.21 normal lightmap path, with an exposed sky tuned to scar/.

    Uses Minecraft's warm block RGB ramp, both neutral baseline mixes and
    quartic brightness lift. The canopy has unobstructed sky (sky level 15).
    Sky strength/tint and extra ambient are artistic settings, not recovered
    game settings. No time-of-day, weather or status effects.
    Reference: https://mcasset.cloud/1.21.8/assets/minecraft/shaders/core/lightmap.fsh
    """
    ambient = float(params.get('pop_light_ambient', .03))
    sky = float(params.get('pop_light_sky', .35))
    lift = float(params.get('pop_light_brightness', 1.))
    levels = np.asarray(levels, dtype=float)
    local = levels / (60. - 3.*levels)
    rgb = np.stack((local, local*((local*.6+.4)*.6+.4),
                    local*(local*local*.6+.4)), axis=-1)
    rgb += sky*np.array([.8, .82, 1.])
    rgb = np.clip(rgb*.96 + .03 + ambient, 0., 1.)
    rgb = (1.-lift)*rgb + lift*(1.-(1.-rgb)**4)
    return np.clip(rgb*.96 + .03, 0., 1.)


def apply_lighting(positions, colors, kinds, params):
    """Bake illumination into RGB, preserving geometry and upstream base colors.

    Emitters pass their own level through the same lightmap as candles.
    """
    if not params.get('pop_lighting', 1) or len(positions) == 0:
        return colors
    ambient = float(params.get('pop_light_ambient', .03))
    if ambient == 1:
        return colors
    levels = light_levels(positions, kinds)
    illumination = light_colors(levels, params)
    return (colors * illumination).astype(np.float32)
