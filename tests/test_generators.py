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
    def test_zeldovich_single_mode_displacement(self):
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        module = modules["zeldovich"]
        n = 32
        x = np.arange(n, dtype=np.float32) / n
        density = np.broadcast_to(np.cos(2*np.pi*x)[:, None, None], (n, n, n)).copy()
        sx, sy, sz = module.displacement_from_density(density)
        # Positive density at x=0 must attract particles toward it, not repel.
        expected = np.broadcast_to((-np.sin(2*np.pi*x)/(2*np.pi))[:, None, None], sx.shape)
        np.testing.assert_allclose(sx, expected, atol=1e-7)
        np.testing.assert_allclose(sy, 0, atol=1e-7)
        np.testing.assert_allclose(sz, 0, atol=1e-7)
        periodic = module._sample_periodic(sx, np.array([[0.1, .2, .3], [1.1, .2, .3]]))
        np.testing.assert_allclose(periodic[0], periodic[1], atol=1e-7)

    def test_zeldovich_evolution_and_y_scaling(self):
        _, modules, _ = worker.load_catalog(ROOT / "generators")
        module = modules["zeldovich"]
        initial, _, _ = module.generate(50000, 42, evolution=0, density_power=1)
        np.testing.assert_allclose(initial.mean(axis=0), 0, atol=0.02)
        np.testing.assert_allclose((initial * initial).mean(axis=0), 12, atol=0.05)
        middle, colors, sizes = module.generate(50000, 42, evolution=0.5, density_power=1)
        later, _, _ = module.generate(50000, 42, evolution=1, density_power=1)
        # q + D*s(q) is linear in D, accounting for periodic box crossings.
        residual = (later - 2*middle + initial + 6) % 12 - 6
        np.testing.assert_allclose(residual, 0, atol=4e-6)
        thin, thin_colors, thin_sizes = module.generate(50000, 42, evolution=0.5, y_scale=0.1, density_power=1)
        np.testing.assert_array_equal(thin[:, [0, 2]], middle[:, [0, 2]])
        np.testing.assert_allclose(thin[:, 1], middle[:, 1] * 0.1)
        np.testing.assert_array_equal(thin_colors, colors)
        np.testing.assert_array_equal(thin_sizes, sizes)
        self.assertTrue((np.abs(later) <= 6).all())

    def test_zeldovich_density_power_suppresses_voids(self):
        _, modules, _ = worker.load_catalog(ROOT / "generators")
        module = modules["zeldovich"]
        base, _, sizes = module.generate(100000, 42, density_power=1)
        concentrated, colors, concentrated_sizes = module.generate(100000, 42, density_power=2)
        strong, _, _ = module.generate(100000, 42, density_power=4)
        # Measure against one common base-density estimate, not each output's own.
        from scipy.ndimage import gaussian_filter
        mass, _ = np.histogramdd(base, bins=32, range=[(-6, 6)] * 3)
        mass = gaussian_filter(mass, 1, mode="wrap")
        threshold = np.median(mass)
        fractions = []
        for positions in (base, concentrated, strong):
            cells = np.floor((positions + 6) / 12 * 32).astype(int) % 32
            fractions.append(np.mean(mass[tuple(cells.T)] < threshold))
        self.assertLess(fractions[1], fractions[0] * 0.6)
        self.assertLess(fractions[2], fractions[1] * 0.6)
        self.assertEqual(len(np.unique(concentrated, axis=0)), len(concentrated))
        np.testing.assert_array_equal(sizes, concentrated_sizes)
        thin, thin_colors, _ = module.generate(100000, 42, density_power=2, y_scale=0.1)
        np.testing.assert_array_equal(thin[:, [0, 2]], concentrated[:, [0, 2]])
        np.testing.assert_allclose(thin[:, 1], concentrated[:, 1] * 0.1)
        np.testing.assert_array_equal(colors, thin_colors)

    def test_local_alignment_preserves_noise_and_untouched_stars(self):
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        from _alignment import attract_to_curves
        points = np.array([[0, 0.1, 0], [0, 0.5, 0], [0, 2, 0], [1.2, 0.1, 0]], dtype=np.float32)
        guide = np.array([[-1., 0, 0], [1., 0, 0]])
        moved, weights, _ = attract_to_curves(points, [guide], 0.6, 1)
        self.assertTrue((moved[:2, 1] < points[:2, 1]).all())
        self.assertTrue((moved[:2, 1] > 0).all())  # Retains scatter, never snaps.
        np.testing.assert_array_equal(moved[:, [0, 2]], points[:, [0, 2]])
        np.testing.assert_array_equal(moved[2], points[2])
        self.assertEqual(weights[2], 0)
        np.testing.assert_array_equal(moved[3], points[3])  # No endpoint pile-up.
        self.assertEqual(weights[3], 0)
        original = modules["noise_filaments"].generate(5000, 42)
        disabled = modules["noise_filaments_aligned"].generate(5000, 42, alignment=0)
        for a, b in zip(original, disabled):
            np.testing.assert_array_equal(a, b)
        aligned = modules["noise_filaments_aligned"].generate(5000, 42)
        np.testing.assert_array_equal(original[1], aligned[1])
        np.testing.assert_array_equal(original[2], aligned[2])
        distance = np.linalg.norm(original[0] - aligned[0], axis=1)
        self.assertGreater(np.count_nonzero(distance > 1e-6), 0)
        self.assertLessEqual(float(distance.max()), 0.6 * 0.35 + 1e-6)
        colored = modules["noise_filaments_aligned"].generate(5000, 42, color_alignment=1)
        np.testing.assert_array_equal(aligned[0], colored[0])
        np.testing.assert_array_equal(aligned[2], colored[2])

    def test_alignment_guides_follow_thin_layer_blend(self):
        worker.load_catalog(ROOT / "generators")
        from noise_filament_curves import build_curves
        from _curves import curve_length
        strict = build_curves(42, y_scale=0.1, min_length=0.7)
        layered = build_curves(42, y_scale=0.1, min_length=0.7, guide_continuity=1)
        # Regression for short B=0 cuts being used to align a relaxed A=0 layer.
        self.assertGreater(max(map(curve_length, layered)), 2 * max(map(curve_length, strict)))
        self.assertTrue(all(np.isfinite(curve).all() for curve in layered))
        full = build_curves(42, y_scale=1, guide_continuity=0)
        full_blend = build_curves(42, y_scale=1, guide_continuity=1)
        self.assertEqual(len(full), len(full_blend))
        for a, b in zip(full, full_blend):
            np.testing.assert_array_equal(a, b)

    def test_curve_extraction_and_regular_population(self):
        worker.load_catalog(ROOT / "generators")
        from _curves import intersect_fields, resample, bundle, allocate_counts
        axis = np.linspace(-1, 1, 32)
        x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
        curves = intersect_fields(x - 0.123, y + 0.177, np.ones(3))
        self.assertEqual(len(curves), 1)  # Shared tetrahedral faces stitch one whole line.
        stars = resample(curves[0], 101)
        np.testing.assert_allclose(stars[:, 0], 0.123, atol=1e-8)
        np.testing.assert_allclose(stars[:, 1], -0.177, atol=1e-8)
        np.testing.assert_allclose(np.abs(np.diff(stars[:, 2])), 0.02, atol=1e-8)
        circle = intersect_fields(x*x + y*y + z*z - 0.6**2, y - 0.017, np.ones(3))
        self.assertEqual(len(circle), 1)
        np.testing.assert_allclose(circle[0][0], circle[0][-1], atol=1e-8)
        for path in bundle(circle[0], 4, 0.03):
            np.testing.assert_allclose(path[0], path[-1], atol=1e-8)
            self.assertTrue(np.isfinite(path).all())
        counts = allocate_counts([10, 1, 0.1], 100, 20)
        self.assertEqual(counts.sum(), 100)
        self.assertTrue((counts >= 20).all())
        self.assertEqual(len(allocate_counts([10, 1, 0.1], 39, 20)), 1)
        np.testing.assert_array_equal(allocate_counts([10, 1], 1, 20), [1])

    def test_curve_colors_do_not_rearrange_stars(self):
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        module = modules["noise_filament_curves"]
        a, colors, sizes = module.generate(3000, 42)
        b, plain, sizes_b = module.generate(3000, 42, color_curves=0)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(sizes, sizes_b)
        self.assertGreater(len(np.unique(colors, axis=0)), 1)
        self.assertEqual(len(np.unique(plain, axis=0)), 1)

    def test_strand_continuity_limits_clump_gaps(self):
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        module = modules["noise_filaments"]
        knots = np.linspace(-1, 1, 100)
        original = np.exp(module._clump_log_weight(knots, 12, 0))
        filled = np.exp(module._clump_log_weight(knots, 12, 0.5))
        self.assertGreater(original.max() / original.min(), 1e6)
        self.assertLessEqual(filled.max() / filled.min(), 2.000001)
        np.testing.assert_array_equal(module._clump_log_weight(knots, 12, 1), np.zeros(100))
        # At full continuity, changing clump contrast cannot create new gaps.
        a = module.generate(1000, 42, strand_continuity=1, clumping=0)
        b = module.generate(1000, 42, strand_continuity=1, clumping=12)
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x, y)

    def test_noise_strands_share_junctions(self):
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        module = modules["noise_filaments_branches"]
        # Linear fields x/y/z have three perpendicular zero-intersection axes.
        # The added families must connect at the origin, without filling a void.
        t = np.linspace(-1, 1, 101)
        zero = np.zeros_like(t)
        for a, b, c in ((t, zero, zero), (zero, t, zero), (zero, zero, t)):
            density = np.exp(module._strand_log_density(a, b, c, 0.065, 1, 1))
            self.assertTrue((density >= 0.99).all())
        isolated = np.exp(module._strand_log_density(t, zero, zero, 0.065, 1, 0))
        self.assertLess(isolated[0], 1e-20)
        void = np.exp(module._strand_log_density(t * 0 + 1, t * 0 + 1,
                                                t * 0 + 1, 0.065, 1, 1))
        self.assertTrue((void < 1e-20).all())

    def test_layer_filaments_3d_structure_and_axis_scaling(self):
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        module = modules["layer_filaments"]
        thin, _, _ = module.generate(30000, 42, y_scale=0.6)
        isotropic, _, _ = module.generate(30000, 42, y_scale=6)
        np.testing.assert_array_equal(thin[:, [0, 2]], isotropic[:, [0, 2]])
        np.testing.assert_allclose(thin[:, 1] * 10, isotropic[:, 1], atol=1e-6)
        self.assertTrue((np.abs(thin) <= [6, 0.6, 6]).all())
        deviations = isotropic.std(axis=0)
        self.assertLess(deviations.max() / deviations.min(), 1.15)
        density = module._cellular_density(42, 6, 0.065, 0.65, 1.5, 0, resolution=48)
        a, b = density[:, 16, :].ravel(), density[:, 32, :].ravel()
        self.assertLess(abs(float(np.corrcoef(a, b)[0, 1])), 0.5)

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
        planar, _ = sample_density(np.ones((17, 17)), 100000, rng)
        self.assertEqual(planar.shape, (100000, 2))
        np.testing.assert_allclose(planar.mean(axis=0), 0, atol=0.01)
        np.testing.assert_allclose((planar * planar).mean(axis=0), 1 / 3, atol=0.01)
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
