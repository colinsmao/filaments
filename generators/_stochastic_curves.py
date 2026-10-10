"""Continuous, softly attracted stochastic trajectories; no extracted path following."""
from itertools import combinations
import numpy as np
from _noise import FastNoiseLite, NoiseType, FractalType
from noise_branch_curves import build_graph
from _branch_curves import trace_graph


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


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


def seed_centers(landscape, seed, extent, field_count, noise_type, frequency, octaves, roughness, seed_count):
    # The old graph locates starting blobs only. No graph edges guide growth.
    graph = build_graph(seed, extent, field_count, noise_type, frequency, octaves, roughness)
    roots = trace_graph(graph, seed, seed_count, length=.01, branch_probability=0)[2].copy()
    values, _ = landscape.sample(roots)
    constraints = [np.array([0, 1, 2 + np.argmin(abs(v[2:]))]) if field_count > 2
                   else np.array([0, 1]) for v in values]
    # Refine the grid estimate against the continuous fields, before adding spread.
    for _ in range(8):
        values, gradients = landscape.sample(roots)
        for i, selected in enumerate(constraints):
            delta = np.linalg.lstsq(gradients[i, selected], values[i, selected], rcond=1e-4)[0]
            delta *= min(1., landscape.scale * .15 / max(np.linalg.norm(delta), 1e-12))
            roots[i] -= delta
    return roots


def grow(seed, extent=6., field_count=3, noise_type=0, frequency=1.5,
         octaves=1, roughness=.2, seed_count=4, curves_per_seed=6, length=18.,
         attraction=1.5, wandering=.28, persistence=2., smoothness=.25,
         start_spread=.12, branch_probability=.4, junction_width=.22,
         max_paths=160, y_scale=.35, length_variation=.6):
    """Return paths, pair-family ids, root centers, and parent path ids (-1 roots).

    All travel and widths are measured before Y compression. Direct noise sampling
    continues beyond the seed box. Paths are never snapped to a guide, deduplicated,
    or joined by proximity. Branch encounters have hysteresis and a travel cooldown.
    """
    field_count, curves_per_seed, max_paths = int(field_count), int(curves_per_seed), int(max_paths)
    landscape = NoiseLandscape(seed, extent, field_count, noise_type, frequency, octaves, roughness)
    roots = seed_centers(landscape, seed, extent, field_count, noise_type, frequency, octaves, roughness, seed_count)
    pair_list = list(combinations(range(field_count), 2))
    paths, states, families, parents = [], [], [], []
    step = max(.02, min(.06, landscape.scale / (20 * 2 ** (int(octaves) - 1))))
    segment_budget = 440000  # Under the existing 1M-vertex transfer ceiling.

    def add(position, heading, pair, remaining, parent, identity, depth=0):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 7391, *identity]))
        branch_rng = np.random.default_rng(np.random.SeedSequence([seed, 9137, *identity]))
        remaining = lifetime(seed, identity, remaining, length_variation, child=parent >= 0)
        index = len(paths)
        paths.append([position.copy()])
        families.append(pair_list.index(tuple(pair)))
        parents.append(parent)
        states.append(dict(index=index, position=position.copy(), heading=heading.copy(), pair=np.array(pair),
                           remaining=remaining, traveled=0., depth=depth, identity=identity,
                           phase=rng.uniform(0, 2*np.pi, (3, 3)), amplitudes=rng.normal(size=(3, 3)) * np.array([1., .4, .15])[:, None],
                           inside=np.zeros(field_count, dtype=bool), cooldown=1., branch_rng=branch_rng,
                           branches=0))
        return states[-1]

    values, gradients = landscape.sample(roots)
    headings = unit(np.cross(gradients[:, 0], gradients[:, 1]))
    # Round-robin roots: increasing the copy count preserves earlier trajectories.
    for copy in range(curves_per_seed):
        for root, center in enumerate(roots):
            for sign_index, sign in enumerate((1., -1.)):
                if len(paths) >= max_paths:
                    break
                rng = np.random.default_rng(np.random.SeedSequence([seed, 6329, root, copy, sign_index]))
                offset = rng.normal(size=3)
                offset -= np.dot(offset, headings[root]) * headings[root]
                offset = unit(offset) * start_spread * np.sqrt(rng.random())
                heading = unit(headings[root] * sign + .08 * wandering * rng.normal(size=3))
                if np.linalg.norm(heading) < .5:
                    heading = unit(rng.normal(size=3))
                add(center + offset, heading, (0, 1), length, -1, (root, copy, sign_index))

    active = list(states)
    while active and segment_budget >= len(active):
        positions = np.asarray([s["position"] for s in active])
        headings = np.asarray([s["heading"] for s in active])
        pairs = np.asarray([s["pair"] for s in active])
        ds = np.minimum(step, [s["remaining"] for s in active])
        # Mid-step look-ahead reduces turning lag without polygonal guide tangents.
        values, gradients = landscape.sample(positions + .5 * ds[:, None] * headings)
        tangent, correction = guidance(values, gradients, pairs, headings)
        correction *= np.minimum(1., landscape.scale / np.maximum(np.linalg.norm(correction, axis=1), 1e-12))[:, None]
        traveled = np.asarray([s["traveled"] for s in active])
        phase = np.asarray([s["phase"] for s in active])
        amplitudes = np.asarray([s["amplitudes"] for s in active])
        argument = 2*np.pi * traveled[:, None, None] / persistence * np.array([.43, .81, 1.37])[None, :, None] + phase
        wander = (amplitudes * np.sin(argument)).sum(axis=1) / 1.55
        wander -= (wander * tangent).sum(axis=1)[:, None] * tangent
        desired = unit(tangent - attraction * correction + wandering * wander)
        # A smooth angular response limits sudden turns, including at branch birth.
        blend = -np.expm1(-ds / smoothness)
        direction = unit(headings * (1 - blend[:, None]) + desired * blend[:, None])
        updated = positions + ds[:, None] * direction
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
                    retained = int(state["branch_rng"].choice(state["pair"]))
                    pair = tuple(sorted((retained, third)))
                    state["branches"] += 1
                    child = add(updated[i], direction[i], pair, state["remaining"], state["index"],
                                (*state["identity"], state["branches"], third), state["depth"] + 1)
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
