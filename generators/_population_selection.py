"""Cached population sketches and incremental candle/rod selection.

No star occupancy draws or light propagation occur in the selector. Sparse
trilinear deposits give continuous local interactions at a chosen spatial scale.
"""
from dataclasses import dataclass
from functools import lru_cache
import time
import numpy as np
from scipy.sparse import csr_matrix
from scipy.special import ndtri
from scipy.spatial import cKDTree
from scipy.stats import qmc
from _block_population import cell_uniform, unique_cells, warp_positions
from _population import density_distances, transverse_scatter
from _population_field import field_profiles, sample_profile
from _postprocess import axis_fade_settings, edge_envelope
from _stable_density_curves import sample_support


# Material colors, lighting, rod intensity and score controls do not change the
# candle sketch. Keep them out of its cache key, even though the worker sends all.
SKETCH_KEYS = ('pop_density', 'pop_curve_density_variation', 'pop_source_density',
               'pop_clumping', 'pop_clump_scale', 'pop_density_octaves', 'pop_density_roughness',
               'pop_spread_xz', 'pop_spread_y', 'pop_taper', 'pp_warp', 'pp_flow_mode',
               'pp_swirl_angle', 'pp_swirl_radius', 'pp_warp_amount', 'pp_warp_scale',
               'fade_xz', 'fade_xz_width', 'fade_y_enabled', 'fade_y_pos_width', 'fade_y_neg_width')


def sketch_parameters(params):
    return tuple((key, params[key]) for key in SKETCH_KEYS if key in params)


@dataclass(frozen=True, eq=False)
class Sketch:
    points: np.ndarray
    weights: np.ndarray
    owners: np.ndarray
    identities: np.ndarray
    profiles: object
    warp_spread: np.ndarray
    mass: np.ndarray


@lru_cache(maxsize=1)
def build_sketch(pool, seed, parameter_items, samples=128):
    p = dict(parameter_items)
    count = len(pool.paths)
    number = 2**int(np.ceil(np.log2(max(32, samples))))
    if count > 2048 or count*number > 524288:
        raise ValueError('Population selection supports 2048 candidates and 524288 sketch samples; reduce seed rate or samples per curve')
    if not count:
        raise ValueError('Population selection requires candidate curves')
    identities = (cell_uniform(pool.owners, seed, 92173)*2**53).astype(np.int64)
    arcs = [np.r_[0., np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))] for path in pool.paths]
    p['_curve_ids'] = identities
    profiles = field_profiles(pool.paths, arcs, seed, p, (pool.density, pool.half))
    spread = np.std(np.concatenate(pool.paths), axis=0)
    all_points, all_weights = [], []
    # Powers of two preserve balanced Sobol nets. Same samples are reused for
    # both material roles; a rod changes their expected mass, not the path.
    for i, (path, arc) in enumerate(zip(pool.paths, arcs)):
        identity = int(identities[i])
        variation = p.get('pop_curve_density_variation', .5)
        factor = np.random.default_rng(np.random.SeedSequence([seed, 64281, identity])).uniform(1-variation, 1+variation)
        mass = arc[-1]*p.get('pop_density', .25)*factor
        if profiles is not None:
            mass *= profiles[i][2]
        quadrature_seed = int(np.random.SeedSequence([seed, 85281, identity]).generate_state(1)[0])
        uvw = qmc.Sobol(3, scramble=True, seed=quadrature_seed).random_base2(number.bit_length()-1)
        s = (density_distances(uvw[:, 0], arc[-1], seed, identity, p) if profiles is None
             else sample_profile(uvw[:, 0], profiles[i]))
        segment = np.minimum(np.searchsorted(arc, s, side='right')-1, len(path)-2)
        delta = path[segment+1]-path[segment]
        tangent = delta/(arc[segment+1]-arc[segment])[:, None]
        center = path[segment]+tangent*(s-arc[segment])[:, None]
        reference = np.eye(3)[np.argmin(np.abs(tangent), axis=1)]
        normal = np.cross(tangent, reference)
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        binormal = np.cross(tangent, normal)
        gaussian = ndtri(np.clip(uvw[:, 1:], 1e-12, 1-1e-12))
        points = center+transverse_scatter(gaussian[:, :1]*normal+gaussian[:, 1:]*binormal, tangent, p)
        points = warp_positions(points, pool.paths, seed, p, spread=spread)
        weights = np.full(number, mass/number)
        taper = p.get('pop_taper', 0.)
        if taper > 0:
            t = np.clip((arc[-1]-s)/(taper*arc[-1]), 0, 1)
            weights *= t*t*(3-2*t)
        survival = np.ones(number)
        normalized = points/pool.half
        for axis, axes, enabled, width, _ in axis_fade_settings(p):
            if enabled and width > 0:
                radius = (normalized[:, 1] if axis == 'y_pos' else -normalized[:, 1]
                          if axis == 'y_neg' else np.max(np.abs(normalized[:, axes]), axis=1))
                survival = np.minimum(survival, edge_envelope(radius, width))
        # Expected edge survival; density-suppression and correlated final draws
        # stay in the shared postprocessor and can differ from this approximation.
        weights *= survival
        all_points.append(points)
        all_weights.append(weights)
    weights = np.concatenate(all_weights)
    return Sketch(np.concatenate(all_points), weights, np.repeat(np.arange(count), number),
                  identities, profiles, spread, weights.reshape(count, number).sum(axis=1))


@lru_cache(maxsize=2)
def rasterize(sketch, spacing):
    """Compact per-curve mass footprints; no full-domain voxel allocation."""
    if spacing <= 0 or not np.isfinite(spacing):
        raise ValueError('Interaction scale must be positive')
    xyz = sketch.points/spacing
    base = np.floor(xyz).astype(np.int64)
    fraction = xyz-base
    cells, values = [], []
    for offset in np.ndindex(2, 2, 2):
        offset = np.asarray(offset)
        cells.append(base+offset)
        values.append(sketch.weights*np.prod(np.where(offset, fraction, 1-fraction), axis=1))
    cells, inverse = unique_cells(np.concatenate(cells))
    matrix = csr_matrix((np.concatenate(values), (np.tile(sketch.owners, 8), inverse)),
                        shape=(len(sketch.mass), len(cells)))
    matrix.eliminate_zeros()
    return matrix, cells.astype(float)*spacing


def gram(matrix, weights):
    """Sparse shared-footprint interactions, worst-case quadratic in curves."""
    result = (matrix.multiply(weights)@matrix.T).tocsr()
    result.eliminate_zeros()
    if result.nnz > 2_000_000:
        raise ValueError('More than 2 million curve interactions; reduce seed rate or interaction scales')
    return result


@lru_cache(maxsize=1)
def population_proximity(sketch, reach):
    """exp(-(closest sample distance/reach)^2) for nearby curve pairs.

    Positive-mass population samples only. AABB pruning and batched nearest
    queries avoid enumerating sample pairs. Beyond 4*reach the affinity is
    treated as zero (at most exp(-16), about 1.13e-7). No self edges.
    """
    if reach <= 0 or not np.isfinite(reach):
        raise ValueError('Isolation distance must be positive')
    n = len(sketch.mass)
    active = np.flatnonzero(sketch.weights > 0)
    active = active[np.argsort(sketch.owners[active], kind='stable')]
    counts = np.bincount(sketch.owners[active], minlength=n)
    offsets = np.r_[0, np.cumsum(counts)]
    points = sketch.points[active]
    groups = [points[offsets[i]:offsets[i+1]] for i in range(n)]
    lower = np.array([p.min(axis=0) if len(p) else np.full(3, np.inf) for p in groups])
    upper = np.array([p.max(axis=0) if len(p) else np.full(3, -np.inf) for p in groups])
    rows, columns, values = [], [], []
    edges = 0
    cutoff = 4*reach
    for i in range(n):
        if not counts[i]:
            continue
        gap = np.maximum(0., np.maximum(lower[i]-upper, lower-upper[i]))
        neighbors = np.flatnonzero((np.arange(n) > i) & (counts > 0) &
                                   (np.sum(gap*gap, axis=1) < cutoff*cutoff))
        if not len(neighbors):
            continue
        samples = np.concatenate([groups[j] for j in neighbors])
        distance, _ = cKDTree(groups[i]).query(samples, k=1, distance_upper_bound=cutoff)
        closest = np.minimum.reduceat(distance, np.r_[0, np.cumsum(counts[neighbors])[:-1]])
        keep = np.isfinite(closest)
        neighbors, closest = neighbors[keep], closest[keep]
        edges += len(neighbors)
        if edges > 1_000_000:
            raise ValueError('More than 2 million isolation interactions; reduce seed rate or isolation distance')
        rows.extend([np.full(len(neighbors), i), neighbors])
        columns.extend([neighbors, np.full(len(neighbors), i)])
        affinity = np.exp(-(closest/reach)**2)
        values.extend([affinity, affinity])
    if not edges:
        return csr_matrix((n, n))
    return csr_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(columns))), shape=(n, n))


def greedy(candle_pairs, candle_initial, rod_pairs, mass, rod_ratio, attraction, repulsion,
           isolation_pairs=None, isolation_strength=0., rod_penalty=None):
    """Normalized marginal scores; selected curves have exactly one role."""
    n = len(mass)
    candle = candle_initial.copy()
    rod = .5*repulsion*rod_ratio*rod_pairs.diagonal()
    valid = mass > 1e-12
    available = valid.copy()
    denominator = np.maximum(mass, 1e-12)
    proximity = np.zeros(n)
    penalize = isolation_strength > 0 and isolation_pairs is not None
    chosen, roles, scores = [], [], []
    for _ in range(n):
        cscore = candle/denominator
        if penalize and chosen:
            # A single nearby approach anchors a candidate. Extra contacts do
            # not accumulate a bonus, and rods do not anchor candle islands.
            cscore = cscore + isolation_strength*(1-proximity)
        cscore = np.where(available, cscore, np.inf)
        rscore = rod/denominator
        if rod_penalty is not None:
            # A role preference in the same per-mass units as the scores.
            # It neither rewards candles nor bypasses their density objective.
            rscore = rscore + rod_penalty
        rscore = np.where(available & (rod_ratio > 0), rscore, np.inf)
        ci, ri = int(np.argmin(cscore)), int(np.argmin(rscore))
        kind = int(rscore[ri] < cscore[ci])
        best = ri if kind else ci
        score = rscore[best] if kind else cscore[best]
        if score >= -1e-10:
            break
        chosen.append(best); roles.append(kind); scores.append(float(score))
        available[best] = False
        if kind == 0:
            a, b = candle_pairs.indptr[best:best+2]
            candle[candle_pairs.indices[a:b]] += candle_pairs.data[a:b]
            if penalize:
                a, b = isolation_pairs.indptr[best:best+2]
                neighbors = isolation_pairs.indices[a:b]
                proximity[neighbors] = np.maximum(proximity[neighbors], isolation_pairs.data[a:b])
        a, b = rod_pairs.indptr[best:best+2]
        rod[rod_pairs.indices[a:b]] += rod_pairs.data[a:b]*(repulsion*rod_ratio if kind else -attraction)
    order = np.argsort(chosen)
    return np.asarray(chosen, dtype=int)[order], np.asarray(roles, dtype=np.int8)[order], scores


def select_population(pool, sketch, params):
    started = time.perf_counter()
    p = params
    spacing = p['select_scale']
    footprint, nodes = rasterize(sketch, spacing)
    support = sample_support(pool.density, nodes, pool.half)/max(float(pool.density.max()), 1e-30)
    target_peak = max(p['pop_density'], 1e-12)*spacing*p['select_budget']
    target = target_peak*np.maximum(support, 0)**p['select_density']
    weight = 1/(target+.02*target_peak)
    pairs = gram(footprint, weight)
    initial = .5*pairs.diagonal()-np.asarray(footprint@(target*weight)).ravel()
    rods_enabled = p['select_rods'] and p.get('pop_blocks', 0) and p.get('pop_block_proxies', 0)
    rod_ratio = p.get('pop_rod_density', .4) if rods_enabled else 0.
    rod_pairs = csr_matrix(pairs.shape)
    if rod_ratio > 0 and p['select_enabled']:
        rod_footprint, _ = rasterize(sketch, p['select_rod_scale'])
        rod_pairs = gram(rod_footprint, 1/max(p['pop_density']*p['select_rod_scale'], 1e-12))
    isolation_pairs = None
    if p['select_enabled']:
        isolation_strength = p.get('select_isolation', 0.)
        isolation_pairs = (population_proximity(sketch, p.get('select_isolation_distance', 8.))
                           if isolation_strength > 0 else None)
        rod_penalty = (pool.short_mask*p.get('select_short_rod_penalty', 0.)
                       if pool.short_mask is not None else None)
        indices, roles, scores = greedy(pairs, initial, rod_pairs, sketch.mass, rod_ratio,
                                        p['select_rod_attraction'], p['select_rod_repulsion'],
                                        isolation_pairs, isolation_strength, rod_penalty)
    else:
        indices = np.flatnonzero(sketch.mass > 1e-12)
        roles, scores = np.zeros(len(indices), dtype=np.int8), []
    if not len(indices):
        raise ValueError('No curve improves the density target; raise Density budget or reduce Density contrast')
    candle_ids = indices[roles == 0]
    modeled = np.asarray(footprint[candle_ids].sum(axis=0)).ravel()
    error0 = float(np.sum(weight*target*target))
    error1 = float(np.sum(weight*(modeled-target)**2))
    stats = dict(candidates=len(pool.paths), candles=int((roles == 0).sum()), rods=int((roles == 1).sum()),
                 sketch_samples=len(sketch.weights), interactions=pairs.nnz+rod_pairs.nnz,
                 expected_candles=float(sketch.mass[candle_ids].sum()),
                 expected_rods=float(sketch.mass[indices[roles == 1]].sum()*rod_ratio),
                 density_error_reduction=1-error1/max(error0, 1e-30),
                 selection_ms=1000*(time.perf_counter()-started))
    if p['select_enabled'] and isolation_pairs is not None:
        stats['isolation_interactions'] = isolation_pairs.nnz
    return indices, roles, stats
