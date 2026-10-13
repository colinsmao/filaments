"""Select original density-grown curves by their marginal corridor coverage."""
from dataclasses import dataclass
from functools import lru_cache
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from _density_field import build_field
from _grid_density_curves import block_seeds
from _field_curves import grow_field
from _block_population import cell_uniform
from _stable_density_curves import sample_support


@dataclass(frozen=True, eq=False)
class CurvePool:
    paths: tuple
    owners: np.ndarray
    density: np.ndarray
    half: np.ndarray
    short_mask: np.ndarray | None = None


def short_candidates(cells, seed, fraction):
    """Stable length-class lottery, independent of seed acceptance and budget."""
    return cell_uniform(cells, seed, 82422) < fraction


@lru_cache(maxsize=1)
def build_pool(seed, field_items, growth_items, max_candidates=None):
    """One cached pool; selection/population edits do not retrace the field."""
    field, p = dict(field_items), dict(growth_items)
    resolution = field.pop('field_resolution')
    density, _, half = build_field(seed, resolution=resolution, **field)
    cells = block_seeds(density, half, seed, p['seed_rate'], p['seed_density_power'],
                        p['seed_xz'], seed_y_pos=p['seed_y_pos'], seed_y_neg=p['seed_y_neg'])
    if max_candidates is not None and len(cells) > max_candidates:
        raise ValueError(f'Population selection supports {max_candidates} candidate seeds; reduce candidate seed rate')
    def grow(roots, length, short=False):
        response = p.get('short_growth_response', p['growth_response']) if short else p['growth_response']
        wander = p.get('short_growth_wander', p['growth_wander']) if short else p['growth_wander']
        return grow_field(density, half, roots, seed, length, p['length_variation'],
                          response, p['growth_pull'], wander, joining=False)

    fraction = p.get('short_curve_fraction', 0.)
    if fraction == 0.:
        # Older experiments and the disabled mixture retain their exact path order.
        paths, owners = grow(cells, p['strand_length'])
    else:
        short = short_candidates(cells, seed, fraction)
        paths, owner_batches = [], []
        # Separate batches avoid allocating long-curve history for short roots.
        for mask, length, is_short in ((~short, p['strand_length'], False), (short, p['short_curve_length'], True)):
            batch_paths, batch_owners = grow(cells[mask], length, is_short)
            if batch_paths:
                paths.extend(batch_paths)
                owner_batches.append(batch_owners)
        owners = np.concatenate(owner_batches) if owner_batches else np.empty((0, 3), dtype=np.int64)
        root_order = {tuple(cell): i for i, cell in enumerate(cells)}
        order = sorted(range(len(paths)), key=lambda i: root_order[tuple(owners[i])])
        paths, owners = [paths[i] for i in order], owners[order]
    short_mask = short_candidates(owners, seed, fraction)
    for a in [*paths, owners, density, half, short_mask]:
        a.setflags(write=False)
    return CurvePool(tuple(paths), owners, density, half, short_mask)


@dataclass(frozen=True)
class Coverage:
    matrix: csr_matrix
    points: np.ndarray
    owner: np.ndarray
    arc: np.ndarray
    lengths: np.ndarray


@lru_cache(maxsize=1)
def build_coverage(pool, radius=8., angle=30.):
    """Candidate-to-probe coverage, with exact point-to-segment distances.

    Equal arc probes are <= radius/2 apart. Crossing directions do not cover
    one another. Each distinct candidate counts once at each probe, independent
    of tessellation or the number of its nearby segments. No nearest-K cutoff.
    """
    if radius <= 0 or not np.isfinite(radius) or not 0 <= angle <= 90:
        raise ValueError('Selection reach must be positive and angle in [0,90]')
    starts, deltas, segment_owners, points, tangents, owners, arcs, lengths = [], [], [], [], [], [], [], []
    for i, path in enumerate(pool.paths):
        delta = np.diff(path, axis=0)
        length = np.linalg.norm(delta, axis=1)
        keep = length > 1e-10
        start, delta, length = path[:-1][keep], delta[keep], length[keep]
        distance = np.r_[0., np.cumsum(length)]
        n = max(2, int(np.ceil(distance[-1]/(radius/2))))
        lengths.append(distance[-1])
        if sum(len(a) for a in owners)+n > 250_000:
            raise ValueError('Selection exceeds 250,000 arc probes; increase overlap reach or reduce candidate rate/length')
        s = (np.arange(n)+.5)*distance[-1]/n
        segment = np.minimum(np.searchsorted(distance, s, side='right')-1, len(length)-1)
        direction = delta[segment]/length[segment, None]
        points.append(start[segment]+direction*(s-distance[segment])[:, None])
        tangents.append(direction)
        owners.append(np.full(n, i, dtype=int))
        arcs.append(np.full(n, distance[-1]/n))
        starts.append(start)
        deltas.append(delta)
        segment_owners.append(np.full(len(delta), i, dtype=int))
    if not points:
        return Coverage(csr_matrix((0, 0)), np.empty((0,3)), np.empty(0,dtype=int), np.empty(0), np.empty(0))
    start, delta, segment_owner, q, tangent, owner, arc = map(np.concatenate,
        (starts, deltas, segment_owners, points, tangents, owners, arcs))
    length2 = np.sum(delta*delta, axis=1)
    segment_tangent = delta/np.sqrt(length2)[:, None]
    tree = cKDTree(start+delta*.5)
    reach = radius+.5*np.sqrt(length2.max())
    cosine = np.cos(np.deg2rad(angle))-1e-12
    # Preflight bounds memory before query_ball_point materializes pair lists.
    query_count = tree.query_ball_point(q, reach, return_length=True)
    if int(query_count.sum()) > 20_000_000:
        raise ValueError('Selection exceeds 20 million nearby segment probes; reduce candidate rate/length or overlap reach')
    rows, cols = [owner], [np.arange(len(q))]  # Every path covers its own samples.
    for low in range(0, len(q), 256):
        hits = tree.query_ball_point(q[low:low+256], reach)
        counts = np.fromiter((len(a) for a in hits), dtype=int)
        if not counts.sum():
            continue
        probe = np.repeat(np.arange(low, min(low+256, len(q))), counts)
        segment = np.concatenate(hits)
        aligned = (np.abs(np.sum(tangent[probe]*segment_tangent[segment], axis=1)) >= cosine)
        aligned &= owner[probe] != segment_owner[segment]
        probe, segment = probe[aligned], segment[aligned]
        offset = q[probe]-start[segment]
        fraction = np.clip(np.sum(offset*delta[segment], axis=1)/length2[segment], 0, 1)
        close = np.sum((offset-fraction[:, None]*delta[segment])**2, axis=1) <= radius*radius
        rows.append(segment_owner[segment[close]])
        cols.append(probe[close])
    matrix = csr_matrix((np.ones(sum(len(a) for a in rows), dtype=bool),
                         (np.concatenate(rows), np.concatenate(cols))), shape=(len(pool.paths), len(q)))
    matrix.sum_duplicates()
    return Coverage(matrix, q, owner, arc, np.asarray(lengths))


def select_curves(pool, coverage, fraction=.95, length_cost=.5, density_power=0., report=None):
    """Greedy weighted set cover. Return only original whole-path indices.

    Divide each sample's arc weight by its number of candidate representatives,
    so a ten-curve bundle does not have ten times a unique branch's importance.
    Select the greatest uncovered weight per length**cost until the requested
    corridor coverage is reached. This is a geometric tolerance, not a promise
    of topological connectivity. Density weighting is optional and defaults off.
    """
    if not 0 < fraction <= 1 or not 0 <= length_cost <= 1 or not 0 <= density_power <= 3:
        raise ValueError('Invalid curve selection coverage, length cost or density influence')
    matrix = coverage.matrix
    if not len(pool.paths):
        return np.empty(0, dtype=int)
    multiplicity = np.asarray(matrix.sum(axis=0)).ravel()
    weight = coverage.arc/np.maximum(multiplicity, 1)
    if density_power > 0:
        sampled = sample_support(pool.density, coverage.points, pool.half)
        # A small floor keeps connecting/unique low-density routes eligible.
        weight *= .01+.99*(np.maximum(sampled, 0)/max(float(pool.density.max()), 1e-30))**density_power
    total = weight.sum()
    residual = weight.copy()
    gains = np.asarray(matrix@weight).ravel()
    cost = np.maximum(coverage.lengths, 1e-10)**length_cost
    columns = matrix.tocsc()
    chosen = []
    covered = 0.
    while covered < fraction*total-1e-10 and len(chosen) < len(pool.paths):
        score = gains/cost
        score[chosen] = -np.inf
        best = int(np.argmax(score))
        if gains[best] <= 1e-12:
            break
        chosen.append(best)
        a, b = matrix.indptr[best:best+2]
        targets = matrix.indices[a:b]
        targets = targets[residual[targets] > 0]
        added = residual[targets]
        covered += added.sum()
        gains = np.maximum(gains-np.asarray(columns[:, targets]@added).ravel(), 0)
        residual[targets] = 0
    if report is not None:
        report.update(candidates=len(pool.paths), selected=len(chosen), probes=len(weight),
                      coverage=float(covered/total) if total else 1.,
                      input_length=float(coverage.lengths.sum()), output_length=float(coverage.lengths[chosen].sum()))
    return np.sort(chosen)
