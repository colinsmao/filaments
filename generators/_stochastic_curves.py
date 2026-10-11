"""Continuous, softly attracted stochastic trajectories; no extracted path following."""
from itertools import combinations
import numpy as np
from _noise import FastNoiseLite, NoiseType, FractalType
from noise_branch_curves import build_graph


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


class CurveRepulsion:
    """Nearby other-curve segments steer tips; deposited paths are never moved.

    A periodically rebuilt tree plus a small recent-segment tree bounds lookup
    work. Closest segments are deduplicated by curve, avoiding tessellation bias.
    """
    def __init__(self, reach, capacity=441000):
        self.reach = reach
        self.a = np.empty((capacity, 3))
        self.b = np.empty((capacity, 3))
        self.owners = np.empty(capacity, dtype=int)
        self.count = self.indexed = self.batches = 0
        self.half_segment = 0.
        self.tree = None

    def add(self, starts, ends, owners):
        end = self.count + len(starts)
        self.a[self.count:end], self.b[self.count:end] = starts, ends
        self.owners[self.count:end] = owners
        self.half_segment = max(self.half_segment, float(np.linalg.norm(ends-starts, axis=1).max()) / 2)
        self.count = end
        self.batches += 1

    def force(self, positions, tangents, owners, fallback):
        from scipy.spatial import cKDTree
        if not self.count:
            return np.zeros_like(positions)
        if self.tree is None or self.batches >= 16:
            self.tree = cKDTree((self.a[:self.count] + self.b[:self.count]) * .5)
            self.indexed, self.batches = self.count, 0
        trees = [(self.tree, 0, self.indexed)]
        if self.count > self.indexed:
            recent = (self.a[self.indexed:self.count] + self.b[self.indexed:self.count]) * .5
            trees.append((cKDTree(recent), self.indexed, len(recent)))
        rows, segments = [], []
        for tree, offset, count in trees:
            _, index = tree.query(positions, k=list(range(1, min(64, count) + 1)),
                                  distance_upper_bound=self.reach + self.half_segment)
            row = np.broadcast_to(np.arange(len(positions))[:, None], index.shape)
            valid = index < count
            rows.append(row[valid])
            segments.append(index[valid] + offset)
        rows, segments = np.concatenate(rows), np.concatenate(segments)
        other = self.owners[segments] != owners[rows]
        rows, segments = rows[other], segments[other]
        if not len(rows):
            return np.zeros_like(positions)
        delta = self.b[segments] - self.a[segments]
        t = np.clip(((positions[rows] - self.a[segments]) * delta).sum(axis=1)
                    / np.maximum((delta*delta).sum(axis=1), 1e-20), 0, 1)
        away = positions[rows] - (self.a[segments] + t[:, None] * delta)
        distance = np.linalg.norm(away, axis=1)
        # Only the nearest encountered segment from each other curve contributes.
        order = np.lexsort((distance, self.owners[segments], rows))
        rows, segments, away, distance = rows[order], segments[order], away[order], distance[order]
        unique = np.r_[True, (np.diff(rows) != 0) | (np.diff(self.owners[segments]) != 0)]
        keep = unique & (distance < self.reach)
        rows, away, distance = rows[keep], away[keep], distance[keep]
        direction = away / np.maximum(distance[:, None], self.reach * .05)
        coincident = distance < 1e-10
        direction[coincident] = fallback[rows[coincident]]
        weight = (1 - distance / self.reach) ** 2
        force = np.zeros_like(positions)
        np.add.at(force, rows, direction * weight[:, None])
        force -= (force*tangents).sum(axis=1)[:, None] * tangents
        # Bound the total in crowded roots instead of letting curve count explode it.
        return force / np.maximum(1., np.linalg.norm(force, axis=1))[:, None]


def lifetime(seed, identity, budget, variation, child=False):
    """Independent bounded lifetimes; changing them cannot reseed the motion.

    Beta(2,2) gives a smoothstep-shaped survival envelope across a bundle.
    Roots span budget*(1-variation) to budget*(1+variation). Children can use
    at most their parent's remaining budget, so descendants also taper away.
    """
    rng = np.random.default_rng(np.random.SeedSequence([seed, 28463, *identity]))
    u = rng.beta(2., 2.)
    factor = 1 - variation + variation * u * (1 if child else 2)
    return budget * factor


def filament_attraction(seed, identity, strength, variation):
    """Mostly near the base strength, with a smaller tail of weakly bound curves."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 49331, *identity]))
    return strength * (1 - variation * rng.random() ** 3)


class AttractionModulation:
    """Separate seed-distance and spatial-noise multipliers for attraction only."""
    def __init__(self, seed, distance_effect=0., distance_scale=4., noise_strength=0.,
                 noise_scale=3., noise_octaves=3, noise_roughness=.5, noise_type=0):
        self.distance_effect, self.distance_scale = distance_effect, distance_scale
        self.noise_strength, self.noise_scale = noise_strength, noise_scale
        self.noise = None
        if noise_strength > 0:
            rng = np.random.default_rng(np.random.SeedSequence([seed, 58249]))
            self.noise = FastNoiseLite(seed=int(rng.integers(0, 2147483647)))
            self.noise.noise_type = NoiseType.NoiseType_Perlin if noise_type == 0 else NoiseType.NoiseType_OpenSimplex2S
            self.noise.frequency = 1.
            self.noise.fractal_type = FractalType.FractalType_FBm
            self.noise.fractal_octaves = int(noise_octaves)
            self.noise.fractal_gain = float(noise_roughness)
            self.noise.fractal_lacunarity = 2.
            self.offset = rng.uniform(0, 128, 3)

    def factors(self, positions, seed_centers):
        factors = np.ones(len(positions))
        if self.distance_effect != 0:
            distance2 = np.sum((positions - seed_centers) ** 2, axis=1)
            factors *= 1 - self.distance_effect * distance2 / (distance2 + self.distance_scale**2)
        if self.noise is not None:
            coords = np.ascontiguousarray((positions / self.noise_scale + self.offset).T, dtype=np.float32)
            values = self.noise.gen_from_coords(coords).astype(float)
            factors *= 1 + self.noise_strength * np.tanh(3 * values)
        return factors


class NoiseLandscape:
    """The same seeded fields as the exact preview, sampled directly in space."""
    def __init__(self, seed, extent=6., field_count=3, noise_type=0,
                 frequency=1.5, octaves=1, roughness=.2):
        self.scale = extent / frequency
        self.epsilon = self.scale * .005 / (2 ** (int(octaves) - 1))
        self.fields, self.offsets = [], []
        for field in range(int(field_count)):
            rng = np.random.default_rng(np.random.SeedSequence([seed, 401, field]))
            noise = FastNoiseLite(seed=int(rng.integers(0, 2147483647)))
            noise.noise_type = NoiseType.NoiseType_Perlin if noise_type == 0 else NoiseType.NoiseType_OpenSimplex2S
            noise.frequency = 1.
            noise.fractal_type = FractalType.FractalType_FBm
            noise.fractal_octaves = int(octaves)
            noise.fractal_gain = float(roughness)
            noise.fractal_lacunarity = 2.
            self.fields.append(noise)
            self.offsets.append(rng.uniform(0, 128, 3))

    def sample(self, points):
        """Values and central-difference gradients in world units, in native batches."""
        shifts = np.vstack((np.zeros((1, 3)), np.eye(3) * self.epsilon, -np.eye(3) * self.epsilon))
        probes = np.asarray(points)[:, None, :] + shifts[None]
        values, gradients = [], []
        for field, offset in zip(self.fields, self.offsets):
            coords = np.ascontiguousarray((probes.reshape(-1, 3) / self.scale + offset).T, dtype=np.float32)
            samples = field.gen_from_coords(coords).reshape(-1, 7).astype(float)
            values.append(samples[:, 0])
            gradients.append((samples[:, 1:4] - samples[:, 4:7]) / (2 * self.epsilon))
        return np.stack(values, axis=1), np.stack(gradients, axis=1)


def guidance(values, gradients, pairs, headings):
    """Return tangent and a regularized, world-space normal correction.

    J is the two-row field Jacobian. J.T (J J.T + lambda I)^-1 f is a
    gradient-preconditioned descent direction for .5*(A*A+B*B), not a projection
    applied to positions. Finite attraction lets trajectories remain off-center.
    """
    rows = np.arange(len(values))
    a, b = pairs[:, 0], pairs[:, 1]
    ga, gb = gradients[rows, a], gradients[rows, b]
    va, vb = values[rows, a], values[rows, b]
    aa = (ga * ga).sum(axis=1)
    ab = (ga * gb).sum(axis=1)
    bb = (gb * gb).sum(axis=1)
    regularizer = (aa + bb) * .003 + 1e-10
    aa, bb = aa + regularizer, bb + regularizer
    determinant = np.maximum(aa * bb - ab * ab, 1e-20)
    u, v = (bb * va - ab * vb) / determinant, (aa * vb - ab * va) / determinant
    correction = u[:, None] * ga + v[:, None] * gb
    tangent = np.cross(ga, gb)
    weak = np.linalg.norm(tangent, axis=1) < 1e-5 * np.sqrt(aa * bb)
    tangent = unit(tangent)
    tangent[weak] = headings[weak]
    tangent *= np.where((tangent * headings).sum(axis=1) < 0, -1., 1.)[:, None]
    return tangent, correction


def branch_departure_directions(landscape, position, parent_heading, pairs):
    """Start each candidate along its own tangent, oriented into the forward hemisphere."""
    values, gradients = landscape.sample(np.tile(position, (len(pairs), 1)))
    tangent, _ = guidance(values, gradients, np.asarray(pairs), np.tile(parent_heading, (len(pairs), 1)))
    return tangent


def branch_separation_scores(landscape, position, heading, pair, third,
                             parent_attraction, child_attraction, smoothness, remaining,
                             modulation=None, seed_center=None):
    """Compare two alternative routes against a predicted continuation of the parent.

    These short deterministic probes rank noise routes only. Actual children
    retain stochastic wandering/repulsion and their attachment. Both predicted
    and actual branches start along their selected pair's outgoing tangent.
    """
    alternatives = [tuple(sorted((int(retained), third))) for retained in pair]
    pairs = np.asarray([tuple(pair), *alternatives])
    positions = np.tile(position, (3, 1)).astype(float)
    headings = np.tile(heading, (3, 1)).astype(float)
    headings[1:] = branch_departure_directions(landscape, position, heading, alternatives)
    attraction = np.array([parent_attraction, child_attraction, child_attraction])
    travel = min(remaining, max(1., min(3 * smoothness, landscape.scale)))
    step = travel / 12
    blend = -np.expm1(-step / smoothness)
    scores = np.zeros(2)
    for _ in range(12):
        probes = positions + .5 * step * headings
        values, gradients = landscape.sample(probes)
        tangent, correction = guidance(values, gradients, pairs, headings)
        correction *= np.minimum(1., landscape.scale / np.maximum(np.linalg.norm(correction, axis=1), 1e-12))[:, None]
        strengths = attraction if modulation is None else attraction * modulation.factors(probes, seed_center)
        desired = unit(tangent - strengths[:, None] * correction)
        headings = unit((1-blend) * headings + blend * desired)
        positions += step * headings
        scores += np.linalg.norm(positions[1:] - positions[0], axis=1)
    return alternatives, scores / (12 * max(travel, 1e-12))


def branch_choice_probabilities(scores, preference):
    """Mix equal chances with a soft preference for route separation."""
    weights = np.exp(8 * (np.asarray(scores) - np.max(scores)))
    return (1-preference) / len(weights) + preference * weights / weights.sum()


def seed_centers(landscape, seed, extent, field_count, noise_type, frequency, octaves, roughness, seed_count,
                 return_graph=False):
    """Choose separated, verified triple zeros of any family, with no AB preference."""
    if field_count < 3:
        raise ValueError("Junction-seeded bundles require at least 3 noise fields")
    vertices, edges, families, junctions = build_graph(seed, extent, field_count, noise_type, frequency, octaves, roughness)
    candidates = np.flatnonzero(junctions)
    if not len(candidates):
        raise ValueError("No triple-zero junctions found; try another seed or noise frequency")
    pair_list = np.asarray(list(combinations(range(field_count), 2)))
    masks = (1 << pair_list[:, 0]) | (1 << pair_list[:, 1])
    incident = np.zeros(len(vertices), dtype=int)
    np.bitwise_or.at(incident, edges[:, 0], masks[families])
    np.bitwise_or.at(incident, edges[:, 1], masks[families])
    constraints = np.array([[f for f in range(field_count) if incident[node] & (1 << f)]
                            for node in candidates])
    # Graph junction keys belong to a particular triple, whose three pairs meet.
    if constraints.shape != (len(candidates), 3):
        raise ValueError("Invalid triple-junction field membership")
    roots = vertices[candidates].copy()
    rows = np.arange(len(roots))[:, None]
    # Refine the grid estimates against the continuous fields, before adding spread.
    for _ in range(12):
        values, gradients = landscape.sample(roots)
        jacobian = gradients[rows, constraints]
        valid = np.abs(np.linalg.det(jacobian)) > 1e-12
        delta = np.zeros_like(roots)
        delta[valid] = np.linalg.solve(jacobian[valid], values[rows, constraints][valid])
        delta *= np.minimum(1., landscape.scale * .15 / np.maximum(np.linalg.norm(delta, axis=1), 1e-12))[:, None]
        roots -= delta
    values, _ = landscape.sample(roots)
    valid = (np.abs(values[rows, constraints]).max(axis=1) < 1e-4) & (np.abs(roots) <= extent).all(axis=1)
    roots, constraints, candidates = roots[valid], constraints[valid], candidates[valid]
    if not len(roots):
        raise ValueError("No continuous triple-zero junctions could be refined; try another seed or noise frequency")
    rng = np.random.default_rng(np.random.SeedSequence([seed, 5123]))
    chosen = [int(rng.integers(len(roots)))]
    distances = np.full(len(roots), np.inf)
    for _ in range(min(int(seed_count), len(roots)) - 1):
        distances = np.minimum(distances, np.linalg.norm(roots - roots[chosen[-1]], axis=1))
        if distances.max() < landscape.scale * 1e-5:
            break  # Multiple mesh candidates can refine to the same junction.
        chosen.append(int(np.argmax(distances)))
    result = roots[chosen], constraints[chosen]
    if return_graph:
        return (*result, (vertices, edges, families, junctions), candidates[chosen])
    return result


def seed_routes(graph, nodes, root_fields, gradients, field_count):
    """Find existing pair-zero routes between selected seeds, without adding edges.

    Walk each pair in both directions until another selected seed, a boundary,
    or a loop. Intermediate unselected triple junctions do not change the pair.
    Returned slots identify each endpoint's local pair and outgoing sign.
    """
    vertices, edges, families, _ = graph
    pair_list = list(combinations(range(field_count), 2))
    local_pairs = [list(combinations(fields, 2)) for fields in root_fields]
    adjacency = {}
    for (a, b), family in zip(edges, families):
        adjacency.setdefault((int(family), int(a)), []).append(int(b))
        adjacency.setdefault((int(family), int(b)), []).append(int(a))
    owners = {int(node): root for root, node in enumerate(nodes)}
    routes = []
    def slot(root, pair, delta):
        axis = np.cross(gradients[root, pair[0]], gradients[root, pair[1]])
        return 2 * local_pairs[root].index(pair) + int(np.dot(axis, delta) < 0)
    for root, node in enumerate(nodes):
        for pair in local_pairs[root]:
            family = pair_list.index(pair)
            for first in set(adjacency.get((family, int(node)), [])):
                previous, current = int(node), first
                visited = {previous}
                distance = float(np.linalg.norm(vertices[current] - vertices[previous]))
                while current not in visited:
                    if current in owners:
                        other = owners[current]
                        if other > root:
                            start = slot(root, pair, vertices[first] - vertices[node])
                            end = slot(other, pair, vertices[previous] - vertices[current])
                            routes.append((root, start, other, end, distance))
                        break
                    visited.add(current)
                    following = set(adjacency.get((family, current), [])) - {previous}
                    if len(following) != 1:
                        break  # Boundary or ambiguous mesh topology: no invented link.
                    previous, current = current, following.pop()
                    distance += float(np.linalg.norm(vertices[current] - vertices[previous]))
    return routes


def paired_launch_plans(seed, copies, roots, routes, scale, bias=1.):
    """Coordinate busy arms using existing routes; never change trajectory guidance."""
    legacy = [launch_plan(seed, root, copies) for root in range(roots)]
    if bias <= 0 or roots < 2:
        return legacy
    # A seed still supports at most two pair families. Favor shorter routes,
    # with a shared random priority so both ends make the same family decision.
    selected = [set() for _ in range(roots)]
    matched = [dict() for _ in range(roots)]
    ranked = []
    for a, sa, b, sb, distance in routes:
        rng = np.random.default_rng(np.random.SeedSequence([seed, 60763, a, sa, b, sb]))
        proximity = 1 / (1 + distance / scale)
        priority = proximity * rng.uniform(.75, 1.25)
        ranked.append((priority, a, sa, b, sb, proximity))
    for _, a, sa, b, sb, proximity in sorted(ranked, reverse=True):
        if sa in matched[a] or sb in matched[b]:
            continue
        if any(len(selected[r] | {s // 2}) > 2 for r, s in ((a, sa), (b, sb))):
            continue
        selected[a].add(sa // 2)
        selected[b].add(sb // 2)
        rng = np.random.default_rng(np.random.SeedSequence([seed, 60869, a, sa, b, sb]))
        accepted = rng.random(copies) < (.65 + .3 * proximity)
        accepted[0] = True
        matched[a][sa] = accepted
        matched[b][sb] = accepted
    plans = []
    for root in range(roots):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 60901, root]))
        # Keep one sparse exploratory family when no route can support a bundle.
        if not selected[root]:
            selected[root].add(legacy[root][0][1] // 2)
        slots = sorted((2 * pair + sign for pair in selected[root] for sign in (0, 1)),
                       key=lambda s: (s not in matched[root], s))
        sparse = rng.random((copies, 6)) < .1
        target = np.zeros((copies, 6), dtype=bool)
        target[:, slots] = sparse[:, slots]
        for slot, accepted in matched[root].items():
            target[:, slot] = accepted
        target[0, slots[0]] = True
        if bias < 1:
            old = np.zeros_like(target)
            for copy, slot in legacy[root]:
                old[copy, slot] = True
            # Limit the union to two families even during the transition.
            for _, slot in legacy[root]:
                if len(selected[root]) < 2:
                    selected[root].add(slot // 2)
            slots = sorted({*slots, *(2*p+s for p in selected[root] for s in (0, 1))},
                           key=lambda s: (s not in matched[root], s))
            mix = np.random.default_rng(np.random.SeedSequence([seed, 61001, root]))
            target = np.where(mix.random((copies, 6)) < bias, target, old)
            target[0, slots[0]] = True
        plans.append([(copy, slot) for copy in range(copies) for slot in slots if target[copy, slot]])
    return plans


def launch_plan(seed, root, copies):
    """Choose 1-2 pairs, then independently accept copies in each direction.

    The primary pair has acceptance probabilities in [.5, 1]; an optional
    secondary pair has probabilities in [0, .5]. Preserve the plan prefix when
    increasing the cap, and guarantee one primary launch per blob.
    """
    rng = np.random.default_rng(np.random.SeedSequence([seed, 36529, root]))
    pairs = rng.permutation(3)[:int(rng.integers(1, 3))]
    probability = np.zeros(6)
    order = []
    for i, pair in enumerate(pairs):
        slots = pair * 2 + rng.permutation(2)
        probability[slots] = rng.uniform(.5, 1., 2) if i == 0 else rng.uniform(0., .5, 2)
        order.extend(slots)
    accepted = rng.random((copies, 6)) < probability
    accepted[0, order[0]] = True
    return [(copy, int(slot)) for copy in range(copies) for slot in order if accepted[copy, slot]]


def grow(seed, extent=6., field_count=3, noise_type=0, frequency=1.5,
         octaves=1, roughness=.2, seed_count=4, curves_per_seed=6, length=18.,
         attraction=1.5, wandering=.28, persistence=2., smoothness=.25,
         start_spread=.12, branch_probability=.4, junction_width=.22,
         max_paths=160, y_scale=.35, length_variation=.6,
         repulsion=.15, repulsion_reach=.2, attraction_variation=.9,
         branch_divergence=.8, attraction_distance_effect=0., attraction_distance_scale=4.,
         attraction_noise_strength=0., attraction_noise_scale=3.,
         attraction_noise_octaves=3, attraction_noise_roughness=.5, seed_pairing=1.):
    """Return paths, pair-family ids, root centers, and parent path ids (-1 roots).

    All travel and widths are measured before Y compression. Direct noise sampling
    continues beyond the seed box. Paths are never snapped to a guide, deduplicated,
    or joined by proximity. Branch encounters have hysteresis and a travel cooldown.
    """
    field_count, curves_per_seed, max_paths = int(field_count), int(curves_per_seed), int(max_paths)
    landscape = NoiseLandscape(seed, extent, field_count, noise_type, frequency, octaves, roughness)
    if max_paths < 1 or curves_per_seed < 1:
        raise ValueError("Curve limits must be positive")
    roots, root_fields, graph, root_nodes = seed_centers(landscape, seed, extent, field_count, noise_type, frequency,
                                     octaves, roughness, min(int(seed_count), max_paths), return_graph=True)
    pair_list = list(combinations(range(field_count), 2))
    paths, states, families, parents = [], [], [], []
    step = max(.02, min(.06, landscape.scale / (20 * 2 ** (int(octaves) - 1))))
    segment_budget = 440000  # Under the existing 1M-vertex transfer ceiling.
    repel = CurveRepulsion(repulsion_reach) if repulsion > 0 and repulsion_reach > 0 else None
    modulation = None
    if attraction_distance_effect != 0 or attraction_noise_strength > 0:
        modulation = AttractionModulation(seed, attraction_distance_effect, attraction_distance_scale,
            attraction_noise_strength, attraction_noise_scale, attraction_noise_octaves,
            attraction_noise_roughness, noise_type)

    def add(position, heading, pair, remaining, parent, identity, depth=0):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 7391, *identity]))
        branch_rng = np.random.default_rng(np.random.SeedSequence([seed, 9137, *identity]))
        repel_rng = np.random.default_rng(np.random.SeedSequence([seed, 19273, *identity]))
        remaining = lifetime(seed, identity, remaining, length_variation, child=parent >= 0)
        index = len(paths)
        paths.append([position.copy()])
        families.append(pair_list.index(tuple(pair)))
        parents.append(parent)
        states.append(dict(index=index, position=position.copy(), heading=heading.copy(), pair=np.array(pair),
                           remaining=remaining, traveled=0., depth=depth, identity=identity,
                           phase=rng.uniform(0, 2*np.pi, (3, 3)), amplitudes=rng.normal(size=(3, 3)) * np.array([1., .4, .15])[:, None],
                           inside=np.zeros(field_count, dtype=bool), cooldown=1., branch_rng=branch_rng,
                           branches=0, repel_axis=unit(repel_rng.normal(size=3)),
                           attraction=filament_attraction(seed, identity, attraction, attraction_variation),
                           seed_center=roots[identity[0]]))
        return states[-1]

    values, gradients = landscape.sample(roots)
    root_pairs = [list(combinations(fields, 2)) for fields in root_fields]
    routes = seed_routes(graph, root_nodes, root_fields, gradients, field_count) if seed_pairing > 0 else []
    plans = paired_launch_plans(seed, curves_per_seed, len(roots), routes, landscape.scale, seed_pairing)
    # Round-robin roots preserve identities; repulsion can change earlier motion.
    # Allocate one launch to every blob before spending more of the shared cap.
    for rank in range(max(map(len, plans))):
        for root, center in enumerate(roots):
            if rank >= len(plans[root]) or len(paths) >= max_paths:
                continue
            copy, slot = plans[root][rank]
            pair = root_pairs[root][slot // 2]
            sign_index = slot % 2
            sign = 1. if sign_index == 0 else -1.
            family = pair_list.index(pair)
            axis = unit(np.cross(gradients[root, pair[0]], gradients[root, pair[1]]))
            identity = (root, copy, family, sign_index)
            rng = np.random.default_rng(np.random.SeedSequence([seed, 6329, *identity]))
            offset = rng.normal(size=3)
            offset -= np.dot(offset, axis) * axis
            offset = unit(offset) * start_spread * np.sqrt(rng.random())
            heading = unit(axis * sign + .08 * wandering * rng.normal(size=3))
            if np.linalg.norm(heading) < .5:
                heading = unit(rng.normal(size=3))
            add(center + offset, heading, pair, length, -1, identity)

    active = list(states)
    if repel is not None:
        starts = np.asarray([s["position"] for s in active])
        repel.add(starts, starts, np.asarray([s["index"] for s in active]))
    while active and segment_budget >= len(active):
        positions = np.asarray([s["position"] for s in active])
        headings = np.asarray([s["heading"] for s in active])
        pairs = np.asarray([s["pair"] for s in active])
        ds = np.minimum(step, [s["remaining"] for s in active])
        # Mid-step look-ahead reduces turning lag without polygonal guide tangents.
        probes = positions + .5 * ds[:, None] * headings
        values, gradients = landscape.sample(probes)
        tangent, correction = guidance(values, gradients, pairs, headings)
        correction *= np.minimum(1., landscape.scale / np.maximum(np.linalg.norm(correction, axis=1), 1e-12))[:, None]
        traveled = np.asarray([s["traveled"] for s in active])
        phase = np.asarray([s["phase"] for s in active])
        amplitudes = np.asarray([s["amplitudes"] for s in active])
        argument = 2*np.pi * traveled[:, None, None] / persistence * np.array([.43, .81, 1.37])[None, :, None] + phase
        wander = (amplitudes * np.sin(argument)).sum(axis=1) / 1.55
        wander -= (wander * tangent).sum(axis=1)[:, None] * tangent
        strengths = np.asarray([s["attraction"] for s in active])
        if modulation is not None:
            strengths *= modulation.factors(probes, np.asarray([s["seed_center"] for s in active]))
        steering = tangent - strengths[:, None] * correction + wandering * wander
        if repel is not None:
            force = repel.force(positions, tangent, np.asarray([s["index"] for s in active]),
                                np.asarray([s["repel_axis"] for s in active]))
            # Ease into repulsion at root/branch birth, preserving attachments.
            ramp = np.clip(traveled / (2 * repulsion_reach), 0, 1)
            steering += repulsion * (ramp*ramp*(3-2*ramp))[:, None] * force
        desired = unit(steering)
        # Smooth each path's ongoing turns; branch departure is chosen separately.
        blend = -np.expm1(-ds / smoothness)
        direction = unit(headings * (1 - blend[:, None]) + desired * blend[:, None])
        updated = positions + ds[:, None] * direction
        if repel is not None:
            repel.add(positions, updated, np.asarray([s["index"] for s in active]))
        survivors, children = [], []
        for i, state in enumerate(active):
            state["position"], state["heading"] = updated[i], direction[i]
            state["remaining"] -= ds[i]
            state["traveled"] += ds[i]
            paths[state["index"]].append(updated[i].copy())
            distance = np.abs(values[i]) / np.maximum(np.linalg.norm(gradients[i], axis=1), 1e-8)
            # Only enter a third surface when also near the current two surfaces.
            for third in range(field_count):
                if third in state["pair"]:
                    continue
                was_inside = state["inside"][third]
                entering = not was_inside and distance[third] < junction_width
                if distance[third] < junction_width:
                    state["inside"][third] = True
                elif distance[third] > junction_width * 1.7:
                    state["inside"][third] = False
                eligible = (entering and np.max(distance[state["pair"]]) < 2*junction_width
                            and state["traveled"] >= state["cooldown"] and state["remaining"] > .5
                            and state["depth"] < 3 and len(paths) < max_paths)
                if eligible and state["branch_rng"].random() < branch_probability:
                    state["branches"] += 1
                    identity = (*state["identity"], state["branches"], third)
                    if branch_divergence > 0:
                        child_strength = filament_attraction(seed, identity, attraction, attraction_variation)
                        child_budget = lifetime(seed, identity, state["remaining"], length_variation, child=True)
                        alternatives, scores = branch_separation_scores(landscape, updated[i], direction[i],
                            state["pair"], third, state["attraction"], child_strength, smoothness, child_budget,
                            modulation, state["seed_center"])
                        probability = branch_choice_probabilities(scores, branch_divergence)
                        pair = alternatives[state["branch_rng"].choice(2, p=probability)]
                    else:
                        retained = int(state["branch_rng"].choice(state["pair"]))
                        pair = tuple(sorted((retained, third)))
                    departure = branch_departure_directions(landscape, updated[i], direction[i], [pair])[0]
                    child = add(updated[i], departure, pair, state["remaining"], state["index"],
                                identity, state["depth"] + 1)
                    child["inside"] = distance < junction_width * 1.7
                    children.append(child)
                    state["cooldown"] = state["traveled"] + max(1., 3*junction_width)
            if state["remaining"] > 1e-9:
                survivors.append(state)
        segment_budget -= len(active)
        active = survivors + children

    # A budget-truncated newborn can contain only its attachment vertex.
    keep = [i for i, p in enumerate(paths) if len(p) > 1]
    remap = {old: new for new, old in enumerate(keep)}
    scale = np.array([1., y_scale, 1.])
    return ([np.asarray(paths[i]) * scale for i in keep], np.asarray(families)[keep], roots * scale,
            np.array([remap.get(parents[i], -1) for i in keep]))
