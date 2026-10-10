"""Stars distributed around a connected network of curved filaments."""
import numpy as np

NAME = "Filament network"
PARAMETERS = [
    dict(key="extent", label="Extent", type="float", default=6.0, min=1.0, max=30.0),
    dict(key="nodes", label="Junctions", type="int", default=18, min=4, max=80),
    dict(key="width", label="Filament width", type="float", default=0.12, min=0.01, max=0.8),
    dict(key="curvature", label="Curvature", type="float", default=0.7, min=0.0, max=3.0),
    dict(key="clusters", label="Cluster fraction", type="float", default=0.2, min=0.0, max=0.8),
    dict(key="star_size", label="Star size (units)", type="float", default=0.04, min=0.002, max=0.5),
    dict(key="size_variation", label="Size variation", type="float", default=0.4, min=0.0, max=0.9),
]


def generate(count, seed, extent=6.0, nodes=18, width=0.12, curvature=0.7, clusters=0.2,
             star_size=0.04, size_variation=0.4):
    rng = np.random.default_rng(seed)
    junctions = rng.uniform(-extent, extent, (nodes, 3))
    # Connect each node to its nearest predecessor: connected with O(nodes^2)
    # work only over a small node set, never over the star count.
    edges = {(i, int(np.argmin(np.linalg.norm(junctions[:i] - junctions[i], axis=1))))
             for i in range(1, nodes)}
    distances = np.linalg.norm(junctions[:, None] - junctions[None, :], axis=2)
    np.fill_diagonal(distances, np.inf)
    for i, j in enumerate(np.argmin(distances, axis=1)):
        edges.add(tuple(sorted((i, int(j)), reverse=True)))
    pairs = np.array(sorted(edges))
    start, end = junctions[pairs[:, 0]], junctions[pairs[:, 1]]
    weights = np.linalg.norm(end - start, axis=1)
    choice = rng.choice(len(pairs), count, p=weights / weights.sum())
    t = rng.random((count, 1))
    bends = rng.normal(0, curvature, start.shape)
    positions = ((1 - t) * start[choice] + t * end[choice]
                 + np.sin(np.pi * t) * bends[choice] + rng.normal(0, width, (count, 3)))
    cluster_count = int(count * clusters)
    positions[:cluster_count] = (junctions[rng.integers(nodes, size=cluster_count)]
                                  + rng.normal(0, width * 2.5, (cluster_count, 3)))
    colors = np.broadcast_to([0.4, 0.72, 1.0], (count, 3)).copy()
    colors[:cluster_count] = [1.0, 0.72, 0.35]
    sizes = star_size * rng.uniform(1 - size_variation, 1 + size_variation, count)
    return positions, colors, sizes
