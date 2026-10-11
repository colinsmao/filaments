"""Local encounters and repeated growth; no prescribed blob-to-blob network."""
from itertools import combinations
import numpy as np
from scipy.spatial import cKDTree
from _stochastic_curves import NoiseLandscape, seed_centers, guidance, unit, launch_plan, lifetime


class Corridors:
    """Segment indices split by source blob, so a bundle cannot reward itself."""
    def __init__(self, paths, origins, weights=None):
        self.groups = []
        if weights is None:
            weights = np.ones(len(paths))
        for origin in sorted(set(origins)):
            indices = [i for i, p in enumerate(paths) if origins[i] == origin and len(p) > 1 and weights[i] > 0]
            if not indices:
                continue
            starts = np.concatenate([np.asarray(paths[i][:-1]) for i in indices])
            ends = np.concatenate([np.asarray(paths[i][1:]) for i in indices])
            owner = np.concatenate([np.full(len(paths[i])-1, i, dtype=int) for i in indices])
            weight = np.concatenate([np.full(len(paths[i])-1, weights[i]) for i in indices])
            delta = ends - starts
            self.groups.append((origin, starts, delta, unit(delta), owner, weight,
                                cKDTree(starts + .5*delta), float(np.linalg.norm(delta, axis=1).max()/2)))

    def query(self, positions, headings, origins, radius):
        """Bounded local force and closest aligned encounter on actual segments."""
        force = np.zeros_like(positions)
        nearest = np.full(len(positions), np.inf)
        targets = positions.copy()
        owners = np.full(len(positions), -1, dtype=int)
        if radius <= 0:
            return force, nearest, targets, owners
        for origin, starts, delta, axes, owner, weight, tree, half in self.groups:
            rows = np.flatnonzero(origins != origin)
            if not len(rows):
                continue
            _, indices = tree.query(positions[rows], k=list(range(1, min(4, len(starts))+1)),
                                    distance_upper_bound=radius+half)
            valid = indices < len(starts)
            ids = np.minimum(indices, len(starts)-1)
            direction = delta[ids]
            t = np.clip(np.sum((positions[rows, None] - starts[ids])*direction, axis=2)
                        / np.maximum(np.sum(direction*direction, axis=2), 1e-20), 0, 1)
            closest = starts[ids] + t[..., None]*direction
            offset = closest - positions[rows, None]
            distance = np.linalg.norm(offset, axis=2)
            alignment = np.sum(headings[rows, None]*axes[ids], axis=2)
            valid &= (distance < radius) & (np.abs(alignment) > .5)
            distance = np.where(valid, distance, np.inf)
            pick = np.argmin(distance, axis=1)
            rr = np.arange(len(rows))
            chosen = ids[rr, pick]
            d = distance[rr, pick]
            good = np.isfinite(d)
            rows, chosen, d = rows[good], chosen[good], d[good]
            offset = offset[rr, pick][good]
            aligned = axes[chosen] * np.where(alignment[rr, pick][good] < 0, -1., 1.)[:, None]
            transverse = offset - np.sum(offset*headings[rows], axis=1)[:, None]*headings[rows]
            w = (1-d/radius)**2 * np.sum(aligned*headings[rows], axis=1)**2 * weight[chosen]
            force[rows] += w[:, None] * (transverse/radius + .5*(aligned-headings[rows]))
            closer = d < nearest[rows]
            r = rows[closer]
            nearest[r], owners[r] = d[closer], owner[chosen[closer]]
            targets[r] = positions[r] + offset[closer]
        force /= np.maximum(1., np.linalg.norm(force, axis=1))[:, None]
        return force, nearest, targets, owners


def trim_contact_tails(paths, contacts):
    """Stop receiving curves at their last attachment unless they also connect onward."""
    outgoing = {source for source, _, _, _ in contacts}
    incoming = {}
    for source, kind, target, _ in contacts:
        if kind != 'curve' or target in outgoing:
            continue
        p = np.asarray(paths[target])
        delta = np.diff(p, axis=0)
        point = np.asarray(paths[source][-1])
        t = np.clip(np.sum((point-p[:-1])*delta, axis=1) / np.maximum(np.sum(delta*delta, axis=1), 1e-20), 0, 1)
        index = int(np.argmin(np.linalg.norm(p[:-1]+t[:, None]*delta-point, axis=1)))
        key = index + t[index]
        if target not in incoming or key > incoming[target][0]:
            incoming[target] = (key, index, point.copy())
    for target, (_, index, point) in incoming.items():
        paths[target] = paths[target][:index+1] + [point]


def contact_statistics(contacts, origins, blob_count):
    """Measure the network after growth; this graph never steers trajectories."""
    links = set()
    parent = list(range(blob_count))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for source, kind, target, _ in contacts:
        a = int(origins[source])
        b = int(origins[target]) if kind == 'curve' else target
        links.add(tuple(sorted((a, b))))
        parent[find(a)] = find(b)
    return dict(blob_links=len(links), components=len({find(i) for i in range(blob_count)}))


def grow_network(seed, extent=6., seed_count=10, curves_per_seed=4, field_count=3,
                 noise_type=0, frequency=1.5, octaves=1, roughness=.2,
                 length=18., attraction=1.2, wandering=.3, persistence=2.,
                 turn_response=.35, interaction_radius=.8, corridor_strength=2.,
                 join_radius=.12, passes=3, reinforcement=.8,
                 unsupported_survival=.2, y_scale=.35):
    landscape = NoiseLandscape(seed, extent, field_count, noise_type, frequency, octaves, roughness)
    roots, root_fields = seed_centers(landscape, seed, extent, field_count, noise_type,
                                     frequency, octaves, roughness, seed_count)
    _, gradients = landscape.sample(roots)
    pair_list = list(combinations(range(int(field_count)), 2))
    states = []
    for root, fields in enumerate(root_fields):
        pairs = list(combinations(fields, 2))
        for copy, slot in launch_plan(seed, root, int(curves_per_seed)):
            pair = pairs[slot//2]
            identity = (root, copy, pair_list.index(pair), slot % 2)
            rng = np.random.default_rng(np.random.SeedSequence([seed, 81203, *identity]))
            axis = unit(np.cross(gradients[root, pair[0]], gradients[root, pair[1]]))
            heading = axis * (1 if slot % 2 == 0 else -1)
            heading = unit(heading + .08*wandering*rng.normal(size=3))
            states.append((root, pair, heading, lifetime(seed, identity, length, .6),
                           rng.uniform(0, 64, 3), rng.random()))
    origins = np.array([s[0] for s in states])
    pairs = np.array([s[1] for s in states])
    initial_headings = np.array([s[2] for s in states])
    budgets = np.array([s[3] for s in states])
    offsets = np.array([s[4] for s in states])
    survival_draws = np.array([s[5] for s in states])
    # Independent spatial fBm components, with per-curve offsets for wandering.
    wander_field = NoiseLandscape(seed+7919, extent=persistence, field_count=3,
                                  noise_type=noise_type, frequency=1., octaves=2, roughness=.35)
    step = max(.04, min(.09, landscape.scale/40))
    memory = None
    report = []
    effective_passes = int(passes) if reinforcement > 0 and corridor_strength > 0 else 1
    for iteration in range(effective_passes):
        paths = [[roots[o].copy()] for o in origins]
        positions = roots[origins].copy()
        headings = initial_headings.copy()
        traveled = np.zeros(len(states))
        active = np.ones(len(states), dtype=bool)
        contacts = []
        current = Corridors([], [])
        supported = np.zeros(len(states), dtype=bool)
        # Bound total work across all passes, not just the final line buffer.
        max_steps = min(int(np.ceil(budgets.max()/step)), max(2, 160000//(len(states)*effective_passes)))
        for tick in range(max_steps):
            ids = np.flatnonzero(active)
            if not len(ids):
                break
            p, h, o = positions[ids], headings[ids], origins[ids]
            ds = np.minimum(step, budgets[ids]-traveled[ids])
            values, gradients = landscape.sample(p + .5*ds[:, None]*h)
            tangent, correction = guidance(values, gradients, pairs[ids], h)
            correction *= np.minimum(1., landscape.scale/np.maximum(np.linalg.norm(correction, axis=1), 1e-12))[:, None]
            wander, _ = wander_field.sample(p+offsets[ids])
            wander *= 3.
            wander -= np.sum(wander*tangent, axis=1)[:, None]*tangent
            steering = tangent - attraction*correction + wandering*wander
            # Only nearby deposited geometry influences a tip. No destination
            # blob, edge list, or long-range target force is calculated.
            if tick % 8 == 0:
                current = Corridors(paths, origins)
            local, _, _, _ = current.query(p, h, o, interaction_radius)
            if memory is not None and reinforcement > 0:
                learned, _, _, _ = memory.query(p, h, o, interaction_radius)
                local += reinforcement*learned
            ramp = np.minimum(1., traveled[ids]/interaction_radius)
            steering += corridor_strength*ramp[:, None]*local
            blend = -np.expm1(-ds/turn_response)
            heading = unit(h*(1-blend[:, None]) + unit(steering)*blend[:, None])
            updated = p + ds[:, None]*heading
            _, distance, target, target_path = current.query(updated, heading, o, join_radius)
            blob_distance = np.linalg.norm(updated[:, None] - roots[None], axis=2)
            blob_distance[np.arange(len(ids)), o] = np.inf
            closest_blob = np.argmin(blob_distance, axis=1)
            blob_d = blob_distance[np.arange(len(ids)), closest_blob]
            can_join = traveled[ids] > 2*interaction_radius
            for row, i in enumerate(ids):
                kind, other = None, -1
                if can_join[row] and blob_d[row] < join_radius:
                    updated[row] = roots[closest_blob[row]]
                    kind, other = 'blob', int(closest_blob[row])
                elif can_join[row] and distance[row] < join_radius:
                    updated[row] = target[row]
                    kind, other = 'curve', int(target_path[row])
                paths[i].append(updated[row].copy())
                if kind:
                    supported[i] = True
                    if kind == 'curve':
                        supported[other] = True
                    contacts.append((int(i), kind, other, len(paths[i])-1))
                    active[i] = False
            positions[ids], headings[ids] = updated, heading
            traveled[ids] += ds
            active[ids[traveled[ids] >= budgets[ids]-1e-9]] = False
        trim_contact_tails(paths, contacts)
        report.append(dict(curves=len(paths), contacts=len(contacts), supported=int(supported.sum()),
                           **contact_statistics(contacts, origins, len(roots))))
        # Reuse the same random draws on each pass. Successful encounters have
        # ten times the memory weight of unsuccessful exploration.
        memory = Corridors(paths, origins, np.where(supported, 1., .1))
    keep = supported | (survival_draws < unsupported_survival)
    for source, kind, target, _ in contacts:
        if kind == 'curve':
            keep[target] = True  # Never remove the geometry a connector ends on.
    if not keep.any():
        keep[int(np.argmin(survival_draws))] = True
    retained = np.flatnonzero(keep)
    scale = np.array([1., y_scale, 1.])
    return ([np.asarray(paths[i])*scale for i in retained], roots*scale,
            origins[retained], dict(passes=report, contacts=contacts,
                retained=retained, all_paths=paths, origins=origins))
