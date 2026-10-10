"""Free curve growth on pairwise noise zeros, branching only at triple zeros."""
import numpy as np
from _noise import grid, FastNoiseLite, NoiseType, FractalType
from _branch_curves import intersection_graph, trace_graph

NAME = "Noise-zero branching curves"
PRIMITIVE = "lines"
PARAMETERS = [
    dict(key="extent", label="Extent (units)", type="float", default=6., min=1., max=20.),
    dict(key="field_count", label="Noise fields", type="int", default=3, min=2, max=4),
    dict(key="noise_type", label="Noise (0 Perlin, 1 Simplex2S)", type="int", default=0, min=0, max=1),
    dict(key="frequency", label="Noise frequency", type="float", default=1.5, min=.5, max=3.),
    dict(key="octaves", label="Detail octaves", type="int", default=1, min=1, max=3),
    dict(key="roughness", label="Detail strength", type="float", default=.2, min=0., max=.5),
    dict(key="seed_count", label="Starting junctions", type="int", default=4, min=1, max=24),
    dict(key="length", label="Growth length (units)", type="float", default=15., min=1., max=80.),
    dict(key="branch_probability", label="Branch probability", type="float", default=.5, min=0., max=1.),
    dict(key="max_paths", label="Maximum curves", type="int", default=96, min=8, max=256),
    dict(key="y_scale", label="Y scale fraction", type="float", default=.35, min=0., max=1.),
    dict(key="show_junctions", label="Junction markers (0 off, 1 on)", type="int", default=1, min=0, max=1),
]


def build_graph(seed, extent=6., field_count=3, noise_type=0, frequency=1.5,
                octaves=1, roughness=.2, resolution=48):
    points = grid(resolution)
    fields = []
    for field in range(int(field_count)):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 401, field]))
        noise = FastNoiseLite(seed=int(rng.integers(0, 2147483647)))
        noise.noise_type = NoiseType.NoiseType_Perlin if noise_type == 0 else NoiseType.NoiseType_OpenSimplex2S
        noise.frequency = 1.
        noise.fractal_type = FractalType.FractalType_FBm
        noise.fractal_octaves = int(octaves)
        noise.fractal_gain = float(roughness)
        noise.fractal_lacunarity = 2.
        coords = np.ascontiguousarray((points * frequency + rng.uniform(0, 128, 3)).T, dtype=np.float32)
        fields.append(noise.gen_from_coords(coords).reshape((resolution,) * 3))
    return intersection_graph(fields, extent)


def grow(seed, extent=6., field_count=3, noise_type=0, frequency=1.5,
         octaves=1, roughness=.2, seed_count=4, length=15., branch_probability=.5,
         max_paths=96, y_scale=.35):
    graph = build_graph(seed, extent, field_count, noise_type, frequency, octaves, roughness)
    paths, families, roots, junctions = trace_graph(graph, seed, seed_count, length, branch_probability, max_paths)
    scale = np.array([1., y_scale, 1.])
    return [p * scale for p in paths], families, roots * scale, junctions * scale


def generate(count, seed, show_junctions=1, **params):
    paths, families, roots, junctions = grow(seed, **params)
    palette = np.array([[.45, .75, 1.], [1., .55, .3], [.55, 1., .55],
                        [.85, .5, 1.], [1., .85, .4], [.4, 1., .9]])
    vertices, colors = [], []
    for path, family in zip(paths, families):
        line = np.stack((path[:-1], path[1:]), axis=1).reshape(-1, 3)
        vertices.append(line)
        colors.append(np.broadcast_to(palette[family], line.shape))
    if show_junctions:
        # Crosses show visited triple-zero junctions; rings distinguish roots.
        for center in junctions:
            marker = np.repeat(center[None], 6, axis=0) + np.repeat(np.eye(3), 2, axis=0) * np.tile([-.045, .045], 3)[:, None]
            vertices.append(marker)
            colors.append(np.broadcast_to([1., 1., 1.], marker.shape))
        theta = np.linspace(0, 2 * np.pi, 25)
        for center in roots:
            ring = center + np.column_stack((np.cos(theta), np.zeros_like(theta), np.sin(theta))) * .12
            marker = np.stack((ring[:-1], ring[1:]), axis=1).reshape(-1, 3)
            vertices.append(marker)
            colors.append(np.broadcast_to([1., .9, .4], marker.shape))
    if not vertices:
        raise ValueError("No curves grew; try another seed or increase growth length")
    positions = np.concatenate(vertices).astype(np.float32)
    return positions, np.concatenate(colors).astype(np.float32), np.full(len(positions), .04, dtype=np.float32)
