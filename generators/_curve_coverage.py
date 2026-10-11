"""Density-proportional curve-length target and deposited material, in world units."""
import itertools
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from _noise import sample_density


class CurveCoverage:
    def __init__(self, density, half_extents, radius, total_length, resolution=48, steering=True):
        self.steering = steering
        self.half = np.asarray(half_extents, dtype=float)
        self.axes = np.array([0, 2]) if self.half[1] < radius/20 else np.arange(3)
        source = density if len(self.axes) == 3 else density.mean(axis=1)
        self.shape = (resolution,)*len(self.axes)
        q = np.meshgrid(*[np.linspace(0, n-1, resolution) for n in source.shape], indexing='ij')
        target = map_coordinates(source, np.array(q), order=1, mode='nearest')
        # Trapezoidal mass, including half-weight boundary vertices, just as
        # the original tent-density sampler. Global density scaling cancels.
        for axis in range(target.ndim):
            for edge in (0, -1):
                sl = [slice(None)]*target.ndim
                sl[axis] = edge
                target[tuple(sl)] *= .5
        self.target = target*(total_length/max(target.sum(), 1e-30))
        self.spacing = 2*self.half[self.axes]/(resolution-1)
        self.radius = radius
        self.sigma = radius/self.spacing
        self.deposited = np.zeros_like(target)
        self.smooth_target = gaussian_filter(self.target, self.sigma, mode='constant')
        self.refresh()

    def coordinates(self, positions):
        return ((positions[:, self.axes]+self.half[self.axes])/self.spacing).T

    def refresh(self):
        self.smooth_deposited = gaussian_filter(self.deposited, self.sigma, mode='constant')
        floor = max(self.smooth_target.max()*1e-6, 1e-12)
        self.load = self.smooth_deposited/np.maximum(self.smooth_target, floor)
        # Bounded fractional deficit: steer toward *underrepresented* space,
        # not just toward the already strongest density peak a second time.
        if self.steering:
            deficit = np.maximum(1-self.load, .05)
            self.deficit_gradient = np.stack(np.gradient(np.log(deficit), *self.spacing, edge_order=2))

    def sample(self, positions, steering=True):
        q = self.coordinates(positions)
        load = map_coordinates(self.load, q, order=1, mode='nearest')
        gradient = np.zeros_like(positions)
        if not steering or not self.steering:
            return load, gradient
        gradient[:, self.axes] = np.column_stack([map_coordinates(g, q, order=1, mode='nearest') for g in self.deficit_gradient])
        steering = self.radius*gradient
        steering /= np.maximum(1., np.linalg.norm(steering, axis=1))[:, None]
        return load, steering

    def deposit(self, start, end):
        if not len(start):
            return
        # Subdivide long contact snaps as well as ordinary growth steps; each
        # sample deposits its exact share of segment arc length, not a count.
        lengths = np.linalg.norm(end-start, axis=1)
        pieces = np.maximum(1, np.ceil(lengths/(.5*self.spacing.min())).astype(int))
        rows = np.repeat(np.arange(len(start)), pieces)
        offsets = np.arange(len(rows))-np.repeat(np.r_[0, np.cumsum(pieces)[:-1]], pieces)
        fractions = (offsets+.5)/pieces[rows]
        positions = start[rows]+(end-start)[rows]*fractions[:, None]
        mass = lengths[rows]/pieces[rows]
        q = np.clip(self.coordinates(positions).T, 0, np.array(self.shape)-1)
        base = np.minimum(q.astype(int), np.array(self.shape)-2)
        fraction = q-base
        for corner in itertools.product((0, 1), repeat=len(self.axes)):
            corner = np.asarray(corner)
            weight = np.prod(np.where(corner, fraction, 1-fraction), axis=1)
            indices = tuple((base+corner).T)
            np.add.at(self.deposited, indices, mass*weight)

    def roots(self, count, rng):
        # Prefer remaining target mass. A small floor avoids an empty sampler;
        # capacity termination still applies if the entire field is full.
        residual = self.target*np.maximum(1-self.load, .001)
        # Undo trapezoidal weights because sample_density applies them itself.
        residual = residual.copy()
        for axis in range(residual.ndim):
            for edge in (0, -1):
                sl = [slice(None)]*residual.ndim
                sl[axis] = edge
                residual[tuple(sl)] *= 2
        points, _ = sample_density(residual, count, rng)
        result = np.zeros((count, 3))
        result[:, self.axes] = points*self.half[self.axes]
        if len(self.axes) == 2 and self.half[1] > 0:
            result[:, 1] = rng.uniform(-self.half[1], self.half[1], count)
        return result
