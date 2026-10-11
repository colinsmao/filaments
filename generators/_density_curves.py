"""Finite stochastic strands guided by derivatives of the actual density."""
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.spatial import cKDTree
from _noise import sample_density
from _guided_walk import VectorNoise, unit
from _curve_coverage import CurveCoverage


class StrandContacts:
    """Nearest aligned deposited segment from a different two-way strand."""
    def __init__(self, paths, families=None):
        segments = [(i//2, np.asarray(p)) for i, p in enumerate(paths) if len(p) > 1]
        self.tree = None
        if not segments:
            return
        start = np.concatenate([p[:-1] for _, p in segments])
        delta = np.concatenate([np.diff(p, axis=0) for _, p in segments])
        owners = np.concatenate([np.full(len(p)-1, i) for i, p in segments])
        length2 = np.sum(delta*delta, axis=1)
        valid = length2 > 1e-12
        self.start, self.delta, self.owner = start[valid], delta[valid], owners[valid]
        self.family = np.asarray(families)[self.owner] if families is not None else None
        self.length2 = length2[valid]
        if not len(self.start):
            return
        self.tangent = self.delta/np.sqrt(self.length2)[:, None]
        self.half_length = .5*np.sqrt(self.length2.max())
        self.tree = cKDTree(self.start+self.delta*.5)

    def query(self, positions, headings, owners, radius, families=None, aligned=True,
              contact_families=None, allow_crossings=True):
        target, tangent = positions.copy(), headings.copy()
        distance = np.full(len(positions), np.inf)
        if self.tree is None or radius <= 0 or not len(positions):
            return target, tangent, distance
        # Bounded nearest-midpoint search; exact distances then reject false
        # candidates. Crowded self-segments can hide eligible guides, so this
        # deliberately makes no guarantee that every encounter is detected.
        _, ids = self.tree.query(positions, k=list(range(1, min(48, len(self.start))+1)),
                                 distance_upper_bound=radius+self.half_length)
        nearby = ids < len(self.start)
        ids = np.minimum(ids, len(self.start)-1)
        offset = positions[:, None]-self.start[ids]
        fraction = np.clip(np.sum(offset*self.delta[ids], axis=2)/self.length2[ids], 0, 1)
        candidates = self.start[ids]+fraction[:, :, None]*self.delta[ids]
        distances = np.linalg.norm(candidates-positions[:, None], axis=2)
        alignment = np.sum(self.tangent[ids]*headings[:, None], axis=2)
        valid = self.owner[ids] != owners[:, None]
        if aligned:
            valid &= np.abs(alignment) >= np.cos(np.deg2rad(25.))
        if families is not None:
            valid &= self.family[ids] == families[:, None]
        if contact_families is not None:
            parallel = ((self.family[ids] == contact_families[:, None])
                        & (np.abs(alignment) >= np.cos(np.deg2rad(25.))))
            # Close duplicates yield to a stable source priority, so two tips
            # cannot both terminate against each other's deposited prefixes.
            valid &= ~parallel | (self.owner[ids] < owners[:, None])
            # Coverage can gate other junctions, but cannot license duplicates.
            valid &= parallel | np.broadcast_to(allow_crossings, len(positions))[:, None]
        valid &= nearby & (distances < radius)
        distances = np.where(valid, distances, np.inf)
        best = distances.argmin(axis=1)
        rows = np.arange(len(positions))
        found = np.isfinite(distances[rows, best])
        chosen = ids[rows, best]
        target[found] = candidates[rows, best][found]
        tangent[found] = (self.tangent[chosen]*np.where(alignment[rows, best] < 0, -1., 1.)[:, None])[found]
        distance[found] = distances[rows, best][found]
        return target, tangent, distance


class DensityShape:
    """Interpolate gradient/Hessian of log Gaussian-smoothed density.

    Derivatives use physical XYZ distances, including the thin Y domain.
    Interpolate the symmetric Hessian, not signed eigenvectors; diagonalize at
    the query so opposite eigenvector signs cannot cancel during interpolation.
    Flat or extremely thin scenes use the Y-averaged XZ density and a 2D
    eigensystem; their starting heights remain unchanged.
    """
    def __init__(self, density, half_extents, radius, derivatives=True):
        self.radius = radius
        self.half = np.asarray(half_extents, dtype=float)
        self.axes = np.array([0, 2]) if self.half[1] < radius/20 else np.arange(3)
        self.density = np.asarray(density, dtype=float)
        data = self.density if len(self.axes) == 3 else self.density.mean(axis=1)
        self.spacing = 2*self.half[self.axes]/(np.array(data.shape)-1)
        # Reflect extends density locally without inventing a sharp box-wall
        # ridge. Growth itself stops at the original box, without wrapping.
        blurred = gaussian_filter(data, radius/self.spacing, mode='reflect')
        self.log_density = np.log(np.maximum(blurred, max(blurred.max()*1e-9, 1e-30)))
        if not derivatives:
            return
        self.gradient = np.stack(np.gradient(self.log_density, *self.spacing, edge_order=2))
        n = len(self.axes)
        self.hessian = np.empty((n, n)+data.shape)
        for i in range(n):
            for j, derivative in enumerate(np.gradient(self.gradient[i], *self.spacing, edge_order=2)):
                self.hessian[i, j] = derivative
        self.hessian = (self.hessian + self.hessian.swapaxes(0, 1))*.5

    def coordinates(self, points):
        return ((points[:, self.axes] + self.half[self.axes])/self.spacing).T

    def eigensystem(self, points):
        """Physical gradient and Hessian eigenpairs on the active axes."""
        q = self.coordinates(points)
        n = len(self.axes)
        grad = np.column_stack([map_coordinates(g, q, order=1, mode='nearest') for g in self.gradient])
        hess = np.empty((len(points), n, n))
        for i in range(n):
            for j in range(i, n):
                hess[:, i, j] = hess[:, j, i] = map_coordinates(self.hessian[i, j], q, order=1, mode='nearest')
        values, vectors = np.linalg.eigh(hess)
        return grad, values, vectors

    def sample(self, points, preferred=None):
        grad, values, vectors = self.eigensystem(points)
        # A tube has two negative transverse curvatures and a less negative
        # axial one. Sheets/round peaks have an ambiguous leading direction.
        confidence = np.clip((values[:, -1]-values[:, -2]) /
                             np.maximum(np.max(np.abs(values), axis=1), 1e-9), 0, 1)
        confidence *= values[:, -2] < 0
        tangent, gradient = np.zeros_like(points), np.zeros_like(points)
        tangent[:, self.axes], gradient[:, self.axes] = vectors[:, :, -1], grad
        if preferred is not None:
            # Softly project the launch vector into low-curvature directions.
            # Tube: one axis. Sheet: its plane. Round blob: no preferred axis.
            gap = values[:, -1, None]-values
            weights = np.exp(-gap / np.maximum(.2*np.max(np.abs(values), axis=1, keepdims=True), 1e-9))
            components = np.einsum('nij,ni->nj', vectors, preferred[:, self.axes])
            tangent[:, self.axes] = np.einsum('nij,nj->ni', vectors, components*weights)
            tangent = unit(tangent)
        return tangent, gradient, confidence

    def log_value(self, points):
        return map_coordinates(self.log_density, self.coordinates(points), order=1, mode='nearest')


class PairFilamentShape:
    """Keep the three original pair directions separate, including at crossings."""
    pairs = np.array([[0, 1], [0, 2], [1, 2]])

    def __init__(self, fields, half_extents, radius, width):
        self.half = np.asarray(half_extents, dtype=float)
        self.radius, self.width = radius, width
        self.axes = np.array([0, 2]) if self.half[1] < radius/20 else np.arange(3)
        self.fields = np.asarray(fields, dtype=float)
        self.planar = len(self.axes) == 2
        self.values_grid = self.fields.mean(axis=2) if self.planar else self.fields
        self.spacing = 2*self.half[self.axes]/(np.array(self.values_grid.shape[1:])-1)
        if self.planar:
            # A literal flat slice need not contain 3D zero-intersection lines.
            # Follow each pair's own density ridge in XZ, never their sum.
            self.shapes = []
            for a, b in self.pairs:
                log_pair = -(self.fields[a]**2+self.fields[b]**2)/(2*width**2)
                self.shapes.append(DensityShape(np.exp(log_pair-log_pair.max()), self.half, radius))
        else:
            self.gradients = np.stack([np.gradient(f, *self.spacing, edge_order=2) for f in self.fields])

    def coordinates(self, points):
        return ((points[:, self.axes]+self.half[self.axes])/self.spacing).T

    def values(self, points):
        q = self.coordinates(points)
        return np.column_stack([map_coordinates(f, q, order=1, mode='nearest') for f in self.values_grid])

    def choose(self, points, rng):
        values = self.values(points)
        log_weight = -np.sum(values[:, self.pairs]**2, axis=2)/(2*self.width**2)
        weight = np.exp(log_weight-log_weight.max(axis=1, keepdims=True))
        cumulative = np.cumsum(weight/weight.sum(axis=1, keepdims=True), axis=1)
        return np.minimum((rng.random(len(points))[:, None] > cumulative).sum(axis=1), 2)

    def log_value(self, points, families):
        values = self.values(points)
        selected = values[np.arange(len(points))[:, None], self.pairs[families]]
        return -np.sum(selected**2, axis=1)/(2*self.width**2)

    def sample(self, points, families, headings):
        if self.planar:
            tangent, gradient, confidence = np.zeros_like(points), np.zeros_like(points), np.zeros(len(points))
            for family, shape in enumerate(self.shapes):
                selected = families == family
                if selected.any():
                    t, g, c = shape.sample(points[selected], headings[selected])
                    tangent[selected], gradient[selected], confidence[selected] = t, g, c
            return tangent, gradient, confidence
        # Reuse the pair-tangent/normal-correction math from stochastic curves.
        # The source is the very same cached A/B/C grids used for density.
        from _stochastic_curves import guidance
        q = self.coordinates(points)
        values = self.values(points)
        gradients = np.empty((len(points), 3, 3))
        for field in range(3):
            for axis in range(3):
                gradients[:, field, axis] = map_coordinates(self.gradients[field, axis], q, order=1, mode='nearest')
        tangent, correction = guidance(values, gradients, self.pairs[families], headings)
        return tangent, -correction/self.radius**2, np.ones(len(points))


def trace_density(density, seed, half_extents, strand_count=512, strand_length=2.,
                  direction_scale=.3, density_pull=.35, curve_wander=.15,
                  join_reach=.6, join_strength=1., join_radius=.08,
                  coverage_mode=0, coverage_radius=.5, capacity_scale=1.,
                  pair_fields=None, pair_width=.065, return_families=False):
    """Seed from density; grow both directions with bounded, local steering.

    Optional original scalar fields lock each source to AB, AC or BC. Without
    them, retain the older density-only experiment. No assigned endpoints or
    exact density-preservation claim; input density is unchanged.
    """
    half = np.asarray(half_extents, dtype=float)
    field = DensityShape(density, half, direction_scale, derivatives=pair_fields is None)
    pair_shape = PairFilamentShape(pair_fields, half, direction_scale, pair_width) if pair_fields is not None else None
    family_rng = np.random.default_rng(np.random.SeedSequence([seed, 82517]))
    rng = np.random.default_rng(np.random.SeedSequence([seed, 82191]))
    roots, _ = sample_density(density, int(strand_count), rng)
    roots = roots.astype(float)*half
    root_offsets = rng.uniform(0, 128, roots.shape)
    noise = VectorNoise(seed, max(4*direction_scale, .1), 0, 2, .35)
    families = pair_shape.choose(roots, family_rng) if pair_shape is not None else None
    preferred = noise.sample(roots, root_offsets)
    launch, _, _ = (pair_shape.sample(roots, families, preferred) if pair_shape is not None
                     else field.sample(roots, preferred))
    positions = np.repeat(roots, 2, axis=0)
    headings = np.repeat(launch, 2, axis=0)*np.tile([1., -1.], len(roots))[:, None]
    paths = [[p.copy()] for p in positions]
    # Total length is 0.5..1.5 times mean; halves share the same budget.
    budgets = np.repeat(strand_length*(.5+rng.beta(2, 2, len(roots)))/2, 2)
    offsets = np.repeat(root_offsets, 2, axis=0)
    traveled = np.zeros(len(positions))
    active = np.ones(len(positions), dtype=bool)
    floor = field.log_value(positions)-np.log(10.)
    pair_floor = (np.repeat(pair_shape.log_value(roots, families)-np.log(10.), 2)
                  if pair_shape is not None else None)
    coverage = (CurveCoverage(density, half, coverage_radius,
                             strand_count*strand_length*capacity_scale, steering=coverage_mode == 2)
                if coverage_mode else None)
    wave_size = max(1, int(np.ceil(len(roots)/4)))
    next_root = len(roots)
    residual_rng = np.random.default_rng(np.random.SeedSequence([seed, 82319]))
    if coverage_mode == 2:
        next_root = wave_size
        active[2*next_root:] = False
    step = min(.08, direction_scale/4)
    # Bounded geometry size even at the largest GUI settings.
    step = max(step, float(budgets.sum())/200000)
    interaction = join_strength > 0 and join_reach > 0
    contacts = StrandContacts([])
    iterations = int(np.ceil(budgets.max()/step))+1
    for iteration in range(iterations*(4 if coverage_mode == 2 else 1)):
        ids = np.flatnonzero(active)
        if not len(ids):
            if next_root >= len(roots):
                break
            coverage.refresh()
            end_root = min(len(roots), next_root+wave_size)
            new_roots = coverage.roots(end_root-next_root, residual_rng)
            starts = np.repeat(new_roots, 2, axis=0)
            preferred = noise.sample(new_roots, root_offsets[next_root:end_root])
            if pair_shape is not None:
                families[next_root:end_root] = pair_shape.choose(new_roots, family_rng)
                new_launch, _, _ = pair_shape.sample(new_roots, families[next_root:end_root], preferred)
            else:
                new_launch, _, _ = field.sample(new_roots, preferred)
            section = slice(2*next_root, 2*end_root)
            positions[section] = starts
            headings[section] = np.repeat(new_launch, 2, axis=0)*np.tile([1., -1.], len(new_roots))[:, None]
            floor[section] = field.log_value(starts)-np.log(10.)
            if pair_shape is not None:
                pair_floor[section] = np.repeat(pair_shape.log_value(new_roots, families[next_root:end_root])-np.log(10.), 2)
            for i, p0 in zip(range(2*next_root, 2*end_root), starts):
                paths[i] = [p0.copy()]
            active[section] = True
            next_root = end_root
            ids = np.flatnonzero(active)
        p, h = positions[ids], headings[ids]
        if coverage is not None and iteration % 4 == 0:
            coverage.refresh()
        load, deficit = coverage.sample(p) if coverage is not None else (np.zeros(len(p)), np.zeros_like(p))
        if interaction and iteration % 4 == 0:
            contacts = StrandContacts(paths, families)
        local_families = families[ids//2] if pair_shape is not None else None
        tangent, gradient, confidence = (pair_shape.sample(p, local_families, h) if pair_shape is not None
                                         else field.sample(p))
        tangent *= np.where(np.sum(tangent*h, axis=1) < 0, -1., 1.)[:, None]
        # Only transverse ascent: never deliberately pull along a strand into
        # a density maximum. Clamp its amplitude to avoid sharp correction.
        sideways = gradient-h*np.sum(gradient*h, axis=1)[:, None]
        pull = sideways*direction_scale
        pull /= np.maximum(1., np.linalg.norm(pull, axis=1))[:, None]
        wandering = noise.sample(p, offsets[ids]) if curve_wander else np.zeros_like(p)
        wandering[:, np.setdiff1d(np.arange(3), field.axes)] = 0
        joining = np.zeros_like(p)
        if interaction:
            eligible = load > .5 if coverage is not None else np.ones(len(p), dtype=bool)
            target, guide, distance = contacts.query(p[eligible], h[eligible], ids[eligible]//2, join_reach,
                families=local_families[eligible] if pair_shape is not None else None)
            weight = np.maximum(0., 1-distance/join_reach)**2
            weight *= np.minimum(1., traveled[ids[eligible]]/max(join_reach, step))
            if coverage is not None:
                # Do not consolidate an underfilled blob merely because
                # another curve is nearby. Join as local capacity runs out.
                weight *= np.clip((load[eligible]-.5)*2, 0., 1.)
            # Match the nearby strand's heading and correct sideways toward it.
            offset = target-p[eligible]
            offset -= h[eligible]*np.sum(offset*h[eligible], axis=1)[:, None]
            joining[eligible] = weight[:, None]*(guide-h[eligible] + 2*offset/join_reach)
            joining[:, np.setdiff1d(np.arange(3), field.axes)] = 0
        if coverage_mode == 2:
            deficit -= h*np.sum(deficit*h, axis=1)[:, None]
        else:
            deficit[:] = 0
        desired = unit(h + confidence[:, None]*(tangent-h) + density_pull*pull + curve_wander*wandering + join_strength*joining + deficit)
        ds = np.minimum(step, budgets[ids]-traveled[ids])
        response = 1-np.exp(-ds/max(direction_scale, .05))
        heading = unit(h + response[:, None]*(desired-h))
        proposed = p + ds[:, None]*heading
        joined = np.zeros(len(ids), dtype=bool)
        if interaction and join_radius > 0:
            eligible = traveled[ids] >= 2*step
            if coverage is not None and pair_shape is None:
                eligible &= load >= .75
            target, _, distance = contacts.query(proposed[eligible], heading[eligible], ids[eligible]//2,
                min(join_radius, join_reach), aligned=pair_shape is None,
                contact_families=local_families[eligible] if pair_shape is not None else None,
                allow_crossings=load[eligible] >= .75 if coverage is not None else True)
            hit = distance < min(join_radius, join_reach)
            joined[eligible] = hit
            # Join an actual deposited segment, not another tip's prediction.
            # Deposited geometry never moves and is never deleted afterward.
            proposed[joined] = target[hit]
        inside = np.all(np.abs(proposed) <= half+1e-10, axis=1)
        supported = field.log_value(proposed) >= floor[ids]
        if pair_shape is not None:
            # Another family's density cannot rescue a tip that left its own
            # filament. Only an explicit final contact may cross that boundary.
            supported &= (pair_shape.log_value(proposed, local_families) >= pair_floor[ids]) | joined
        full = np.zeros(len(ids), dtype=bool)
        if coverage is not None:
            proposed_load, _ = coverage.sample(proposed, steering=False)
            full = (proposed_load >= 1.) & (traveled[ids] >= 2*step)
        accepted = inside & supported & (~full | joined)
        if coverage is not None:
            coverage.deposit(p[accepted], proposed[accepted])
        for row, identity in enumerate(ids):
            if accepted[row]:
                paths[identity].append(proposed[row].copy())
        positions[ids], headings[ids] = proposed, heading
        traveled[ids] += ds
        active[ids] = accepted & ~joined & (traveled[ids] < budgets[ids]-1e-9)
    output, output_families = [], []
    for i in range(len(roots)):
        path = np.concatenate((np.asarray(paths[2*i+1])[::-1], np.asarray(paths[2*i])[1:]))
        if len(path) >= 3:
            output.append(path)
            output_families.append(families[i] if families is not None else -1)
    if not output:
        raise ValueError('No density strands survived; increase direction scale or change the noise seed')
    return (output, np.asarray(output_families)) if return_families else output
