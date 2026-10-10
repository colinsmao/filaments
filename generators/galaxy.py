"""An artistic spiral disk with a central bulge, not an astrophysics simulation."""
import numpy as np

NAME = "Spiral galaxy"
PARAMETERS = [
    dict(key="radius", label="Radius", type="float", default=5.0, min=1.0, max=30.0),
    dict(key="arms", label="Arms", type="int", default=4, min=1, max=8),
    dict(key="turns", label="Winding", type="float", default=1.3, min=0.1, max=3.0),
    dict(key="scatter", label="Arm scatter", type="float", default=0.18, min=0.01, max=1.0),
    dict(key="thickness", label="Disk thickness", type="float", default=0.12, min=0.01, max=1.0),
    dict(key="bulge", label="Bulge fraction", type="float", default=0.2, min=0.0, max=0.8),
]


def generate(count, seed, radius=5.0, arms=4, turns=1.3, scatter=0.18,
             thickness=0.12, bulge=0.2):
    rng = np.random.default_rng(seed)
    r = radius * np.sqrt(rng.random(count))
    angle = (rng.integers(arms, size=count) * (2 * np.pi / arms)
             + turns * 2 * np.pi * r / radius
             + rng.normal(0, scatter, count))
    positions = np.column_stack((r * np.cos(angle), rng.normal(0, thickness, count), r * np.sin(angle)))
    bulge_count = int(count * bulge)
    positions[:bulge_count] = rng.normal(0, radius * 0.14, (bulge_count, 3))
    t = np.clip(np.linalg.norm(positions, axis=1) / radius, 0, 1)[:, None]
    colors = (1 - t) * np.array([1.0, 0.8, 0.45]) + t * np.array([0.4, 0.65, 1.0])
    return positions, colors
