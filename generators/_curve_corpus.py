"""Local octave-noise curves, built without any density input.

Grid cells and variant IDs determine every random draw. Selection never moves
vertices. The cache holds only geometry, so density edits can reuse it.
"""
from functools import lru_cache
from dataclasses import dataclass
import heapq
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.sparse import csr_matrix
from _block_population import cell_uniform
from _noise import fractal_noise

MAX_CANDIDATES = 65536
MAX_SEGMENTS = 4_000_000
MAX_PROBES = 8_000_000


@dataclass(frozen=True)
class NoiseCurves:
    """Evaluable raw curves, with normalized t in [-.5, .5].

    Sampling/clipping produces the polylines consumed by the current shared
    population stage. The continuous definition remains available for future
    direct quadrature, tangents, interval selection and material assignment.
    """
    centers: np.ndarray
    directions: np.ndarray
    sides: np.ndarray
    ups: np.ndarray
    spans: np.ndarray
    offsets: np.ndarray
    identities: np.ndarray
    half: np.ndarray
    steps: int
    seed: int
    wavelength: float
    bend: float
    vertical: float
    octaves: int
    roughness: float

    def evaluate(self, t, indices=None):
        """Vectorized P(t); t may be shared 1D or one row per selected curve."""
        use = slice(None) if indices is None else np.atleast_1d(indices)
        s = self.spans[use, None]*np.atleast_1d(np.asarray(t, dtype=float))
        points = self.centers[use, None]+s[:, :, None]*self.directions[use, None]
        if self.bend > 0 and len(points):
            offsets = self.offsets[use]
            q = np.broadcast_to(offsets[:, None], points.shape).copy()
            q[:, :, 0] += s/self.wavelength
            for stream, basis, amount in ((22003, self.sides[use], self.bend*self.wavelength),
                                           (22007, self.ups[use], self.bend*self.wavelength*self.vertical)):
                if amount == 0:
                    continue
                noise_seed = np.random.SeedSequence([self.seed, stream])
                noise = fractal_noise(q.reshape(-1, 3), noise_seed, 1., self.octaves,
                                       self.roughness).reshape(s.shape).astype(float)
                origin = fractal_noise(offsets, noise_seed, 1., self.octaves, self.roughness)
                noise -= origin[:, None]
                points += (amount*noise)[:, :, None]*basis[:, None]
        return points


def _clip_from_middle(points, half):
    """Stop both halves at their first box exit; pad with the exact endpoint."""
    points = points.copy()
    middle = points.shape[1]//2
    for order in (np.arange(middle, points.shape[1]), np.arange(middle, -1, -1)):
        part = points[:, order].copy()
        outside = np.any(np.abs(part) > half, axis=2)
        hit = outside.any(axis=1)
        rows = np.flatnonzero(hit)
        first = outside[rows].argmax(axis=1)
        a, b = part[rows, first-1], part[rows, first]
        delta = b-a
        wall = np.where(delta > 0, half, -half)
        fraction = np.divide(wall-a, delta, out=np.full_like(delta, np.inf), where=delta != 0)
        end = a + np.clip(fraction.min(axis=1), 0, 1)[:, None]*delta
        end = np.clip(end, -half, half)
        for i, row in enumerate(rows):
            part[row, first[i]:] = end[i]
        points[:, order] = part
    return points


@lru_cache(maxsize=1)
def build_definition(half_tuple, corpus_seed=173, cell_size=64., per_cell=16,
                 span=128., bend=.8, vertical=.15, axis_bias=0.,
                 seed_xz=1., seed_y_pos=1., seed_y_neg=1.,
                 wavelength=96., octaves=3, roughness=.25):
    """Create an immutable, density-independent parametric curve family.

    p(s) = anchor + s*heading + bend*wavelength*(N(s)-N(0)) in the
    two transverse directions. N is independently seeded compiled Perlin fBm.
    Span is baseline travel, not final arc length. The forward projection is
    strictly increasing, preventing cusps/loops while noise bends stay smooth.
    """
    half = np.asarray(half_tuple, dtype=float)
    if (half.shape != (3,) or not np.isfinite(half).all() or np.any(half <= 0)
            or not np.isfinite([cell_size, span, bend, vertical, axis_bias, wavelength, roughness]).all()
            or cell_size <= 0 or span <= 0 or not 0 <= bend <= 3
            or not 0 <= vertical <= 1 or not 0 <= axis_bias <= 1
            or not 1 <= per_cell <= 128 or wavelength <= 0
            or not 1 <= octaves <= 5 or not 0 <= roughness <= .75):
        raise ValueError('Invalid independent curve corpus bounds or controls')
    low = -half*np.array([seed_xz, seed_y_neg, seed_xz])
    high = half*np.array([seed_xz, seed_y_pos, seed_xz])
    first, stop = np.floor(low/cell_size).astype(int), np.ceil(high/cell_size).astype(int)
    shape = np.maximum(stop-first, 0)
    candidates = int(np.prod(shape))*int(per_cell)
    # At least 12 samples per smallest active octave; even subdivisions include
    # the exact anchor. This depends only on corpus controls, never density.
    finest = wavelength/2**(int(octaves)-1 if roughness > 0 and bend > 0 else 0)
    step = min(4., finest/12)
    steps = max(8, int(np.ceil(1.35*span/step/2))*2)
    if candidates > MAX_CANDIDATES or candidates*steps > MAX_SEGMENTS:
        raise ValueError('Curve corpus exceeds 65,536 candidates or 4 million segments; increase grid spacing/wavelength or reduce copies/span/octaves')
    cells = np.indices(tuple(shape)).reshape(3, -1).T+first
    all_centers, all_directions, all_sides, all_ups, all_lengths, all_offsets, all_ids = [], [], [], [], [], [], []
    for variant in range(int(per_cell)):
        draws = np.column_stack([cell_uniform(cells, int(corpus_seed), 150001+32*variant+j) for j in range(10)])
        center = (cells+draws[:, :3])*cell_size
        valid = np.all((center >= low) & (center <= high), axis=1)
        center, r, key = center[valid], draws[valid], cells[valid]
        angle = 2*np.pi*r[:, 3]
        cardinal = np.round(angle/(np.pi/2))*(np.pi/2)
        angle = (1-axis_bias)*angle+axis_bias*cardinal
        direction = np.column_stack((np.cos(angle), vertical*(2*r[:, 4]-1), np.sin(angle)))
        direction /= np.linalg.norm(direction, axis=1)[:, None]
        side = np.column_stack((-np.sin(angle), np.zeros(len(angle)), np.cos(angle)))
        up = np.cross(side, direction)
        length = span*(.65+.7*r[:, 5])
        all_centers.append(center)
        all_directions.append(direction)
        all_sides.append(side)
        all_ups.append(up)
        all_lengths.append(length)
        all_offsets.append(r[:, 6:9]*128)
        all_ids.append(np.column_stack((key, np.full(len(key), variant))))
    identities = np.concatenate(all_ids)
    centers, direction = np.concatenate(all_centers), np.concatenate(all_directions)
    arrays = (centers, direction, np.concatenate(all_sides), np.concatenate(all_ups),
              np.concatenate(all_lengths), np.concatenate(all_offsets), identities, half)
    for a in arrays:
        a.setflags(write=False)
    return NoiseCurves(*arrays, steps, corpus_seed, wavelength, bend, vertical, int(octaves), roughness)


@lru_cache(maxsize=1)
def build_corpus(half_tuple, corpus_seed=173, cell_size=64., per_cell=16,
                 span=128., bend=.8, vertical=.15, axis_bias=0.,
                 seed_xz=1., seed_y_pos=1., seed_y_neg=1.,
                 wavelength=96., octaves=3, roughness=.25):
    """Cache a read-only preview/arc table from the evaluable curve definition."""
    curves = build_definition(half_tuple, corpus_seed, cell_size, per_cell, span, bend,
        vertical, axis_bias, seed_xz, seed_y_pos, seed_y_neg, wavelength, octaves, roughness)
    points = curves.evaluate(np.linspace(-.5, .5, curves.steps+1))
    points = _clip_from_middle(points, curves.half)
    points.setflags(write=False)
    return points, curves.identities


def quadrature(points, half, grid_shape):
    """Midpoint samples with at least two probes per crossed density cell."""
    delta = np.diff(points, axis=1)
    length = np.linalg.norm(delta, axis=2)
    cell = 2*np.asarray(half)/(np.asarray(grid_shape)-1)
    subdivisions = np.ceil(2*np.max(np.abs(delta/cell), axis=2)).astype(int)
    subdivisions[length <= 1e-10] = 0
    subdivisions[(length > 1e-10) & (subdivisions == 0)] = 1
    n = subdivisions.ravel()
    total = int(n.sum())
    if total > MAX_PROBES:
        raise ValueError('Curve scoring exceeds 8 million probes; reduce corpus size/span or field resolution')
    segment = np.repeat(np.arange(len(n)), n)
    offset = np.arange(total)-np.repeat(np.cumsum(n)-n, n)
    fraction = (offset+.5)/n[segment]
    q = points[:, :-1].reshape(-1, 3)[segment]+delta.reshape(-1, 3)[segment]*fraction[:, None]
    owner = segment//length.shape[1]
    weight = length.ravel()[segment]/n[segment]
    return q, owner, weight, length.sum(axis=1)


def score_corpus(points, density, half, power=.5, continuity=1.):
    """Arc-weighted mean support times an optional effective-support fraction.

    For w=rho**power, effective support is mean(w)**2/mean(w**2).
    A brief bright crossing loses against sustained support at equal mean.
    Continuity zero is the plain mean-density baseline. No geometry is edited.
    """
    if not np.isfinite(density).all() or np.any(density < 0):
        raise ValueError('Selection density must be finite and nonnegative')
    q, owner, arc, lengths = quadrature(points, half, density.shape)
    coords = ((q/half+1)*.5*(np.asarray(density.shape)-1)).T
    rho = map_coordinates(density, coords, order=1, mode='nearest')
    peak = max(float(np.max(density)), 1e-30)
    w = np.maximum(rho/peak, 0.)**power
    total = np.bincount(owner, arc*w, minlength=len(points))
    square = np.bincount(owner, arc*w*w, minlength=len(points))
    mean = total/np.maximum(lengths, 1e-30)
    support = np.clip(total*total/np.maximum(lengths*square, 1e-30), 0, 1)
    score = mean*support**continuity
    return score, dict(mean=mean, support=support, lengths=lengths,
                       points=q, owner=owner, arc=arc, density=rho)


def footprints(samples, half, size):
    """Sparse arc length in coarse cells, in units of one cell traversal."""
    shape = np.maximum(1, np.ceil(2*np.asarray(half)/size).astype(int))
    xyz = np.minimum(((samples['points']+half)/size).astype(int), shape-1)
    key = np.ravel_multi_index(xyz.T, shape)
    # Compress touched cells rather than allocating the entire bounding volume.
    _, column = np.unique(key, return_inverse=True)
    return csr_matrix((samples['arc']/size, (samples['owner'], column)),
                      shape=(len(samples['lengths']), int(column.max())+1))


def select_candidates(scores, identities, count, seed, binding=1., diversity=0., footprint=None):
    """Seeded weighted sampling without replacement; optionally discourage load.

    The exponential race is nested as count increases. Binding=0 is uniform,
    including zero-density candidates. Lazy heap updates apply a monotone local
    overlap penalty without an all-pairs distance search or moving any curve.
    """
    if not len(scores) or count <= 0:
        return np.empty(0, dtype=int)
    score = np.asarray(scores, dtype=float)
    if not np.isfinite(score).all() or np.any(score < 0) or binding < 0 or diversity < 0:
        raise ValueError('Invalid curve selection score or strength')
    weights = np.ones_like(score) if binding == 0 else (score/max(float(score.max()), 1e-30))**binding
    uniforms = np.empty(len(score))
    for variant in np.unique(identities[:, 3]):
        use = identities[:, 3] == variant
        uniforms[use] = cell_uniform(identities[use, :3], seed, 190001+int(variant))
    race = -np.log(np.maximum(uniforms, 1e-15))
    priority = np.divide(race, weights, out=np.full_like(race, np.inf), where=weights > 0)
    eligible = np.flatnonzero(np.isfinite(priority))
    count = min(int(count), len(eligible))
    if diversity <= 0:
        return np.sort(eligible[np.argsort(priority[eligible], kind='stable')[:count]])
    if footprint is None or footprint.shape[0] != len(score):
        raise ValueError('Overlap selection needs candidate footprints')
    load = np.zeros(footprint.shape[1])
    heap = [(priority[i], int(i)) for i in eligible]
    heapq.heapify(heap)
    chosen = []
    while heap and len(chosen) < count:
        _, i = heapq.heappop(heap)
        a, b = footprint.indptr[i:i+2]
        cells, mass = footprint.indices[a:b], footprint.data[a:b]
        penalty = np.sum(mass/(1+load[cells])**diversity)/max(float(mass.sum()), 1e-30)
        revised = priority[i]/max(penalty, 1e-30)
        if heap and revised > heap[0][0]*(1+1e-12):
            heapq.heappush(heap, (revised, i))
        else:
            chosen.append(i)
            load[cells] += mass
    return np.sort(chosen)


def unpack_paths(points, indices):
    return [p[np.r_[True, np.linalg.norm(np.diff(p, axis=0), axis=1) > 1e-10]].copy()
            for p in points[indices]]
