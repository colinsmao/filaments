"""CPU-only tests and an optional local benchmark; never opens the viewer."""
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("worker", ROOT / "python" / "worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class Generators(unittest.TestCase):
    def test_thin_region_preserves_noise_wavelength_and_fade_envelope(self):
        worker.load_catalog(ROOT / "generators")
        from _noise import grid, fractal_noise, fade_density
        full = fractal_noise(grid(9), 42, 2, 3).reshape(9, 9, 9)
        thin = fractal_noise(grid(9, 0.5), 42, 2, 3).reshape(9, 9, 9)
        # Shared spatial coordinates must have identical noise, unlike squashing.
        np.testing.assert_array_equal(full[:, 2:7, :], thin[:, ::2, :])
        envelope = fade_density(np.ones((21, 21, 21)))
        self.assertEqual(envelope[10, 10, 10], 1)
        self.assertEqual(envelope[10, 10, 0], 0)
        self.assertTrue(((envelope >= 0) & (envelope <= 1)).all())
        self.assertTrue(0 < envelope[10, 10, 18] < 1)
        self.assertTrue((envelope[0] == 0).all())

    def test_thin_region_and_fade_outputs(self):
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        for name in ("noise_clouds", "noise_filaments"):
            module = modules[name]
            plain, _, _ = module.generate(20000, 42, y_scale=0.1)
            faded, colors, sizes = module.generate(20000, 42, y_scale=0.1, fade=1)
            repeated, _, _ = module.generate(20000, 42, y_scale=0.1, fade=1)
            np.testing.assert_array_equal(faded, repeated)
            self.assertEqual(faded.shape, (20000, 3))
            self.assertTrue((np.abs(faded[:, 1]) <= 0.6).all())
            self.assertTrue(np.isfinite(faded).all() and np.isfinite(colors).all() and (sizes > 0).all())
            scale = np.array([6, 0.6, 6])
            plain_radius = np.linalg.norm(plain / scale, axis=1)
            faded_radius = np.linalg.norm(faded / scale, axis=1)
            self.assertLess(np.mean(faded_radius > 0.9), np.mean(plain_radius > 0.9) * 0.5)
            flat, _, _ = module.generate(100, 42, y_scale=0, fade=1)
            self.assertTrue((flat[:, 1] == 0).all())
        original, _, _ = modules["noise_filaments"].generate(1000, 42, layer_continuity=0)
        adaptive, _, _ = modules["noise_filaments"].generate(1000, 42, layer_continuity=1)
        np.testing.assert_array_equal(original, adaptive)  # Full-depth mode is unchanged.

    def test_continuous_noise_density_sampling(self):
        worker.load_catalog(ROOT / "generators")  # Also enables shared generator imports.
        from _noise import sample_density, fractal_noise
        rng = np.random.default_rng(91)
        points, _ = sample_density(np.ones((9, 9, 9)), 100000, rng)
        self.assertTrue((np.abs(points) < 1).all())
        np.testing.assert_allclose(points.mean(axis=0), 0, atol=0.01)
        np.testing.assert_allclose((points * points).mean(axis=0), 1 / 3, atol=0.01)
        # Linear density rho(x)=x+1 has mean x=1/3; trilinear interpolation is exact.
        linear = np.broadcast_to(np.linspace(0, 2, 9)[:, None, None], (9, 9, 9))
        points, _ = sample_density(linear, 100000, rng)
        self.assertAlmostEqual(float(points[:, 0].mean()), 1 / 3, delta=0.01)
        with self.assertRaises(ValueError):
            sample_density(np.zeros((3, 3, 3)), 10, rng)
        boundary = rng.random((1000, 3)).astype(np.float32)
        boundary[:, 0] = 1
        left, right = boundary.copy(), boundary.copy()
        left[:, 0] -= 0.0001
        right[:, 0] += 0.0001
        self.assertLess(float(np.abs(fractal_noise(left, 42, 1, 1) - fractal_noise(right, 42, 1, 1)).max()), 0.001)

    def test_seed_shapes_ranges_and_parameter_effect(self):
        catalog, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        for entry in catalog:
            module = modules[entry["id"]]
            for count in (1, 10000):
                a, color, sizes = module.generate(count, 42)
                b, _, repeated_sizes = module.generate(count, 42)
                self.assertEqual(a.shape, (count, 3))
                self.assertEqual(color.shape, (count, 3))
                np.testing.assert_array_equal(a, b)
                np.testing.assert_array_equal(sizes, repeated_sizes)
                self.assertEqual(sizes.shape, (count,))
                self.assertTrue(np.isfinite(sizes).all() and (sizes > 0).all())
                self.assertTrue(np.isfinite(a).all())
                self.assertTrue(((color >= 0) & (color <= 1)).all())
            other, _, _ = module.generate(10000, 43)
            self.assertFalse(np.array_equal(a, other))
            changed, _, _ = module.generate(10000, 42, **{entry["parameters"][0]["key"]: 15.0})
            self.assertGreater(np.linalg.norm(changed, axis=1).mean(), np.linalg.norm(a, axis=1).mean())
            same, same_color, uniform = module.generate(10000, 42, star_size=0.1, size_variation=0)
            np.testing.assert_array_equal(same, a)
            np.testing.assert_array_equal(same_color, color)
            np.testing.assert_allclose(uniform, 0.1)
            self.assertGreater(np.ptp(sizes), 0)

    def test_request_validation_and_binary_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "stars.bin"
            for count in (0, -1, 1000001, 1.5):
                result = worker.generate_request(dict(generator="galaxy", count=count), ROOT / "generators", output)
                self.assertFalse(result["ok"])
            result = worker.generate_request(dict(generator="galaxy", count=100, params={"radius": 999}), ROOT / "generators", output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["params"]["radius"], 30)
            self.assertEqual(output.stat().st_size, 16 + 100 * 28)
            self.assertEqual(output.read_bytes()[:8], b"FSTAR002")

    def test_per_star_sizes_and_legacy_scripts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "stars.bin"
            script = root / "test.py"
            prefix = "import numpy as np\ndef generate(count, seed):\n    return np.zeros((count,3)), np.ones((count,3))"
            for suffix, expected in (("", [0.04] * 3), (", 0.2", [0.2] * 3),
                                     (", np.array([0.1, 0.2, 0.3])", [0.1, 0.2, 0.3])):
                script.write_text(prefix + suffix)
                result = worker.generate_request(dict(generator="test", count=3), root, output)
                self.assertTrue(result["ok"], result)
                data = np.frombuffer(output.read_bytes()[16:], dtype="<f4").reshape(3, 7)
                np.testing.assert_allclose(data[:, 6], expected)
            for suffix in (", 0", ", -1", ", np.nan", ", np.inf", ", 1001", ", np.ones((3,1))", ", np.ones(2)"):
                script.write_text(prefix + suffix)
                result = worker.generate_request(dict(generator="test", count=3), root, output)
                self.assertFalse(result["ok"], suffix)


if __name__ == "__main__":
    import sys
    if "--benchmark" in sys.argv:
        with tempfile.TemporaryDirectory() as temp:
            for mode in ("galaxy", "filaments"):
                for count in (100000, 1000000):
                    start = time.perf_counter()
                    result = worker.generate_request(dict(generator=mode, count=count, seed=42), ROOT / "generators", Path(temp) / "points.bin")
                    assert result["ok"], result
                    print(f"{mode}: {count:,} points; math/validation/packing {result['generation_ms']:.1f} ms; in-process total {(time.perf_counter()-start)*1000:.1f} ms")
    else:
        unittest.main()
