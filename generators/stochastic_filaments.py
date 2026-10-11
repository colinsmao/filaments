"""Smooth stochastic bundles attracted toward pairwise noise-zero strands."""
import numpy as np
from _stochastic_curves import grow

NAME = "Stochastic filament bundles"
PRIMITIVE = "lines"
PARAMETERS = [
    dict(key="extent", label="Seed region extent (units)", type="float", default=6., min=1., max=20.),
    dict(key="field_count", label="Noise fields", type="int", default=3, min=3, max=4),
    dict(key="noise_type", label="Noise (0 Perlin, 1 Simplex2S)", type="int", default=0, min=0, max=1),
    dict(key="frequency", label="Noise frequency", type="float", default=1.5, min=.5, max=3.),
    dict(key="octaves", label="Detail octaves", type="int", default=1, min=1, max=3),
    dict(key="roughness", label="Detail strength", type="float", default=.2, min=0., max=.5),
    dict(key="seed_count", label="Seed blobs", type="int", default=4, min=1, max=12),
    dict(key="curves_per_seed", label="Max curves / direction", type="int", default=6, min=1, max=16),
    dict(key="seed_pairing", label="Seed pairing bias", type="float", default=1., min=0., max=1.),
    dict(key="length", label="Mean curve length (units)", type="float", default=18., min=1., max=40.),
    dict(key="length_variation", label="Length variation", type="float", default=.6, min=0., max=.95),
    dict(key="attraction", label="Attraction strength", type="float", default=1.5, min=0., max=6.),
    dict(key="attraction_variation", label="Attraction variation", type="float", default=.9, min=0., max=1.),
    dict(key="attraction_distance_effect", label="Seed-distance attraction effect", type="float", default=0., min=-1., max=1.),
    dict(key="attraction_distance_scale", label="Attraction distance scale (units)", type="float", default=4., min=.1, max=20.),
    dict(key="attraction_noise_strength", label="Attraction noise strength", type="float", default=0., min=0., max=1.),
    dict(key="attraction_noise_scale", label="Attraction noise scale (units)", type="float", default=3., min=.1, max=20.),
    dict(key="attraction_noise_octaves", label="Attraction noise octaves", type="int", default=3, min=1, max=5),
    dict(key="attraction_noise_roughness", label="Attraction noise roughness", type="float", default=.5, min=0., max=1.),
    dict(key="repulsion", label="Curve repulsion", type="float", default=.15, min=0., max=1.),
    dict(key="repulsion_reach", label="Repulsion reach (units)", type="float", default=.2, min=.03, max=.6),
    dict(key="start_spread", label="Starting spread (units)", type="float", default=.12, min=0., max=1.),
    dict(key="wandering", label="Wandering strength", type="float", default=.28, min=0., max=1.5),
    dict(key="persistence", label="Wandering length (units)", type="float", default=2., min=.3, max=8.),
    dict(key="smoothness", label="Turn response length (units)", type="float", default=.25, min=.05, max=1.5),
    dict(key="branch_probability", label="Branch probability / encounter", type="float", default=.4, min=0., max=1.),
    dict(key="branch_divergence", label="Branch divergence preference", type="float", default=.8, min=0., max=1.),
    dict(key="junction_width", label="Branch encounter width (units)", type="float", default=.22, min=.03, max=1.),
    dict(key="max_paths", label="Maximum curves", type="int", default=160, min=8, max=256),
    dict(key="y_scale", label="Y scale fraction", type="float", default=.35, min=0., max=1.),
    dict(key="show_seeds", label="Seed markers (0 off, 1 on)", type="int", default=1, min=0, max=1),
    dict(key="color_families", label="Color by field pair (0 off, 1 on)", type="int", default=1, min=0, max=1),
]


def generate_population_source(count, seed, show_seeds=1, color_families=1, **params):
    paths, families, roots, _ = grow(seed, **params)
    palette = np.array([[.45, .75, 1.], [1., .55, .3], [.55, 1., .55],
                        [.85, .5, 1.], [1., .85, .4], [.4, 1., .9]])
    vertices, colors = [], []
    for path, family in zip(paths, families):
        line = np.stack((path[:-1], path[1:]), axis=1).reshape(-1, 3)
        vertices.append(line)
        colors.append(np.broadcast_to(palette[family] if color_families else [.55, .78, 1.], line.shape))
    if show_seeds:
        theta = np.linspace(0, 2*np.pi, 33)
        for center in roots:
            ring = center + .12 * np.column_stack((np.cos(theta), np.zeros_like(theta), np.sin(theta)))
            line = np.stack((ring[:-1], ring[1:]), axis=1).reshape(-1, 3)
            vertices.append(line)
            colors.append(np.broadcast_to([1., .9, .4], line.shape))
    positions = np.concatenate(vertices).astype(np.float32)
    lines = positions, np.concatenate(colors).astype(np.float32), np.full(len(positions), .04, dtype=np.float32)
    path_colors = palette[families] if color_families else np.broadcast_to([.55, .78, 1.], (len(paths), 3))
    return lines, paths, path_colors


def generate(count, seed, **params):
    return generate_population_source(count, seed, **params)[0]
