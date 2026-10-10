"""Seed-grown skeleton preview. Geometry stays independent of star population."""
import numpy as np
from _noise import fractal_noise

NAME = "Seed-grown filament curves"
PRIMITIVE = "lines"
PARAMETERS = [
    dict(key="spread", label="Seed spread (units)", type="float", default=6., min=1., max=20.),
    dict(key="seed_count", label="Seed blobs", type="int", default=8, min=1, max=32),
    dict(key="arms", label="Filaments per seed", type="int", default=3, min=1, max=6),
    dict(key="length", label="Filament length (units)", type="float", default=8., min=.5, max=30.),
    dict(key="length_variation", label="Length variation", type="float", default=.3, min=0., max=.8),
    dict(key="noise_scale", label="Noise scale (units)", type="float", default=6., min=.5, max=20.),
    dict(key="turning", label="Noise turning (degrees / unit)", type="float", default=35., min=0., max=150.),
    dict(key="branch_spacing", label="Branch spacing (0 off)", type="float", default=0., min=0., max=12.),
    dict(key="branch_angle", label="Branch angle (degrees)", type="float", default=35., min=5., max=80.),
    dict(key="y_scale", label="Y scale fraction", type="float", default=.35, min=0., max=1.),
    dict(key="show_seeds", label="Seed markers (0 off, 1 on)", type="int", default=1, min=0, max=1),
    dict(key="color_paths", label="Color by seed (0 off, 1 on)", type="int", default=1, min=0, max=1),
]


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def grow(seed, spread=6., seed_count=8, arms=3, length=8., length_variation=.3,
         noise_scale=6., turning=35., branch_spacing=0., branch_angle=35.,
         y_scale=.35):
    """Return polylines, owner seed indices, and seed centers in world units.

    Tips advance together through a shared vector noise field. Only the component
    perpendicular to each heading bends it; a bounded rotation keeps momentum.
    Branches have independent random streams, a two-generation limit and a total
    path budget. They begin exactly on a parent vertex and have shorter lives.
    No attraction/joining rule yet: this isolates the appearance of growth.
    """
    seed_count, arms = int(seed_count), int(arms)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 381]))
    # Best-candidate spacing in a ball avoids a regular lattice or crowded seeds.
    centers = []
    for _ in range(seed_count):
        candidates = _unit(rng.normal(size=(32, 3))) * (spread * rng.random((32, 1)) ** (1 / 3))
        if centers:
            distance = np.linalg.norm(candidates[:, None] - np.asarray(centers)[None], axis=2).min(axis=1)
            centers.append(candidates[np.argmax(distance)])
        else:
            centers.append(candidates[0])
    centers = np.asarray(centers)
    paths, owners, states = [], [], []
    step = min(.08, noise_scale / 12.)
    max_paths = max(256, seed_count * arms)

    def add_tip(position, direction, budget, owner, depth, stream_id):
        local = np.random.default_rng(np.random.SeedSequence([seed, 728, stream_id]))
        paths.append([position.copy()])
        owners.append(owner)
        states.append(dict(path=len(paths) - 1, position=position.copy(), direction=direction,
                           remaining=budget, traveled=0., depth=depth, rng=local,
                           next_branch=1. + local.exponential(max(branch_spacing, .25))))

    # Approximately separated directions, randomly rotated for each seed.
    for owner, center in enumerate(centers):
        rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        for arm in range(arms):
            height = 1 - 2 * (arm + .5) / arms
            angle = arm * np.pi * (3 - np.sqrt(5))
            direction = np.array([np.sqrt(1 - height * height) * np.cos(angle), height,
                                  np.sqrt(1 - height * height) * np.sin(angle)]) @ rotation
            budget = length * rng.uniform(1 - length_variation, 1 + length_variation)
            add_tip(center, direction, budget, owner, 0, owner * arms + arm)

    active = list(states)
    while active:
        positions = np.asarray([s["position"] for s in active])
        field = np.column_stack([fractal_noise(positions, seed + 104729 * (axis + 1),
                                               1. / noise_scale, 2) for axis in range(3)])
        children = []
        survivors = []
        for i, state in enumerate(active):
            ds = min(step, state["remaining"])
            direction = state["direction"]
            bend = field[i] - np.dot(field[i], direction) * direction
            magnitude = np.linalg.norm(bend)
            angle = np.deg2rad(turning) * ds * min(2. * magnitude, 1.)
            if magnitude > 1e-12:
                direction = _unit(np.cos(angle) * direction + np.sin(angle) * bend / magnitude)
            state["position"] = state["position"] + ds * direction
            state["direction"] = direction
            state["remaining"] -= ds
            state["traveled"] += ds
            paths[state["path"]].append(state["position"].copy())
            if (branch_spacing > 0 and state["depth"] < 2 and len(paths) < max_paths
                    and state["traveled"] >= state["next_branch"] and state["remaining"] > 1.):
                local = state["rng"]
                side = local.normal(size=3)
                side = _unit(side - np.dot(side, direction) * direction)
                theta = np.deg2rad(branch_angle)
                child_direction = _unit(np.cos(theta) * direction + np.sin(theta) * side)
                add_tip(state["position"], child_direction, state["remaining"] * .65,
                        owners[state["path"]], state["depth"] + 1, 10000 + len(paths))
                children.append(states[-1])
                state["next_branch"] = state["traveled"] + 1. + local.exponential(max(branch_spacing, .25))
            if state["remaining"] > 1e-10:
                survivors.append(state)
        active = survivors + children

    scale = np.array([1., y_scale, 1.])
    return [np.asarray(path) * scale for path in paths], np.asarray(owners), centers * scale


def generate(count, seed, show_seeds=1, color_paths=1, **params):
    # The line preview's resolution is geometric, independent of the star budget.
    paths, owners, centers = grow(seed, **params)
    palette = .62 + .32 * np.cos(np.arange(len(centers))[:, None] * 2.39996
                                + np.array([0., 2.0944, 4.1888]))
    vertices, colors = [], []
    for path, owner in zip(paths, owners):
        segments = np.stack((path[:-1], path[1:]), axis=1).reshape(-1, 3)
        vertices.append(segments)
        colors.append(np.broadcast_to(palette[owner] if color_paths else [.65, .8, 1.], segments.shape))
    if show_seeds:
        # Small wire spheres are markers only; no star distribution yet.
        theta = np.linspace(0, 2 * np.pi, 25)
        for center in centers:
            for a, b in ((0, 1), (0, 2), (1, 2)):
                ring = np.broadcast_to(center, (len(theta), 3)).copy()
                ring[:, a] += .16 * np.cos(theta)
                ring[:, b] += .16 * np.sin(theta)
                segments = np.stack((ring[:-1], ring[1:]), axis=1).reshape(-1, 3)
                vertices.append(segments)
                colors.append(np.broadcast_to([1., .88, .55], segments.shape))
    positions = np.concatenate(vertices).astype(np.float32)
    return positions, np.concatenate(colors).astype(np.float32), np.full(len(positions), .04, dtype=np.float32)
