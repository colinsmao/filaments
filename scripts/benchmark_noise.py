"""CPU-only noise benchmark; never builds, starts, or closes the viewer.

Optional local references from the comparison are kept outside version control:
  --baseline .reference/noise-benchmark/previous_numpy_noise.py
  --reference2d .reference/noise-benchmark/opensimplex_numpy.py
"""
import argparse
import importlib.util
from pathlib import Path
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generators"))
from _noise import grid, FastNoiseLite, NoiseType
import noise_filaments


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure(name, function):
    function()  # warmup
    times = []
    for _ in range(3):
        started = time.perf_counter()
        function()
        times.append(time.perf_counter() - started)
    print(f"{name}: {statistics.median(times) * 1000:.1f} ms (median of 3)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--reference2d", type=Path)
    args = parser.parse_args()
    points = grid() * 2 + np.array([17.31, 31.47, 47.23], dtype=np.float32)
    coords = np.ascontiguousarray(points.T)
    print(f"One octave, {len(points):,} sample coordinates; native calls include output allocation.")
    if args.baseline:
        baseline = load_module("baseline", args.baseline)
        permutation = np.tile(np.random.default_rng(42).permutation(256), 2)
        measure("Previous NumPy Perlin 3D", lambda: baseline.gradient_noise(points, permutation))
    if args.reference2d:
        reference = load_module("reference2d", args.reference2d)
        measure("Reference NumPy OpenSimplex 2D (different dimension/precision)",
                lambda: reference.noise2d_mono(points[:, 0], points[:, 1], 42))
    for kind in ("Perlin", "OpenSimplex2", "OpenSimplex2S"):
        noise = FastNoiseLite(seed=42)
        noise.frequency = 1
        noise.noise_type = getattr(NoiseType, "NoiseType_" + kind)
        measure("Compiled " + kind + " 3D", lambda: noise.gen_from_coords(coords))
    for count in (100000, 1000000):
        measure(f"Filament generator, {count:,} stars (excludes worker startup/packing)",
                lambda: noise_filaments.generate(count, 42))


if __name__ == "__main__":
    main()
