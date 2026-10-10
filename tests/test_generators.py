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
    def test_triple_zero_graph_and_probabilistic_branches(self):
        worker.load_catalog(ROOT / "generators")
        from _branch_curves import intersection_graph, trace_graph
        axis = np.linspace(-1, 1, 9)
        x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
        fields = [x - .13, y + .17, z - .23]
        graph = intersection_graph(fields)
        vertices, edges, families, junctions = graph
        np.testing.assert_allclose(vertices[junctions], [[.13, -.17, .23]], atol=1e-12)
        joint = np.flatnonzero(junctions)[0]
        self.assertEqual(np.count_nonzero(edges == joint), 6)
        for family, pair in enumerate(((0, 1), (0, 2), (1, 2))):
            coordinates = vertices[edges[families == family]]
            for dimension in pair:
                np.testing.assert_allclose(coordinates[..., dimension], [.13, -.17, .23][dimension], atol=1e-12)
        plain = trace_graph(graph, 42, seed_count=1, length=8., branch_probability=0.)
        branched = trace_graph(graph, 42, seed_count=1, length=8., branch_probability=1.)
        self.assertEqual(set(plain[1]), {0})
        self.assertEqual(set(branched[1]), {0, 1, 2})
        for path in branched[0]:
            np.testing.assert_allclose(path[0], vertices[joint], atol=1e-12)
        for a, b in zip(plain[0], branched[0]):
            np.testing.assert_array_equal(a, b)
        # A fourth plane adds more triple crossings, not an imposed graph edge.
        four = intersection_graph(fields + [x + y + z - .35])
        self.assertEqual(four[3].sum(), 4)
        self.assertTrue(all(np.count_nonzero(four[1] == i) == 6 for i in np.flatnonzero(four[3])))

    def test_noise_branch_curve_preview(self):
        worker.load_catalog(ROOT / "generators")
        from noise_branch_curves import build_graph, generate
        from _branch_curves import trace_graph
        graph = build_graph(42)
        self.assertGreater(graph[3].sum(), 0)
        plain = trace_graph(graph, 42, branch_probability=0.)
        branched = trace_graph(graph, 42, branch_probability=1.)
        self.assertEqual(set(plain[1]), {0})
        self.assertGreater(len(branched[0]), len(plain[0]))
        self.assertEqual(set(branched[1]), {0, 1, 2})
        original = generate(1, 42)
        repeated = generate(1000000, 42)
        for a, b in zip(original, repeated):
            np.testing.assert_array_equal(a, b)
        for kind in (0, 1):
            result = generate(100, 42, noise_type=kind, field_count=4, y_scale=0, show_junctions=0)
            self.assertTrue(all(np.isfinite(a).all() for a in result))
            self.assertEqual(len(result[0]) % 2, 0)
            np.testing.assert_array_equal(result[0][:, 1], 0)
        with tempfile.TemporaryDirectory() as temp:
            result = worker.generate_request(dict(generator="noise_branch_curves", count=1, seed=42),
                                            ROOT / "generators", Path(temp) / "lines.bin")
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["primitive"], "lines")

    def test_grown_curve_geometry_and_branch_attachments(self):
        worker.load_catalog(ROOT / "generators")
        from grown_filaments import grow, generate
        params = dict(seed_count=2, arms=3, length=5., length_variation=0., y_scale=1.)
        straight, owners, centers = grow(42, turning=0, **params)
        self.assertEqual(len(straight), 6)
        for path, owner in zip(straight, owners):
            np.testing.assert_array_equal(path[0], centers[owner])
            steps = np.diff(path, axis=0)
            self.assertAlmostEqual(np.linalg.norm(steps, axis=1).sum(), 5.)
            np.testing.assert_allclose(np.cross(steps, steps[0]), 0, atol=1e-12)
        curved, _, _ = grow(42, **params)
        branched, _, _ = grow(42, branch_spacing=.1, **params)
        self.assertGreater(len(branched), len(curved))
        for a, b in zip(curved, branched):
            np.testing.assert_array_equal(a, b)  # Enabling branches preserves trunks.
        for i, child in enumerate(branched[len(curved):], len(curved)):
            self.assertTrue(any(np.any(np.all(parent == child[0], axis=1)) for parent in branched[:i]))
        flat, _, _ = grow(42, **dict(params, y_scale=0))
        for path, flattened in zip(curved, flat):
            np.testing.assert_array_equal(path[:, [0, 2]], flattened[:, [0, 2]])
            np.testing.assert_array_equal(flattened[:, 1], 0)
        a = generate(1, 42)
        b = generate(1000000, 42)
        for first, second in zip(a, b):
            np.testing.assert_array_equal(first, second)
        recolored = generate(100, 42, color_paths=0)
        np.testing.assert_array_equal(a[0], recolored[0])
        self.assertFalse(np.array_equal(a[1], recolored[1]))

    def test_line_preview_protocol_and_validation(self):
        import struct
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "lines.bin"
            response = worker.generate_request(dict(generator="grown_filaments", count=1, seed=42,
                params=dict(fade=1, pp_merge=1)), ROOT / "generators", output)
            self.assertTrue(response["ok"], response)
            self.assertEqual(response["primitive"], "lines")
            self.assertEqual(response["requested_count"], 1)
            self.assertEqual(response["count"] % 2, 0)
            self.assertNotIn("fade", response["params"])
            self.assertNotIn("pp_merge", response["params"])
            self.assertEqual(struct.unpack("<8sQ", output.read_bytes()[:16]), (b"FSTAR002", response["count"]))
            data = np.frombuffer(output.read_bytes()[16:], dtype="<f4").reshape(-1, 7)
            self.assertEqual(len(data), response["count"])
            self.assertTrue((np.linalg.norm(data[::2, :3] - data[1::2, :3], axis=1) < .1).all())
            root = Path(temp)
            for n in (0, 1, 3):
                (root / "invalid.py").write_text("import numpy as np\nPRIMITIVE = 'lines'\n"
                    f"def generate(count, seed):\n    return np.zeros(({n},3)), np.ones(({n},3))\n")
                result = worker.generate_request(dict(generator="invalid", count=10), root, output)
                self.assertFalse(result["ok"])
                self.assertIn("even vertex count", result["error"])

    def test_density_aware_fade_limits_edge_knots(self):
        from _postprocess import density_fade_weights, apply_to_stars
        rho = np.array([.1, 1., 100., 10000.])
        np.testing.assert_array_equal(density_fade_weights(1., rho), np.ones(4))
        np.testing.assert_array_equal(density_fade_weights(.2, rho, 0), np.full(4, .2))
        output = rho * density_fade_weights(.2, rho)
        self.assertTrue((output <= .2 / .8).all())
        self.assertTrue((np.diff(output) > 0).all())  # No inverted dense/sparse ordering.
        self.assertLess(output[-1] / output[-2], 1.02)  # Edge peaks saturate.
        self.assertLess((rho * density_fade_weights(.02, rho)).max(), output.max() / 8)

        rng = np.random.default_rng(12)
        dense = rng.normal(0, .015, (6000, 3)); dense[:, 0] = .8
        sparse = rng.uniform(-.6, .6, (3000, 3)); sparse[:, 0] = -.8
        center = rng.uniform(-.1, .1, (1000, 3))
        positions = np.vstack((dense, sparse, center)).astype(np.float32)
        colors = np.ones_like(positions)
        ids = np.arange(len(positions))
        bounds = ((0, 0, 0), (1, 1, 1))
        old = apply_to_stars(positions, colors, ids, 42,
                            dict(fade=1, fade_density_strength=0), bounds)[2]
        new = apply_to_stars(positions, colors, ids, 42,
                            dict(fade=1, fade_density_strength=1), bounds)[2]
        self.assertLess(np.count_nonzero(new < 6000), np.count_nonzero(old < 6000) * .1)
        self.assertGreater(np.count_nonzero((new >= 6000) & (new < 9000)), np.count_nonzero(new < 6000))
        np.testing.assert_array_equal(new[new >= 9000], np.arange(9000, 10000))
        # With a shared random stream, the new fade only removes more stars.
        self.assertTrue(np.isin(new, old).all())

    def test_swirl_flow_and_stable_guide_assignments(self):
        from _appearance import apply_appearance, swirl_warp, coherent_warp
        rng = np.random.default_rng(19)
        positions = rng.uniform(-4, 4, (4000, 3)).astype(np.float32)
        colors = rng.random(positions.shape).astype(np.float32)
        sizes = np.full(4000, .04, dtype=np.float32)
        self.assertIs(swirl_warp(positions, 0, 6), positions)
        twisted = swirl_warp(positions, 120, 6)
        np.testing.assert_array_equal(twisted[:, 1], positions[:, 1])
        np.testing.assert_allclose((twisted[:, [0, 2]]**2).sum(axis=1),
                                   (positions[:, [0, 2]]**2).sum(axis=1), rtol=3e-7)
        self.assertTrue((np.linalg.norm(twisted - positions, axis=1) > 0).all())
        np.testing.assert_allclose(swirl_warp(twisted, -120, 6), positions, atol=1e-6)
        params = dict(pp_curves=1, pp_curve_colors=1, pp_merge=1)
        base = apply_appearance(positions, colors, sizes, 42, params)
        for mode in (0, 1):
            result = apply_appearance(positions, colors, sizes, 42, dict(params, pp_warp=1, pp_flow_mode=mode))
            np.testing.assert_array_equal(result[1], base[1])
            np.testing.assert_array_equal(result[2], base[2])
            expected = swirl_warp(base[0], 120, 6) if mode == 0 else coherent_warp(base[0], 42, .2, 3.)
            np.testing.assert_array_equal(result[0], expected)

    def test_box_fade_width_and_native_control(self):
        from _postprocess import fade_density, edge_envelope
        density = np.ones((21, 21, 21))
        soft = fade_density(density, .8)
        narrow = fade_density(density, .2)
        # Equal distance to the nearest face, including outside the old sphere.
        self.assertAlmostEqual(soft[16, 16, 16], soft[16, 10, 10])
        self.assertGreater(soft[16, 16, 16], 0)
        self.assertLess(soft.sum(), narrow.sum())
        self.assertAlmostEqual(float(edge_envelope(.6, .8)), .5)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "stars.bin"
            for name in ("noise_clouds", "zeldovich"):
                a = worker.generate_request(dict(generator=name, count=5000, seed=42,
                    params=dict(fade=1, fade_width=.8)), ROOT / "generators", output)
                self.assertTrue(a["ok"], a)
                first = output.read_bytes()
                b = worker.generate_request(dict(generator=name, count=5000, seed=42,
                    params=dict(fade=1, fade_width=.2)), ROOT / "generators", output)
                self.assertTrue(b["ok"], b)
                self.assertNotEqual(first, output.read_bytes())
                self.assertEqual(b["params"]["fade_width"], .2)

    def test_appearance_toggles_and_sparse_alignment(self):
        from _appearance import apply_appearance, neighbor_spacing
        rng = np.random.default_rng(21)
        positions = np.vstack((rng.normal(0, .03, (500, 3)), rng.uniform(-2, 2, (4000, 3)))).astype(np.float32)
        colors = rng.random(positions.shape).astype(np.float32)
        sizes = np.full(len(positions), .04, dtype=np.float32)
        original = (positions, colors, sizes)
        for a, b in zip(original, apply_appearance(*original, 42, {})):
            self.assertIs(a, b)
        params = dict(pp_curves=1, pp_curve_reach=.5, pp_curve_strength=.9, pp_sparse_fraction=.7)
        moved = apply_appearance(*original, 42, params)
        spacing = neighbor_spacing(positions)[1]
        dense = spacing < np.quantile(spacing, .3)
        np.testing.assert_array_equal(moved[0][dense], positions[dense])
        distance = np.linalg.norm(moved[0] - positions, axis=1)
        self.assertGreater(np.count_nonzero(distance > .001), 200)
        self.assertLessEqual(distance.max(), .5 * .9 + 1e-6)
        np.testing.assert_array_equal(moved[1], colors)
        np.testing.assert_array_equal(moved[2], sizes)
        colored = apply_appearance(*original, 42, dict(params, pp_curve_colors=1))
        np.testing.assert_array_equal(moved[0], colored[0])
        self.assertGreater(np.count_nonzero(colored[1] != colors), 100)

    def test_dense_merge_conserves_volume_and_centroid(self):
        from _appearance import apply_appearance
        rng = np.random.default_rng(51)
        positions = rng.normal(0, .08, (2000, 3)).astype(np.float32)
        colors = rng.random(positions.shape).astype(np.float32)
        sizes = rng.uniform(.02, .06, len(positions)).astype(np.float32)
        p, c, s = apply_appearance(positions, colors, sizes, 42,
                                  dict(pp_merge=1, pp_merge_distance=.15, pp_dense_fraction=1))
        self.assertLess(len(p), len(positions) // 2)
        self.assertGreater(s.max(), sizes.max())
        before, after = sizes.astype(float)**3, s.astype(float)**3
        np.testing.assert_allclose(before.sum(), after.sum(), rtol=1e-6)
        np.testing.assert_allclose((positions * before[:, None]).sum(axis=0),
                                   (p * after[:, None]).sum(axis=0), atol=1e-8)
        np.testing.assert_allclose((colors * before[:, None]).sum(axis=0),
                                   (c * after[:, None]).sum(axis=0), atol=1e-8)

    def test_combined_appearance_worker_and_tiny_clouds(self):
        from _appearance import apply_appearance
        params = dict(pp_curves=1, pp_curve_colors=1, pp_merge=1, pp_warp=1)
        for count in (1, 2, 10):
            p = np.zeros((count, 3), dtype=np.float32)
            result = apply_appearance(p, np.ones_like(p), np.full(count, .04), 42, params)
            self.assertGreater(len(result[0]), 0)
            self.assertTrue(all(np.isfinite(a).all() for a in result))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "stars.bin"
            request = dict(generator="zeldovich", count=10000, seed=42, params=dict(params, fade=1))
            result = worker.generate_request(request, ROOT / "generators", output)
            self.assertTrue(result["ok"], result)
            first = output.read_bytes()
            repeated = worker.generate_request(request, ROOT / "generators", output)
            self.assertTrue(repeated["ok"], repeated)
            self.assertEqual(first, output.read_bytes())
            self.assertLess(result["count"], 10000)

    def test_soft_cutoff_preserves_peak_contrast(self):
        from _postprocess import suppress_voids
        # Mean exactly 1: compare dilute voids with two well-above-threshold peaks.
        density = np.array([0.1] * 100 + [10., 20.] + [63.])
        self.assertEqual(density.mean(), 1)
        filtered = suppress_voids(density, 1)
        self.assertLess(filtered[0] / density[0], .01)
        self.assertGreater(filtered[-3] / density[-3], .99)
        # A 2:1 peak ratio remains about 2:1, rather than becoming 4:1.
        self.assertAlmostEqual(filtered[-2] / filtered[-3], 2, delta=.02)
        self.assertTrue((filtered <= density).all())
        self.assertIs(suppress_voids(density, 0), density)
        np.testing.assert_array_equal(suppress_voids(np.zeros(3), 1), np.zeros(3))

    def test_shared_edge_fade_preserves_survivors(self):
        from _postprocess import apply_to_stars, edge_envelope
        np.testing.assert_allclose(edge_envelope(np.array([0, .7, .85, 1, 2]), width=.3), [1, 1, .5, 0, 0])
        rng = np.random.default_rng(42)
        positions = rng.uniform(-1, 1, (20000, 3)).astype(np.float32)
        colors = rng.random((20000, 3)).astype(np.float32)
        sizes = np.arange(20000, dtype=np.float32) + 1
        disabled = apply_to_stars(positions, colors, sizes, 42, {"fade": 0})
        self.assertIs(disabled[0], positions)
        bounds = ((0, 0, 0), (1, 1, 1))
        a = apply_to_stars(positions, colors, sizes, 42, {"fade": 1}, bounds)
        b = apply_to_stars(positions, colors, sizes, 42, {"fade": 1}, bounds)
        ids = a[2].astype(int) - 1
        self.assertGreater(len(ids), 1000)
        self.assertLess(len(ids), len(positions))
        self.assertTrue((np.max(np.abs(a[0]), axis=1) < 1).all())
        for actual, original, repeat in zip(a, (positions, colors, sizes), b):
            np.testing.assert_array_equal(actual, original[ids])
            np.testing.assert_array_equal(actual, repeat)
        core = np.flatnonzero(np.max(np.abs(positions), axis=1) <= .2)
        self.assertTrue(np.isin(core, ids).all())

    def test_shared_edge_fade_worker_and_native_delegation(self):
        import struct
        catalog, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        for entry in catalog:
            self.assertEqual(sum(p["key"] == "fade" for p in entry["parameters"]),
                             0 if entry["primitive"] == "lines" else 1)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "stars.bin"
            for name in ("galaxy", "filaments", "zeldovich", "noise_filament_curves"):
                result = worker.generate_request(dict(generator=name, count=5000, seed=42,
                    params={"fade": 1}), ROOT / "generators", output)
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["requested_count"], 5000)
                self.assertGreater(result["count"], 0)
                self.assertLess(result["count"], 5000)
                self.assertEqual(struct.unpack('<8sQ', output.read_bytes()[:16]),
                                 (b'FSTAR002', result["count"]))
                self.assertEqual(output.stat().st_size, 16 + 28 * result["count"])
            # A density generator retains its own sampling and is not faded twice.
            result = worker.generate_request(dict(generator="noise_clouds", count=5000,
                seed=42, params={"fade": 1}), ROOT / "generators", output)
            self.assertTrue(result["ok"], result)
            expected = modules["noise_clouds"].generate(5000, 42, fade=1)
            actual = np.frombuffer(output.read_bytes()[16:], dtype='<f4').reshape(-1, 7)
            np.testing.assert_array_equal(actual, np.column_stack(expected).astype(np.float32))

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
        initial, _, _ = module.generate(50000, 42, evolution=0, void_threshold=0)
        np.testing.assert_allclose(initial.mean(axis=0), 0, atol=0.02)
        np.testing.assert_allclose((initial * initial).mean(axis=0), 12, atol=0.05)
        middle, colors, sizes = module.generate(50000, 42, evolution=0.5, void_threshold=0)
        later, _, _ = module.generate(50000, 42, evolution=1, void_threshold=0)
        # q + D*s(q) is linear in D, accounting for periodic box crossings.
        residual = (later - 2*middle + initial + 6) % 12 - 6
        np.testing.assert_allclose(residual, 0, atol=4e-6)
        thin, thin_colors, thin_sizes = module.generate(50000, 42, evolution=0.5, y_scale=0.1, void_threshold=0)
        np.testing.assert_array_equal(thin[:, [0, 2]], middle[:, [0, 2]])
        np.testing.assert_allclose(thin[:, 1], middle[:, 1] * 0.1)
        np.testing.assert_array_equal(thin_colors, colors)
        np.testing.assert_array_equal(thin_sizes, sizes)
        self.assertTrue((np.abs(later) <= 6).all())

    def test_zeldovich_soft_cutoff_suppresses_voids(self):
        _, modules, _ = worker.load_catalog(ROOT / "generators")
        module = modules["zeldovich"]
        base, _, sizes = module.generate(100000, 42, void_threshold=0)
        concentrated, colors, concentrated_sizes = module.generate(100000, 42, void_threshold=1)
        strong, _, _ = module.generate(100000, 42, void_threshold=2)
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
        thin, thin_colors, _ = module.generate(100000, 42, void_threshold=1, y_scale=0.1)
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
            plain_radius = np.max(np.abs(plain / scale), axis=1)
            faded_radius = np.max(np.abs(faded / scale), axis=1)
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
            if entry["primitive"] == "lines":
                continue  # Geometry-controlled counts covered by the line preview tests.
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
