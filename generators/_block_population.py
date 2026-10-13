"""Sparse cell-mass integration and occupancy sampling for the Minecraft trial.

Native curves and density controls use blocks; legacy callers supply a scale.
Integration probes estimate mass in unit cells; they are never rendered. Each cell
gets one Bernoulli trial with probability 1-exp(-mass), equivalent to asking
whether a Poisson population has at least one member there. Overlapping curves
contribute to the same mass before selection, with no post-sampling deduplication.
"""
import numpy as np
from scipy.special import ndtri
from scipy.stats import qmc
from _population_context import curve_ids

MAX_PROBES = 2_097_152

# Artistic material proxies, in blocks. Palette/type belongs to a whole path;
# grouping and rod axis belong to a cell. These streams never drive placement.
CANDLE_COLORS = np.array([[.96, .92, .83], [.84, .80, .90], [.66, .68, .75],
                         [.99, .97, .92], [.60, .53, .72]])


def curve_materials(count, seed, params):
    from _population import migrate_parameters
    params = migrate_parameters(params)
    weights = np.array([params.get('pop_candle_weight', 82.), params.get('pop_rod_weight', 15.),
                        params.get('pop_full_block_weight', 3.)], dtype=float)
    if not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError('At least one material curve weight must be positive; weights must be finite and nonnegative')
    rod_probability = weights[1] / weights.sum()
    block_probability = weights[2] / (weights[0]+weights[2]) if weights[0]+weights[2] else 0.
    kinds = np.zeros(count, dtype=np.int8)  # candle, rod, full block
    identities = curve_ids(params, count)
    colors = np.empty((count, 3))
    for i in range(count):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 93281, int(identities[i])]))
        rod, block, tint = rng.random(3)
        kinds[i] = 1 if rod < rod_probability else (2 if block < block_probability else 0)
        colors[i] = CANDLE_COLORS[min(int(tint * len(CANDLE_COLORS)), len(CANDLE_COLORS)-1)]
    if '_curve_kinds' in params:
        forced = np.asarray(params['_curve_kinds'])
        if forced.shape != (count,) or forced.dtype.kind not in 'iu' or ((forced < 0) | (forced > 2)).any():
            raise ValueError('Selected materials must be one candle/rod/block kind per curve')
        kinds = forced.astype(np.int8)
    colors[kinds == 1] = [.98, .97, .90]
    colors[kinds == 2] = [1., .97, .82]
    return kinds, colors


def proxy_shapes(cells, kinds, seed, params):
    """Axis-aligned cell-centered cuboids; opposite rod facings look identical."""
    shapes = np.ones((len(cells), 3), dtype=np.float32)
    candle = kinds == 0
    maximum = int(params.get('pop_candle_max', 4))
    weights = np.array([.5, .27, .15, .08])[:maximum]
    groups = np.searchsorted(np.cumsum(weights / weights.sum()), cell_uniform(cells[candle], seed, 21))
    width = np.array([2., 4., 5., 6.])[groups] / 16
    shapes[candle] = np.column_stack((width, np.full(len(width), 6/16), width))
    rod = np.flatnonzero(kinds == 1)
    axes = (cell_uniform(cells[rod], seed, 22) * 3).astype(int)
    shapes[rod] = 2/16
    shapes[rod, axes] = 1.
    return shapes


def warp_positions(positions, paths, seed, params, spread=None):
    """Same generator-space transform for integration probes and line preview."""
    if not params.get('pp_warp', 0) or len(positions) == 0:
        return positions
    from _appearance import swirl_warp, coherent_warp
    if params.get('pp_flow_mode', 0) == 0:
        return swirl_warp(positions, params.get('pp_swirl_angle', 120.),
                          params.get('pp_swirl_radius', 6.))
    # A fixed source spread makes the wave transform independent of probe count
    # and lets the preview use exactly the same field as population integration.
    spread = params.get('_warp_spread', np.std(np.concatenate(paths), axis=0)) if spread is None else spread
    return coherent_warp(positions, seed, params.get('pp_warp_amount', .2),
                         params.get('pp_warp_scale', 3.), spread=spread)


def cell_uniform(cells, seed, stream=0):
    """Stable independent selection stream keyed by signed integer cell XYZ."""
    xyz = cells.astype(np.uint64)
    h = (xyz[:, 0] * np.uint64(0x9e3779b97f4a7c15)
         ^ xyz[:, 1] * np.uint64(0xbf58476d1ce4e5b9)
         ^ xyz[:, 2] * np.uint64(0x94d049bb133111eb)
         ^ np.uint64(seed) ^ np.uint64(75281 + stream))
    h = (h ^ (h >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
    h = (h ^ (h >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    h ^= h >> np.uint64(31)
    return (h >> np.uint64(11)).astype(float) * (1. / 2**53)


def unique_cells(cells):
    """Lexicographic cell union via one integer key, with a wide-domain fallback."""
    low = cells.min(axis=0)
    shape = cells.max(axis=0)-low+1
    nx, ny, nz = map(int, shape)
    if nx*ny*nz > np.iinfo(np.int64).max:
        return np.unique(cells, axis=0, return_inverse=True)
    shifted = cells-low
    keys = (shifted[:, 0]*ny+shifted[:, 1])*nz+shifted[:, 2]
    _, indices, inverse = np.unique(keys, return_index=True, return_inverse=True)
    return cells[indices], inverse


def cell_masses(paths, path_colors, seed, params, limit=1_000_000, density_source=None):
    """Estimate integrated cell masses using bounded scrambled Sobol quadrature.

    The along-curve CDF and Gaussian cross section match the continuous sampler.
    At least 128 probes per expected star and 8 per block of arc are requested;
    each path uses a power of two probes. A global budget bounds memory/time.
    Very fine grids/large spreads can have under-resolved cell masses; report the
    budget limit rather than claiming exact voxel integration.
    """
    from _population import density_distances, transverse_scatter
    from _population_field import field_profiles, sample_profile
    scale = 1. if 'pop_blocks' in params else float(params['pop_block_scale'])
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Blocks per unit must be positive in block mode')
    colors = np.asarray(path_colors, dtype=float)
    if colors.shape != (len(paths), 3) or not np.isfinite(colors).all() or ((colors < 0) | (colors > 1)).any():
        raise ValueError('Population source needs one valid RGB color per curve')
    proxies = bool(params.get('pop_block_proxies', 1))
    kinds, material_colors = curve_materials(len(paths), seed, params) if proxies else (None, None)
    identities = curve_ids(params, len(paths))
    curves, arcs, expected = [], [], []
    variation = params.get('pop_curve_density_variation', .5)
    for i, path in enumerate(paths):
        path = np.asarray(path, dtype=float)
        if path.ndim != 2 or path.shape[1] != 3 or len(path) < 2 or not np.isfinite(path).all():
            raise ValueError('Population paths must be finite (N, 3) arrays with at least two vertices')
        if (np.abs(path) > 1e6).any():
            raise ValueError('Population path exceeds coordinate limits')
        path = path[np.r_[True, np.linalg.norm(np.diff(path, axis=0), axis=1) > 1e-10]]
        arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
        factor = np.random.default_rng(np.random.SeedSequence([seed, 64281, int(identities[i])])).uniform(1-variation, 1+variation)
        curves.append(path)
        arcs.append(arc)
        density_factor = 1.
        if proxies:
            if kinds[i] == 1:
                density_factor = params.get('pop_rod_density', .4)
            elif kinds[i] == 2:
                density_factor = params.get('pop_full_block_density', .05)
        expected.append(arc[-1] * params.get('pop_density', 4.) * factor * density_factor)
    expected = np.asarray(expected)
    profiles = field_profiles(curves, arcs, seed, params, density_source)
    if profiles is not None:
        expected *= np.array([p[2] for p in profiles])
    limited = expected.sum() > limit
    if limited:
        expected *= limit / expected.sum()
    requested = np.array([max(64., 128*n, 8*a[-1]*scale) if n > 0 else 0.
                          for a, n in zip(arcs, expected)])
    probes = np.zeros(len(paths), dtype=np.int64)
    active = requested > 0
    probes[active] = np.exp2(np.ceil(np.log2(requested[active]))).astype(np.int64)
    integration_limited = probes.sum() > MAX_PROBES
    if integration_limited:
        if active.sum() > MAX_PROBES:
            raise ValueError('Too many paths for block integration')
        # Power-of-two reductions preserve balanced Sobol nets on every path.
        while probes.sum() > MAX_PROBES:
            largest = probes.max()
            probes[probes == largest] //= 2
    all_cells, all_mass, all_rgb, all_owners = [], [], [], []
    taper = params.get('pop_taper', .3)
    warp_spread = params.get('_warp_spread', np.std(np.concatenate(paths), axis=0)) if paths and params.get('pp_warp', 0) else None
    for i, (path, arc, mass, number) in enumerate(zip(curves, arcs, expected, probes)):
        if number == 0:
            continue
        identity = int(identities[i])
        quadrature_seed = int(np.random.SeedSequence([seed, 85281, identity]).generate_state(1)[0])
        uvw = qmc.Sobol(d=3, scramble=True, seed=quadrature_seed).random_base2(int(number).bit_length()-1)
        s = (density_distances(uvw[:, 0], arc[-1], seed, identity, params) if profiles is None
             else sample_profile(uvw[:, 0], profiles[i]))
        segment = np.minimum(np.searchsorted(arc, s, side='right') - 1, len(path)-2)
        delta = path[segment+1] - path[segment]
        segment_length = arc[segment+1] - arc[segment]
        center = path[segment] + delta * ((s-arc[segment])/segment_length)[:, None]
        tangent = delta / segment_length[:, None]
        reference = np.eye(3)[np.argmin(np.abs(tangent), axis=1)]
        normal = np.cross(tangent, reference)
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        binormal = np.cross(tangent, normal)
        gaussian = ndtri(np.clip(uvw[:, 1:], 1e-12, 1-1e-12))
        scatter = gaussian[:, :1]*normal + gaussian[:, 1:]*binormal
        positions = center + transverse_scatter(scatter, tangent, params)
        positions = warp_positions(positions, paths, seed, params, spread=warp_spread)
        if 'pop_blocks' not in params:
            positions *= scale  # Legacy experiment adapter only.
        if not np.isfinite(positions).all() or (np.abs(positions) >= 2**22).any():
            raise ValueError('Block coordinates too large for half-cell precision; reduce extent')
        weights = np.full(number, mass/number)
        if taper > 0:
            t = np.clip((arc[-1]-s)/(taper*arc[-1]), 0, 1)
            weights *= t*t*(3-2*t)
        # Integrate each path first so crossings can keep one actual material,
        # selected proportional to its local contribution, without color blends.
        local_cells, local_inverse = unique_cells(np.floor(positions).astype(np.int64))
        weights = np.bincount(local_inverse, weights=weights, minlength=len(local_cells))
        all_cells.append(local_cells)
        all_mass.append(weights)
        all_owners.append(np.full(len(local_cells), i, dtype=np.int32))
        color = colors[i] if params.get('pop_colors', 0) else (material_colors[i] if proxies else np.array([.72, .82, 1.]))
        all_rgb.append(weights[:, None]*color)
    stats = dict(population_limited=bool(limited), population_candidates=int(round(expected.sum())),
                 block_integration_limited=bool(integration_limited), block_probes=int(probes.sum()))
    if not all_cells:
        if proxies:
            stats['_block_kinds'] = np.empty(0, dtype=np.int8)
            stats['_block_owners'] = np.empty(0, dtype=np.int32)
        return np.empty((0, 3), dtype=np.int64), np.empty(0), np.empty((0, 3)), stats
    cells, inverse = unique_cells(np.concatenate(all_cells))
    mass = np.bincount(inverse, weights=np.concatenate(all_mass), minlength=len(cells))
    rgb_mass = np.concatenate(all_rgb)
    rgb = np.column_stack([np.bincount(inverse, weights=rgb_mass[:, j], minlength=len(cells)) for j in range(3)])
    rgb = np.divide(rgb, mass[:, None], out=np.zeros_like(rgb), where=mass[:, None] > 0)
    if proxies:
        contributions = np.concatenate(all_mass)
        owners = np.concatenate(all_owners)
        # Exponential races are categorical draws weighted by each path's mass.
        # Independent from the occupancy hash; no first-path priority at joins.
        uniforms = np.concatenate([cell_uniform(c, seed, 1000+int(identities[i])) for c, i in
                                   zip(all_cells, [j for j, n in enumerate(probes) if n])])
        scores = -np.log(np.maximum(uniforms, 1e-15)) / np.maximum(contributions, 1e-300)
        order = np.lexsort((owners, scores, inverse))
        ordered_cells = inverse[order]
        winners = order[np.r_[True, ordered_cells[1:] != ordered_cells[:-1]]]
        chosen = owners[winners]
        rgb = colors[chosen] if params.get('pop_colors', 0) else material_colors[chosen]
        stats['_block_kinds'] = kinds[chosen]
        stats['_block_owners'] = chosen
    return cells, mass, np.clip(rgb, 0, 1), stats


def populate_blocks(paths, path_colors, seed, params, limit=1_000_000, density_source=None):
    if params.get('pp_merge', 0) or params.get('pp_curves', 0):
        raise ValueError('Block sampling requires Merge dense stars and Align sparse stars off; these edit continuous stars')
    cells, mass, colors, stats = cell_masses(paths, path_colors, seed, params, limit, density_source=density_source)
    probability = -np.expm1(-mass)
    selected = np.flatnonzero(cell_uniform(cells, seed) < probability)
    if len(selected) > limit:
        priority = cell_uniform(cells[selected], seed, stream=1)
        selected = np.sort(selected[np.argpartition(priority, limit-1)[:limit]])
        stats['population_limited'] = True
    stats.update(block_candidate_cells=len(cells), block_expected_occupied=float(probability.sum()))
    kinds = stats.pop('_block_kinds', None)
    owners = stats.pop('_block_owners', None)
    if kinds is not None:
        stats['_block_shapes'] = proxy_shapes(cells[selected], kinds[selected], seed, params)
        stats['_block_kinds'] = kinds[selected]
        stats['_fade_groups'] = curve_ids(params, len(paths))[owners[selected]]
    return ((cells[selected].astype(np.float32)+.5, colors[selected].astype(np.float32),
             np.ones(len(selected), dtype=np.float32)), stats)
