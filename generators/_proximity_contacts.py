"""Batched exact segment contacts within a physical radius, without guide curves."""
import numpy as np
from scipy.spatial import cKDTree


class ProximityContacts:
    def __init__(self, radius, angle, half=None):
        self.radius = radius
        self.cosine = np.cos(np.deg2rad(angle))
        self.starts = np.empty((0, 3))
        self.ends = np.empty((0, 3))
        self.owners = np.empty(0, dtype=int)
        self.joins = 0
        self.half = half
        self.bridges = {}
        self.birth = np.empty(0, dtype=int)
        self.iteration = 0
        self.ancestors = {}

    def advance_batch(self, starts, ends, owners, budgets):
        ends = ends.copy()
        joined = np.zeros(len(starts), dtype=bool)
        self.bridges = {}
        for owner in owners:
            self.ancestors.setdefault(int(owner), 0)
        if len(self.starts):
            vector = self.ends-self.starts
            norm2 = np.einsum('ij,ij->i', vector, vector)
            delta = ends-starts
            lengths2 = np.einsum('ij,ij->i', delta, delta)
            tree = cKDTree((self.starts+self.ends)*.5)
            candidates = tree.query_ball_point((starts+ends)*.5,
                self.radius + .5*(np.sqrt(lengths2)+np.sqrt(norm2.max())))
            sizes = np.fromiter(map(len, candidates), dtype=int, count=len(candidates))
            rows = np.repeat(np.arange(len(starts)), sizes)
            cols = np.concatenate(candidates).astype(int) if sizes.sum() else np.empty(0, dtype=int)
            if len(cols):
                # Elect one winner between fresh parallel fronts. Older geometry
                # can receive a contact from either priority; a small ancestry
                # DAG below prevents the winning route joining its own feeder.
                keep = (self.owners[cols] != owners[rows]) & ((self.owners[cols] < owners[rows]) |
                        (self.iteration-self.birth[cols] >= 2))
                rows, cols = rows[keep], cols[keep]
                a, c = lengths2[rows], norm2[cols]
                u, v = delta[rows], vector[cols]
                b = np.einsum('ij,ij->i', u, v)
                keep = (np.abs(b)+1e-12 >= self.cosine*np.sqrt(a*c)) & (a > 1e-18)
                rows, cols, a, b, c, u, v = (x[keep] for x in (rows, cols, a, b, c, u, v))
                w = starts[rows]-self.starts[cols]
                d, e = np.einsum('ij,ij->i', u, w), np.einsum('ij,ij->i', v, w)
                denominator = a*c-b*b
                s = np.clip(np.divide(b*e-c*d, denominator, out=np.zeros_like(a),
                                      where=denominator > 1e-12*a*c), 0, 1)
                t = (b*s+e)/c
                s = np.where(t < 0, np.clip(-d/a, 0, 1),
                             np.where(t > 1, np.clip((b-d)/a, 0, 1), s))
                t = np.clip(t, 0, 1)
                targets = self.starts[cols]+t[:, None]*v
                distance2 = np.sum((starts[rows]+s[:, None]*u-targets)**2, axis=1)
                travel2 = np.sum((starts[rows]-targets)**2, axis=1)
                keep = (distance2 <= self.radius**2) & (travel2 <= budgets[rows]**2)
                rows, cols, s, distance2, targets = (x[keep] for x in (rows, cols, s, distance2, targets))
                order = np.lexsort((cols, distance2, s, rows))
                for choice in order:
                    row, col = rows[choice], cols[choice]
                    source, receiver = int(owners[row]), int(self.owners[col])
                    if joined[row] or self.ancestors[receiver] & (1 << source):
                        continue
                    target = targets[choice]
                    distance = np.linalg.norm(target-starts[row])
                    heading = delta[row]/np.sqrt(lengths2[row])
                    axis = vector[col]/np.sqrt(norm2[col])
                    if axis@heading < 0:
                        axis = -axis
                    # A short cubic connects tangentially instead of inserting
                    # an abrupt sideways line. Deposit the very same polyline
                    # used for rendering/population and enforce its arc budget.
                    controls = np.array([starts[row], starts[row]+heading*distance/3,
                                         target-axis*distance/3, target])
                    if self.half is not None:
                        controls = np.clip(controls, -self.half, self.half)
                    t = np.linspace(0, 1, 7)[:, None]
                    bridge = ((1-t)**3*controls[0] + 3*(1-t)**2*t*controls[1]
                              + 3*(1-t)*t*t*controls[2] + t**3*controls[3])
                    if np.linalg.norm(np.diff(bridge, axis=0), axis=1).sum() <= budgets[row]+1e-9:
                        ends[row], joined[row] = target, True
                        self.bridges[row] = bridge
                        inherited = (1 << receiver) | self.ancestors[receiver]
                        for ancestor, destinations in self.ancestors.items():
                            if ancestor == source or destinations & (1 << source):
                                self.ancestors[ancestor] |= inherited
        valid = np.linalg.norm(ends-starts, axis=1) > 1e-9
        straight = valid & ~joined
        added_a, added_b, added_owners = [starts[straight]], [ends[straight]], [owners[straight]]
        for row, bridge in self.bridges.items():
            keep = np.linalg.norm(np.diff(bridge, axis=0), axis=1) > 1e-9
            added_a.append(bridge[:-1][keep]); added_b.append(bridge[1:][keep])
            added_owners.append(np.full(np.count_nonzero(keep), owners[row]))
        self.starts = np.concatenate([self.starts]+added_a)
        self.ends = np.concatenate([self.ends]+added_b)
        self.birth = np.r_[self.birth, np.full(sum(map(len, added_owners)), self.iteration)]
        self.owners = np.concatenate([self.owners]+added_owners)
        self.iteration += 1
        self.joins += int(joined.sum())
        return ends, joined
