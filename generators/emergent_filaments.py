"""Free noise-guided growth, local joins, and iterative corridor reinforcement."""
import numpy as np
from _emergent_network import grow_network

NAME = "Emergent filament network"
PRIMITIVE = "lines"
PARAMETERS = [
    dict(key="extent", label="Seed region extent (units)", type="float", default=6., min=1., max=20.),
    dict(key="seed_count", label="Seed blobs", type="int", default=10, min=2, max=12),
    dict(key="curves_per_seed", label="Max curves / direction", type="int", default=4, min=1, max=8),
    dict(key="field_count", label="Noise fields", type="int", default=3, min=3, max=4),
    dict(key="noise_type", label="Noise (0 Perlin, 1 Simplex2S)", type="int", default=0, min=0, max=1),
    dict(key="frequency", label="Noise frequency", type="float", default=1.5, min=.5, max=3.),
    dict(key="octaves", label="Detail octaves", type="int", default=1, min=1, max=3),
    dict(key="roughness", label="Detail strength", type="float", default=.2, min=0., max=.5),
    dict(key="length", label="Mean exploration length (units)", type="float", default=18., min=2., max=30.),
    dict(key="attraction", label="Noise attraction", type="float", default=1.2, min=0., max=4.),
    dict(key="wandering", label="Noise wandering strength", type="float", default=.3, min=0., max=1.5),
    dict(key="persistence", label="Wandering scale (units)", type="float", default=2., min=.3, max=8.),
    dict(key="turn_response", label="Turn response length (units)", type="float", default=.35, min=.05, max=1.5),
    dict(key="interaction_radius", label="Local interaction radius (units)", type="float", default=.8, min=.1, max=2.),
    dict(key="corridor_strength", label="Local corridor attraction", type="float", default=2., min=0., max=5.),
    dict(key="join_radius", label="Local join radius (units)", type="float", default=.12, min=0., max=.3),
    dict(key="passes", label="Growth passes", type="int", default=3, min=1, max=6),
    dict(key="reinforcement", label="Previous-pass reinforcement", type="float", default=.8, min=0., max=2.),
    dict(key="unsupported_survival", label="Unconnected curve survival", type="float", default=.2, min=0., max=1.),
    dict(key="y_scale", label="Y scale fraction", type="float", default=.35, min=0., max=1.),
    dict(key="show_seeds", label="Seed markers (0 off, 1 on)", type="int", default=1, min=0, max=1),
]


def generate_population_source(count, seed, show_seeds=1, **params):
    paths, nodes, origins, _ = grow_network(seed, **params)
    palette = np.array([[.45, .75, 1.], [.5, .9, .8], [.7, .65, 1.]])
    path_colors = palette[origins % len(palette)]
    vertices = [np.stack((p[:-1], p[1:]), axis=1).reshape(-1, 3) for p in paths]
    colors = [np.broadcast_to(c, v.shape) for c, v in zip(path_colors, vertices)]
    if show_seeds:
        t = np.linspace(0, 2*np.pi, 33)
        for node in nodes:
            ring = node + .12*np.column_stack((np.cos(t), np.zeros_like(t), np.sin(t)))
            line = np.stack((ring[:-1], ring[1:]), axis=1).reshape(-1, 3)
            vertices.append(line)
            colors.append(np.broadcast_to([1., .9, .4], line.shape))
    positions = np.concatenate(vertices).astype(np.float32)
    lines = positions, np.concatenate(colors).astype(np.float32), np.full(len(positions), .04, dtype=np.float32)
    return lines, paths, path_colors


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
