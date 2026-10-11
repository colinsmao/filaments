"""One-pass persistent walks with one local guide and value-only vector noise."""
import numpy as np
from scipy.spatial import cKDTree
from _noise import FastNoiseLite, NoiseType, FractalType


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def ball(rng, count, radius):
    return unit(rng.normal(size=(count, 3))) * radius * rng.random((count, 1))**(1/3)


class VectorNoise:
    def __init__(self, seed, scale, noise_type, octaves, roughness):
        self.scale = scale
        self.fields, self.offsets = [], []
        for axis in range(3):
            rng = np.random.default_rng(np.random.SeedSequence([seed, 90101, axis]))
            field = FastNoiseLite(seed=int(rng.integers(0, 2147483647)))
            field.noise_type = NoiseType.NoiseType_Perlin if noise_type == 0 else NoiseType.NoiseType_OpenSimplex2S
            field.frequency = 1.
            field.fractal_type = FractalType.FractalType_FBm
            field.fractal_octaves = int(octaves)
            field.fractal_gain = float(roughness)
            field.fractal_lacunarity = 2.
            self.fields.append(field)
            self.offsets.append(rng.uniform(0, 128, 3))

    def sample(self, points, individual_offsets):
        # Shared landscape dominates; a small independent component separates
        # copies. No gradients, zeros, or surface intersection graph are used.
        result = []
        for field, offset in zip(self.fields, self.offsets):
            coords = points/self.scale + offset
            shared = field.gen_from_coords(np.ascontiguousarray(coords.T, dtype=np.float32))
            individual = field.gen_from_coords(np.ascontiguousarray((coords+individual_offsets).T, dtype=np.float32))
            result.append(2*(.8*shared+.2*individual))
        return np.column_stack(result)


class SegmentIndex:
    """One global tree, queried in batches; candidate segments retain curve owners."""
    def __init__(self, paths, groups):
        used = [i for i, p in enumerate(paths) if len(p) > 1]
        self.tree = None
        if not used:
            return
        self.starts = np.concatenate([np.asarray(paths[i][:-1]) for i in used])
        self.delta = np.concatenate([np.diff(paths[i], axis=0) for i in used])
        self.owner = np.concatenate([np.full(len(paths[i])-1, i, dtype=int) for i in used])
        self.group = groups[self.owner]
        self.axes = unit(self.delta)
        self.tree = cKDTree(self.starts+.5*self.delta)
        self.half = float(np.linalg.norm(self.delta, axis=1).max()/2)

    def candidates(self, positions, headings, groups, radius):
        n = len(positions)
        if self.tree is None or radius <= 0:
            return np.empty((n, 0)), np.empty((n, 0, 3)), np.empty((n, 0), dtype=int)
        _, ids = self.tree.query(positions, k=list(range(1, min(24, len(self.starts))+1)),
                                 distance_upper_bound=radius+self.half)
        valid = ids < len(self.starts)
        ids = np.minimum(ids, len(self.starts)-1)
        delta = self.delta[ids]
        t = np.clip(np.sum((positions[:, None]-self.starts[ids])*delta, axis=2)
                    / np.maximum(np.sum(delta*delta, axis=2), 1e-20), 0, 1)
        offset = self.starts[ids]+t[..., None]*delta-positions[:, None]
        distance = np.linalg.norm(offset, axis=2)
        alignment = np.sum(self.axes[ids]*headings[:, None], axis=2)
        valid &= (distance < radius) & (self.group[ids] != groups[:, None]) & (np.abs(alignment) > .5)
        score = np.where(valid, (1-distance/radius)**2 * alignment**2, 0.)
        owner = self.owner[ids]
        # Count each curve once, regardless of how many of its segments appear.
        order = np.argsort(-score, axis=1, kind='stable')
        ordered_owner = np.take_along_axis(owner, order, axis=1)
        duplicate = np.any((ordered_owner[:, :, None] == ordered_owner[:, None, :])
                           & np.tril(np.ones((order.shape[1], order.shape[1]), dtype=bool), -1)[None], axis=2)
        ordered_score = np.take_along_axis(score, order, axis=1)
        ordered_score[duplicate] = 0
        score = np.take_along_axis(ordered_score, np.argsort(order, axis=1), axis=1)
        tangent = self.axes[ids]*np.where(alignment < 0, -1., 1.)[..., None]
        transverse = offset - np.sum(offset*headings[:, None], axis=2)[..., None]*headings[:, None]
        guide = unit(tangent + transverse/radius)
        return score, guide, owner


def choose_guides(scores, kinds, owners, previous_kind, previous_owner, remaining, rng, free_probability):
    """Retain one valid guide, or make one weighted choice; never sum targets."""
    n = len(scores)
    rows = np.arange(n)
    matches = (kinds[None] == previous_kind[:, None]) & (owners == previous_owner[:, None]) & (scores > 0)
    match = np.argmax(np.where(matches, scores, -1.), axis=1)
    hold = (remaining > 0) & matches.any(axis=1)
    rest = (remaining > 0) & (previous_kind == 0)
    total = scores.sum(axis=1)
    pick = np.sum(np.cumsum(scores, axis=1) < (rng.random(n)*total)[:, None], axis=1)
    pick = np.minimum(pick, scores.shape[1]-1)
    pick = np.where(hold, match, pick)
    exploring = (~hold & (rng.random(n) < free_probability)) | (total == 0) | rest
    selected_kind = np.where(exploring, 0, kinds[pick])
    selected_owner = np.where(exploring, -1, owners[rows, pick])
    return pick, selected_kind, selected_owner, hold | rest


def walk(seed, extent=6., blob_count=10, curves_per_blob=5, free_filaments=15,
         length=16., length_variation=.6, noise_type=0, noise_scale=3., octaves=2,
         roughness=.35, wandering=.7, persistence=.8, guide_strength=2.5,
         blob_radius=3., filament_radius=1., capture_radius=.18,
         guide_hold=1.5, free_probability=.2, y_scale=.35):
    blob_count, curves_per_blob, free_filaments = int(blob_count), int(curves_per_blob), int(free_filaments)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 90113]))
    blobs = []
    for _ in range(blob_count):
        candidates = ball(rng, 8, extent)
        chosen = 0 if not blobs else np.argmax(np.linalg.norm(candidates[:, None]-np.asarray(blobs)[None], axis=2).min(axis=1))
        blobs.append(candidates[chosen])
    blobs = np.asarray(blobs).reshape(-1, 3)
    starts, headings, groups, budgets, offsets = [], [], [], [], []
    for group in range(blob_count+free_filaments):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 90121, group]))
        free = group >= blob_count
        center = ball(rng, 1, extent)[0] if free else blobs[group]
        direction = unit(rng.normal(size=3))
        for copy in range(2 if free else curves_per_blob):
            starts.append(center.copy())
            headings.append(direction*(1 if copy == 0 else -1) if free else unit(rng.normal(size=3)))
            groups.append(group)
            budgets.append(length*(1-length_variation+2*length_variation*rng.beta(2, 2))*(.5 if free else 1.))
            offsets.append(rng.uniform(0, 128, 3))
    if not starts:
        raise ValueError('Enable blob-launched curves or free filaments')
    positions, headings = np.asarray(starts), np.asarray(headings)
    groups, budgets, offsets = np.asarray(groups), np.asarray(budgets), np.asarray(offsets)
    paths = [[p.copy()] for p in positions]
    noise = VectorNoise(seed, noise_scale, noise_type, octaves, roughness)
    choice_rng = np.random.default_rng(np.random.SeedSequence([seed, 90139]))
    traveled = np.zeros(len(paths))
    hold = np.zeros(len(paths))
    guide_kind = np.zeros(len(paths), dtype=int)
    guide_owner = np.full(len(paths), -1, dtype=int)
    captured = np.full(len(paths), -1, dtype=int)
    active = np.ones(len(paths), dtype=bool)
    step = .08
    index = SegmentIndex([], np.empty(0, dtype=int))
    following_steps = 0
    max_steps = min(int(np.ceil(budgets.max()/step)), max(2, 160000//len(paths)))
    for tick in range(max_steps):
        ids = np.flatnonzero(active)
        if not len(ids):
            break
        p, h = positions[ids], headings[ids]
        ds = np.minimum(step, budgets[ids]-traveled[ids])
        if tick % 8 == 0 and filament_radius > 0 and guide_strength > 0:
            index = SegmentIndex(paths, groups)
        direction = np.zeros_like(p)
        if guide_strength > 0:
            vector = blobs[None] - p[:, None]
            distance = np.linalg.norm(vector, axis=2)
            blob_score = np.where((distance < blob_radius) & (np.arange(blob_count)[None] != groups[ids, None]),
                                  (1-distance/max(blob_radius, 1e-12))**2, 0.)
            score, guide, owner = index.candidates(p, h, groups[ids], filament_radius)
            # Dummy zero-score column allows scenes without blobs or nearby guides.
            scores = np.column_stack((np.zeros(len(ids)), blob_score, score))
            vectors = np.concatenate((np.zeros((len(ids), 1, 3)), unit(vector), guide), axis=1)
            kinds = np.r_[0, np.ones(blob_count, dtype=int), np.full(score.shape[1], 2, dtype=int)]
            owners = np.column_stack((np.full(len(ids), -1), np.broadcast_to(np.arange(blob_count), blob_score.shape), owner))
            pick, kind, chosen, retained = choose_guides(scores, kinds, owners, guide_kind[ids], guide_owner[ids],
                                                        hold[ids], choice_rng, free_probability)
            direction = vectors[np.arange(len(ids)), pick] * (kind != 0)[:, None]
            # Fade at the influence boundary. Only this selected guide acts.
            direction *= np.sqrt(scores[np.arange(len(ids)), pick])[:, None]
            hold[ids] = np.where(retained, hold[ids], guide_hold)
            guide_kind[ids], guide_owner[ids] = kind, chosen
            following_steps += int(np.count_nonzero(kind == 2))
        random_steering = noise.sample(p, offsets[ids]) if wandering > 0 else np.zeros_like(p)
        proposed = h + (ds/persistence)[:, None]*(wandering*random_steering + guide_strength*direction)
        new_heading = unit(proposed)
        stalled = np.linalg.norm(new_heading, axis=1) < .5
        new_heading[stalled] = h[stalled]
        updated = p + ds[:, None]*new_heading
        if blob_count and capture_radius > 0:
            distances = np.linalg.norm(updated[:, None]-blobs[None], axis=2)
            distances = np.where(np.arange(blob_count)[None] == groups[ids, None], np.inf, distances)
            closest = np.argmin(distances, axis=1)
            hit = distances[np.arange(len(ids)), closest] < capture_radius
            updated[hit] = blobs[closest[hit]]
            captured[ids[hit]] = closest[hit]
            active[ids[hit]] = False
        for row, i in enumerate(ids):
            paths[i].append(updated[row].copy())
        positions[ids], headings[ids] = updated, new_heading
        traveled[ids] += ds
        hold[ids] -= ds
        active[ids[traveled[ids] >= budgets[ids]-1e-9]] = False
    output, output_groups = [], []
    for group in range(blob_count+free_filaments):
        ids = np.flatnonzero(groups == group)
        if group < blob_count:
            output.extend(np.asarray(paths[i]) for i in ids)
            output_groups.extend([group]*len(ids))
        else:
            output.append(np.concatenate((np.asarray(paths[ids[1]])[::-1], np.asarray(paths[ids[0]])[1:])))
            output_groups.append(group)
    scale = np.array([1., y_scale, 1.])
    return ([p*scale for p in output], blobs*scale, np.asarray(output_groups),
            dict(captures=int(np.count_nonzero(captured >= 0)), following_steps=following_steps,
                 steps=int(sum(len(p)-1 for p in paths)), captured=captured, starts=np.asarray(starts),
                 initial_groups=groups, half_paths=paths))
