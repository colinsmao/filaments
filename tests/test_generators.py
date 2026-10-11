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
    def test_curve_coverage_counts_length_and_original_density_capacity(self):
        worker.load_catalog(ROOT / 'generators')
        from _curve_coverage import CurveCoverage
        u = np.linspace(-1, 1, 32)
        x, y, z = np.meshgrid(u*4, u*0, u*2, indexing='ij')
        blobs = np.exp(-((x-2)**2+z*z)/.4)+np.exp(-((x+2)**2+z*z)/.4)
        bridge = np.exp(-z*z/.03)*np.exp(-(x/2.3)**8)
        low = CurveCoverage(blobs+.01*bridge, [4., 0., 2.], .25, 100.)
        high = CurveCoverage(blobs+.2*bridge, [4., 0., 2.], .25, 100.)
        scaled = CurveCoverage(7*(blobs+.01*bridge), [4., 0., 2.], .25, 100.)
        np.testing.assert_allclose(low.target, scaled.target)
        self.assertAlmostEqual(low.target.sum(), 100.)
        a, b = np.array([[-.5, 0., 0.]]), np.array([[.5, 0., 0.]])
        for field in (low, high):
            field.deposit(a, b)
            field.refresh()
            self.assertAlmostEqual(field.deposited.sum(), 1.)
        load_low = low.sample(np.zeros((1, 3)))[0][0]
        load_high = high.sample(np.zeros((1, 3)))[0][0]
        self.assertGreater(load_low, 3*load_high)
        # The same traffic consumes more capacity in the weaker bridge.
        split = CurveCoverage(blobs+.01*bridge, [4., 0., 2.], .25, 100.)
        p = np.column_stack((np.linspace(-.5, .5, 101), np.zeros((101, 2))))
        split.deposit(p[:-1], p[1:])
        self.assertAlmostEqual(split.deposited.sum(), low.deposited.sum())

    def test_curve_coverage_filling_births_prefer_remaining_material(self):
        worker.load_catalog(ROOT / 'generators')
        from _curve_coverage import CurveCoverage
        field = CurveCoverage(np.ones((24, 24, 24)), [2., 0., 2.], .2, 40.)
        field.deposited[:] = field.target
        field.deposited[:24] = 0
        field.refresh()
        roots = field.roots(1000, np.random.default_rng(42))
        self.assertGreater(np.mean(roots[:, 0] < 0), .85)
        np.testing.assert_array_equal(roots[:, 1], 0.)
        self.assertTrue((np.abs(roots[:, [0, 2]]) <= 2).all())

    def test_curve_capacity_limits_growth_and_fill_is_repeatable(self):
        worker.load_catalog(ROOT / 'generators')
        from _density_curves import trace_density
        density = np.ones((24, 24, 24))
        params = dict(strand_count=32, strand_length=3., direction_scale=.2,
                      density_pull=0., curve_wander=0., join_strength=0., coverage_radius=.4)
        small = trace_density(density, 42, [2., 0., 2.], coverage_mode=1, capacity_scale=.1, **params)
        large = trace_density(density, 42, [2., 0., 2.], coverage_mode=1, capacity_scale=3., **params)
        length = lambda paths: sum(np.linalg.norm(np.diff(p, axis=0), axis=1).sum() for p in paths)
        self.assertLess(length(small), .8*length(large))
        first = trace_density(density, 42, [2., 0., 2.], coverage_mode=2, **params)
        again = trace_density(density, 42, [2., 0., 2.], coverage_mode=2, **params)
        self.assertEqual(len(first), len(again))
        for a, b in zip(first, again):
            np.testing.assert_array_equal(a, b)
            self.assertTrue(np.isfinite(a).all())
            self.assertTrue((np.abs(a) <= [2., 0., 2.]).all())

    def test_density_contacts_exclude_self_crossings_and_distant_paths(self):
        worker.load_catalog(ROOT / 'generators')
        from _density_curves import StrandContacts
        line = np.array([[0., 0, 0], [2., 0, 0]])
        index = StrandContacts([line, line[::-1], line+[0., 1., 0.]])
        points = np.array([[1., .1, 0.]]*4)
        headings = np.array([[1., 0, 0], [-1., 0, 0], [0., 0, 1.], [1., 0, 0]])
        target, tangent, distance = index.query(points, headings, np.array([2, 2, 2, 0]), .3)
        np.testing.assert_allclose(distance[:2], .1)
        np.testing.assert_allclose(target[:2], [[1., 0, 0.]]*2)
        np.testing.assert_array_equal(tangent[:2], headings[:2])
        self.assertTrue(np.isinf(distance[2:]).all())

    def test_density_joined_growth_retains_roots_and_meets_deposited_geometry(self):
        worker.load_catalog(ROOT / 'generators')
        from _density_curves import trace_density
        x, y, z = np.meshgrid(*[np.linspace(-1, 1, 24)]*3, indexing='ij')
        density = np.exp(-z*z/(2*.08**2))
        args = dict(strand_count=32, strand_length=2., direction_scale=.15, curve_wander=0.)
        independent = trace_density(density, 42, [2., 0., 2.], join_strength=0., **args)
        disabled = trace_density(density, 42, [2., 0., 2.], join_reach=0., **args)
        joined = trace_density(density, 42, [2., 0., 2.], **args)
        self.assertEqual(len(joined), len(independent))
        for a, b, c in zip(independent, disabled, joined):
            np.testing.assert_array_equal(a, b)
            # At least the shared launch vertex survives unchanged.
            self.assertTrue((np.linalg.norm(a[:, None]-c[None], axis=2) < 1e-10).any())
        length = lambda paths: sum(np.linalg.norm(np.diff(p, axis=0), axis=1).sum() for p in paths)
        self.assertLess(length(joined), length(independent))
        hits = 0
        for i, path in enumerate(joined):
            a = np.concatenate([p[:-1] for j, p in enumerate(joined) if i != j])
            d = np.concatenate([np.diff(p, axis=0) for j, p in enumerate(joined) if i != j])
            for endpoint in path[[0, -1]]:
                u = np.clip(np.sum((endpoint-a)*d, axis=1)/np.maximum(np.sum(d*d, axis=1), 1e-20), 0, 1)
                hits += np.min(np.linalg.norm(endpoint-a-u[:, None]*d, axis=1)) < 1e-8
        self.assertGreater(hits, 0)

    def test_overlap_thinning_distinct_curves_and_reversed_directions(self):
        worker.load_catalog(ROOT / 'generators')
        from _curve_overlap import thin_parallel_curves
        x = np.linspace(0, 5, 101)
        paths = [np.column_stack((x, x*0, x*0+offset)) for offset in (0, .04, .08)]
        paths[1] = paths[1][::-1].copy()
        np.testing.assert_array_equal(thin_parallel_curves(paths, .2, 1), [0])
        # Many nearby segments from ONE retained curve cannot fill allowance 2.
        np.testing.assert_array_equal(thin_parallel_curves(paths, .2, 2), [0, 1])
        np.testing.assert_array_equal(thin_parallel_curves(paths, 0, 1), [0, 1, 2])

    def test_overlap_thinning_keeps_crossings_height_and_unique_extensions(self):
        worker.load_catalog(ROOT / 'generators')
        from _curve_overlap import thin_parallel_curves
        primary = np.array([[0., 0, 0], [10., 0, 0]])
        duplicate = np.array([[0., 0, .04], [7., 0, .04]])
        extension = np.array([[3., 0, .04], [7., 0, .04], [7., 0, 3.]])
        crossing = np.array([[5., 0, -2.], [5., 0, 2.]])
        above = primary + [0., 1., 0.]
        paths = [primary, duplicate, extension, crossing, above]
        original = [p.copy() for p in paths]
        np.testing.assert_array_equal(thin_parallel_curves(paths, .2, 1), [0, 2, 3, 4])
        for a, b in zip(paths, original):
            np.testing.assert_array_equal(a, b)

    def test_overlap_thinning_measures_arc_length_not_vertices(self):
        worker.load_catalog(ROOT / 'generators')
        from _curve_overlap import thin_parallel_curves
        primary = np.array([[0., 0, 0], [10., 0, 0]])
        # Almost all vertices overlap, but half the physical length diverges.
        x = np.linspace(0., 4., 1000)
        candidate = np.vstack((np.column_stack((x, x*0, x*0+.04)), [4., 0., 4.04]))
        np.testing.assert_array_equal(thin_parallel_curves([primary, candidate], .2, 1), [0, 1])

    def test_density_shape_follows_physical_tube_and_ring(self):
        worker.load_catalog(ROOT / 'generators')
        from _density_curves import DensityShape
        half = np.array([2., .5, 2.])
        axes = [np.linspace(-v, v, 48) for v in half]
        x, y, z = np.meshgrid(*axes, indexing='ij')
        tube = np.exp(-(y*y+z*z)/(2*.18**2))
        field = DensityShape(tube, half, .12)
        tangent, grad, confidence = field.sample(np.array([[0., 0., 0.], [.3, .1, .1]]))
        self.assertTrue((np.abs(tangent[:, 0]) > .999).all())
        self.assertTrue((confidence > .9).all())
        self.assertLess(grad[1, 1], 0.)
        self.assertLess(grad[1, 2], 0.)
        ring = np.exp(-((np.hypot(x, z)-1)**2+y*y)/(2*.12**2))
        field = DensityShape(ring, half, .1)
        q = np.array([[2**-.5, 0., 2**-.5]])
        tangent, _, _ = field.sample(q)
        expected = np.array([-2**-.5, 0., 2**-.5])
        self.assertGreater(abs(tangent[0]@expected), .99)

    def test_density_strands_flat_bounds_and_determinism(self):
        worker.load_catalog(ROOT / 'generators')
        from _density_curves import trace_density
        x, y, z = np.meshgrid(*[np.linspace(-1, 1, 24)]*3, indexing='ij')
        density = np.exp(-z*z/(2*.15**2))
        args = dict(strand_count=24, strand_length=.8, direction_scale=.15, join_strength=0.)
        for half in ([2., 0., 2.], [2., 1e-5, 2.]):
            first = trace_density(density, 42, half, **args)
            second = trace_density(density, 42, half, **args)
            self.assertEqual(len(first), len(second))
            for a, b in zip(first, second):
                np.testing.assert_array_equal(a, b)
                self.assertTrue(np.isfinite(a).all())
                self.assertTrue((np.abs(a) <= np.array(half)+1e-9).all())
                self.assertLessEqual(np.linalg.norm(np.diff(a, axis=0), axis=1).sum(), 1.2+1e-8)
                np.testing.assert_array_equal(a[:, 1], np.full(len(a), a[0, 1]))

    def test_density_strands_worker_and_population_independence(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'points.bin'
            params = dict(strand_count=24, strand_length=1., y_scale=.2, pop_taper=0)
            def run(density):
                response = worker.generate_request(dict(generator='density_filament_curves', count=100,
                    seed=42, params=dict(params, pop_density=density)), ROOT/'generators', output)
                self.assertTrue(response['ok'], response)
                self.assertTrue(response['population'])
                return output.read_bytes(), output.with_suffix('.stars.bin').read_bytes()
            lines, stars = run(4.)
            same_lines, more_stars = run(8.)
            self.assertEqual(lines, same_lines)
            self.assertNotEqual(stars, more_stars)

    def test_centerline_selection_preserves_discovered_connections(self):
        worker.load_catalog(ROOT / 'generators')
        from _centerline_selection import select_centerlines
        blobs = np.array([[0., 0., 0.], [2., 1., 0.]])
        direct = np.linspace(blobs[0], blobs[1], 12)
        curved = direct.copy()
        curved[:, 2] = .5*np.sin(np.linspace(0, np.pi, 12))
        free_a = np.array([[5., 0, 0], [6., 0, 0]])
        free_b = np.array([[5., 0, 0], [4., 0, 0]])
        report = dict(initial_groups=np.array([0, 1, 2, 2]),
                      captured=np.array([1, 0, -1, -1]),
                      half_paths=[curved, direct[::-1], free_a, free_b])
        paths, groups, stats = select_centerlines(blobs, report, open_count=1)
        self.assertEqual(stats['blob_pairs'], [(0, 1)])
        self.assertEqual(stats['selected_ids'], [1, 2])
        self.assertEqual(len(paths), 2)
        np.testing.assert_array_equal(paths[0][[0, -1]], blobs[::-1]*[1, .35, 1])
        np.testing.assert_array_equal(paths[1][[0, -1]], [[4., 0, 0], [6., 0, 0]])
        # Captures are required: proximity alone must never invent a link.
        report['captured'][:] = -1
        with self.assertRaisesRegex(ValueError, 'No centerlines'):
            select_centerlines(blobs, report, open_count=0)

    def test_guided_walk_chooses_one_guide_and_holds_it(self):
        worker.load_catalog(ROOT / 'generators')
        from _guided_walk import choose_guides
        scores = np.array([[0., .01, 1.], [0., 1., .01], [0., 0., 0.]])
        kinds = np.array([0, 1, 2])
        owners = np.array([[-1, 0, 5]]*3)
        pick, kind, owner, held = choose_guides(scores, kinds, owners, np.array([1, 2, 0]),
            np.array([0, 5, -1]), np.array([1., 1., 0]), np.random.default_rng(42), 0)
        np.testing.assert_array_equal(pick[:2], [1, 2])  # Keep even the weaker guide until its hold expires.
        np.testing.assert_array_equal(kind, [1, 2, 0])
        np.testing.assert_array_equal(owner, [0, 5, -1])
        np.testing.assert_array_equal(held, [True, True, False])
        _, free_kind, _, _ = choose_guides(scores, kinds, owners, np.zeros(3, dtype=int),
            np.full(3, -1), np.zeros(3), np.random.default_rng(42), 1.)
        np.testing.assert_array_equal(free_kind, 0)

    def test_guided_walk_segment_candidates_are_local_and_deduplicated(self):
        worker.load_catalog(ROOT / 'generators')
        from _guided_walk import SegmentIndex
        path = np.column_stack((np.zeros(12), np.zeros(12), np.linspace(0, 2, 12)))
        index = SegmentIndex([path], np.array([7]))
        p = np.array([[.2, 0, 1.], [.2, 0, 1.], [5., 0, 1.], [.2, 0, 1.]])
        h = np.array([[0., 0, 1.], [0., 0, 1.], [0., 0, 1.], [1., 0, 0]])
        score, guide, owners = index.candidates(p, h, np.array([0, 7, 0, 0]), 1.)
        self.assertEqual(np.count_nonzero(score[0]), 1)
        np.testing.assert_array_equal(score[1:], 0.)
        chosen = np.argmax(score[0])
        self.assertLess(guide[0, chosen, 0], 0)
        self.assertGreater(guide[0, chosen, 2], 0)

    def test_guided_walk_free_starts_lengths_and_blob_arrivals(self):
        worker.load_catalog(ROOT / 'generators')
        from _guided_walk import walk
        params = dict(blob_count=0, free_filaments=4, wandering=0, guide_strength=0,
                      length=10., length_variation=0, y_scale=1.)
        paths, blobs, groups, report = walk(42, **params)
        self.assertEqual(blobs.shape, (0, 3))
        self.assertEqual(len(paths), 4)
        for i, path in enumerate(paths):
            self.assertAlmostEqual(np.linalg.norm(np.diff(path, axis=0), axis=1).sum(), 10., places=8)
            direction = (path[-1]-path[0])/np.linalg.norm(path[-1]-path[0])
            self.assertLess(np.linalg.norm(np.cross(path-path[0], direction), axis=1).max(), 1e-10)
            np.testing.assert_array_equal(path[0], report['half_paths'][2*i+1][-1])
            np.testing.assert_array_equal(path[-1], report['half_paths'][2*i][-1])
        single = walk(42, blob_count=1, curves_per_blob=2, free_filaments=0, length=2., capture_radius=100.)
        self.assertEqual(single[3]['captures'], 0)  # Source blob cannot recapture its walks.
        first = walk(42)
        repeated = walk(42)
        self.assertGreater(first[3]['captures'], 0)
        self.assertGreater(first[3]['following_steps'], 0)
        for a, b in zip(first[0], repeated[0]):
            np.testing.assert_array_equal(a, b)
        for i, target in enumerate(first[3]['captured']):
            if target >= 0:
                endpoint = np.asarray(first[3]['half_paths'][i][-1])*[1., .35, 1.]
                np.testing.assert_array_equal(endpoint, first[1][target])
                self.assertNotEqual(first[3]['initial_groups'][i], target)

    def test_guided_walk_shared_population_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'points.bin'
            params = dict(blob_count=2, curves_per_blob=2, free_filaments=2, length=3., pop_taper=0)
            def run(changes):
                response = worker.generate_request(dict(generator='guided_walk_filaments', count=100, seed=42,
                    params=dict(params, **changes)), ROOT / 'generators', output)
                self.assertTrue(response['ok'], response)
                self.assertTrue(response['population'])
                return output.read_bytes(), output.with_suffix('.stars.bin').read_bytes()
            lines, stars = run({})
            without_markers, same_stars = run(dict(show_seeds=0))
            self.assertNotEqual(lines, without_markers)
            self.assertEqual(stars, same_stars)
            same_lines, more_stars = run(dict(pop_density=8))
            self.assertEqual(lines, same_lines)
            self.assertNotEqual(stars, more_stars)
            run(dict(blob_count=0, noise_type=1, y_scale=0))
            run(dict(curves_per_blob=0))  # Blobs can be attractors without launching walks.

    def test_emergent_interactions_are_local_and_exclude_own_blob(self):
        worker.load_catalog(ROOT / 'generators')
        from _emergent_network import Corridors
        corridor = Corridors([np.array([[0., 0., 0.], [0., 0., 2.]])], [1])
        positions = np.array([[.2, 0, 1.], [.2, 0, 1.], [5., 0, 1.], [.2, 0, 1.], [.2, 0, 1.]])
        headings = np.array([[0., 0, 1.], [0., 0, 1.], [0., 0, 1.], [1., 0, 0], [0., 0, -1.]])
        force, distance, target, owner = corridor.query(positions, headings, np.array([0, 1, 0, 0, 0]), .8)
        self.assertLess(force[0, 0], 0)
        np.testing.assert_array_equal(force[1:4], 0.)
        np.testing.assert_allclose(force[4], force[0])
        self.assertAlmostEqual(distance[0], .2)
        np.testing.assert_array_equal(target[0], [0., 0., 1.])
        self.assertEqual(owner[0], 0)
        self.assertTrue(np.isinf(distance[1:4]).all())
        np.testing.assert_array_equal(corridor.query(positions, headings, np.zeros(5), 0)[0], 0.)

    def test_emergent_tail_trimming_preserves_local_attachments(self):
        from _emergent_network import trim_contact_tails
        paths = [[np.array([0., 0, z]) for z in (0., .5, 1., 1.5, 2.)],
                 [np.array([1., 0, .8]), np.array([0., 0, .8])],
                 [np.array([-1., 0, 1.2]), np.array([0., 0, 1.2])]]
        trim_contact_tails(paths, [(1, 'curve', 0, 1), (2, 'curve', 0, 1)])
        np.testing.assert_array_equal(paths[0][-1], [0., 0, 1.2])
        self.assertEqual(len(paths[0]), 4)
        # A receiver that itself reaches a blob must retain its onward connection.
        before = [p.copy() for p in paths[0]]
        trim_contact_tails(paths, [(1, 'curve', 0, 1), (0, 'blob', 2, 3)])
        np.testing.assert_array_equal(paths[0], before)

    def test_emergent_growth_repeats_without_feedback_and_has_exact_contacts(self):
        from _emergent_network import grow_network
        params = dict(seed_count=4, curves_per_seed=1, length=7., unsupported_survival=1., y_scale=1., reinforcement=0)
        first = grow_network(42, passes=1, **params)
        second = grow_network(42, passes=2, **params)
        for a, b in zip(first[0], second[0]):
            np.testing.assert_array_equal(a, b)
        for path, origin in zip(first[0], first[2]):
            np.testing.assert_array_equal(path[0], first[1][origin])
            self.assertTrue(np.isfinite(path).all())
        paths, nodes, origins, report = grow_network(42, seed_count=10, curves_per_seed=2, length=16., passes=1,
                                                     unsupported_survival=0., y_scale=1.)
        self.assertGreater(len(report['contacts']), 0)
        retained = set(report['retained'])
        for source, kind, target, _ in report['contacts']:
            self.assertIn(source, retained)
            point = np.array(report['all_paths'][source][-1])
            if kind == 'blob':
                np.testing.assert_array_equal(point, nodes[target])
            else:
                self.assertIn(target, retained)
                self.assertNotEqual(report['origins'][source], report['origins'][target])
                path = np.array(report['all_paths'][target])
                d = np.diff(path, axis=0)
                t = np.clip(np.sum((point-path[:-1])*d, axis=1)/np.maximum(np.sum(d*d, axis=1), 1e-20), 0, 1)
                self.assertLess(np.linalg.norm(path[:-1]+t[:, None]*d-point, axis=1).min(), 1e-8)

    def test_emergent_generator_reuses_star_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'points.bin'
            params = dict(seed_count=2, curves_per_seed=1, length=3., passes=1, show_seeds=1, pop_taper=0)
            def run(changes):
                response = worker.generate_request(dict(generator='emergent_filaments', count=100,
                    seed=42, params=dict(params, **changes)), ROOT / 'generators', output)
                self.assertTrue(response['ok'], response)
                self.assertTrue(response['population'])
                return output.read_bytes(), output.with_suffix('.stars.bin').read_bytes()
            curves, stars = run({})
            hidden_markers, same_stars = run(dict(show_seeds=0))
            self.assertNotEqual(curves, hidden_markers)
            self.assertEqual(stars, same_stars)
            same_curves, more_stars = run(dict(pop_density=8))
            self.assertEqual(curves, same_curves)
            self.assertNotEqual(stars, more_stars)

    def test_seed_pairing_uses_actual_routes_and_facing_directions(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import seed_routes
        # Same AB label is insufficient: the third seed is on a disconnected arm.
        # The connected route bends sideways, so this is not a nearest-seed line.
        vertices = np.array([[0., 0, 0], [0, 0, 1], [2, 0, 2], [0, 0, 4],
                             [0, 0, 5], [0, 0, 6], [0, 0, 7], [0, 1, 0]])
        edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4], [5, 6], [0, 7]])
        families = np.array([0, 0, 0, 0, 0, 1])
        graph = vertices, edges, families, np.ones(len(vertices), dtype=bool)
        gradients = np.broadcast_to(np.eye(3), (3, 3, 3))
        routes = seed_routes(graph, [0, 3, 5], np.tile([0, 1, 2], (3, 1)), gradients, 3)
        self.assertEqual(len(routes), 1)
        a, sa, b, sb, distance = routes[0]
        self.assertEqual((a, sa, b, sb), (0, 0, 1, 1))
        self.assertGreater(distance, 4.)  # Measured along the noise route.

    def test_paired_launches_are_reciprocal_sparse_and_bounded(self):
        from _stochastic_curves import paired_launch_plans, launch_plan
        routes = [(0, 0, 1, 1, 3.), (0, 2, 2, 3, 4.), (0, 4, 3, 5, 5.)]
        plans = paired_launch_plans(42, 16, 4, routes, 4.)
        self.assertEqual(plans, paired_launch_plans(42, 16, 4, routes, 4.))
        larger = paired_launch_plans(42, 24, 4, routes, 4.)
        for small, large in zip(plans, larger):
            self.assertEqual(small, large[:len(small)])
            self.assertGreaterEqual(len(small), 1)
            self.assertLessEqual(len({slot // 2 for _, slot in small}), 2)
        counts = np.array([np.bincount([s for _, s in p], minlength=6) for p in plans])
        self.assertEqual(np.count_nonzero(counts[0] >= 8), 2)  # Never all three busy pairs.
        for a, sa, b, sb, _ in routes:
            if counts[a, sa] >= 8:
                self.assertEqual([c for c, s in plans[a] if s == sa], [c for c, s in plans[b] if s == sb])
                self.assertGreater(counts[a, sa], counts[a, sa ^ 1] + 5)
        disabled = paired_launch_plans(42, 16, 4, routes, 4., bias=0)
        self.assertEqual(disabled, [launch_plan(42, r, 16) for r in range(4)])
        self.assertEqual(paired_launch_plans(42, 16, 1, [], 4.), [launch_plan(42, 0, 16)])
        sparse = paired_launch_plans(42, 16, 4, [], 4.)
        self.assertLess(sum(map(len, sparse)), sum(map(len, disabled)) / 2)

    def test_attraction_distance_and_noise_modulation(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import AttractionModulation
        points = np.array([[0., 0, 0], [4., 0, 0], [4000., 0, 0]])
        origin = np.zeros(3)
        distance = AttractionModulation(42, distance_effect=.8, distance_scale=4.)
        np.testing.assert_allclose(distance.factors(points, origin), [1., .6, .2], atol=1e-6)
        stronger = AttractionModulation(42, distance_effect=-.8, distance_scale=4.)
        np.testing.assert_allclose(stronger.factors(points, origin), [1., 1.4, 1.8], atol=1e-6)
        np.testing.assert_array_equal(distance.factors(points + 7, origin + 7), distance.factors(points, origin))
        points = np.random.default_rng(4).uniform(-10, 10, (100, 3))
        for noise_type in (0, 1):
            settings = dict(noise_strength=.9, noise_scale=3., noise_type=noise_type)
            noise = AttractionModulation(42, **settings)
            factors = noise.factors(points, origin)
            np.testing.assert_array_equal(factors, AttractionModulation(42, **settings).factors(points, origin + 5))
            self.assertTrue(((factors > .1) & (factors < 1.9)).all())
            self.assertGreater(np.std(factors), .1)
            self.assertLess(np.max(np.abs(factors - noise.factors(points + 1e-4, origin))), .002)
            self.assertFalse(np.array_equal(factors, AttractionModulation(43, **settings).factors(points, origin)))
            combined = AttractionModulation(42, distance_effect=.8, distance_scale=4., **settings)
            np.testing.assert_allclose(combined.factors(points, origin), distance.factors(points, origin) * factors)

    def test_attraction_modifiers_change_paths_without_reseeding(self):
        from _stochastic_curves import grow
        params = dict(seed_count=1, curves_per_seed=3, length=5., branch_probability=0,
                      repulsion=0, y_scale=1., length_variation=0)
        baseline = grow(42, **params)[0]
        disabled = grow(42, attraction_distance_scale=1., attraction_noise_scale=.5,
                        attraction_noise_octaves=5, **params)[0]
        for a, b in zip(baseline, disabled):
            np.testing.assert_array_equal(a, b)
        for modifiers in (dict(attraction_distance_effect=.9, attraction_distance_scale=1.),
                          dict(attraction_noise_strength=1., attraction_noise_scale=1.)):
            changed = grow(42, **modifiers, **params)[0]
            self.assertEqual(len(baseline), len(changed))
            self.assertGreater(max(np.linalg.norm(a-b, axis=1).max() for a, b in zip(baseline, changed)), .01)
            for a, b in zip(baseline, changed):
                np.testing.assert_array_equal(a[0], b[0])
                self.assertAlmostEqual(np.linalg.norm(np.diff(b, axis=0), axis=1).sum(), 5., places=8)

    def test_attraction_modifiers_keep_original_blob_for_branches(self):
        from unittest.mock import patch
        from _stochastic_curves import grow, AttractionModulation
        contexts = []
        original = AttractionModulation.factors
        def record(modulation, points, centers):
            contexts.append(np.asarray(centers).copy())
            return original(modulation, points, centers)
        with patch.object(AttractionModulation, "factors", record):
            paths, _, roots, parents = grow(42, seed_count=2, curves_per_seed=2, length=12.,
                branch_probability=1., repulsion=0, y_scale=1., attraction_distance_effect=.4)
        self.assertTrue(np.any(parents >= 0))
        # A single center is used by route prediction; batches are used by growth.
        self.assertTrue(any(c.ndim == 1 for c in contexts))
        self.assertTrue(any(c.ndim == 2 and len(c) > np.count_nonzero(parents < 0) for c in contexts))
        for centers in contexts:
            distances = np.linalg.norm(centers.reshape(-1, 1, 3) - roots[None], axis=2)
            np.testing.assert_allclose(distances.min(axis=1), 0, atol=1e-12)

    def test_filament_attraction_has_a_reproducible_weak_tail(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import filament_attraction
        strengths = np.array([filament_attraction(42, (i,), 2., .9) for i in range(1000)])
        self.assertTrue(((strengths >= .2) & (strengths <= 2.)).all())
        self.assertGreater(np.median(strengths), 1.7)
        self.assertGreater(np.count_nonzero(strengths < .6), 30)
        self.assertEqual(filament_attraction(42, (3,), 2., .9), strengths[3])
        self.assertEqual(filament_attraction(42, (3,), 2., 0), 2.)
        self.assertEqual(filament_attraction(42, (3,), 0., 1), 0.)
        from _stochastic_curves import grow
        params = dict(seed_count=1, curves_per_seed=4, length=5., branch_probability=0,
                      repulsion=0, y_scale=1., length_variation=0)
        uniform = grow(42, attraction_variation=0, **params)[0]
        varied = grow(42, attraction_variation=1, **params)[0]
        self.assertEqual(len(uniform), len(varied))
        self.assertGreater(max(np.linalg.norm(a-b, axis=1).max() for a, b in zip(uniform, varied)), .1)
        for a, b in zip(uniform, varied):
            np.testing.assert_array_equal(a[0], b[0])
            self.assertAlmostEqual(np.linalg.norm(np.diff(b, axis=0), axis=1).sum(), 5., places=8)

    def test_branch_departure_and_route_divergence(self):
        from _stochastic_curves import branch_departure_directions, branch_separation_scores, branch_choice_probabilities
        class Planes:
            scale = 4.
            gradients = np.array([[1., 0, 0], [0, 1., 0], [.02, 1., .03]])
            def sample(self, p):
                return p @ self.gradients.T, np.broadcast_to(self.gradients, (len(p), 3, 3))
        field = Planes()
        parent = np.array([0., 0, 1.])
        pairs, scores = branch_separation_scores(field, np.zeros(3), parent, (0, 1), 2,
                                                1.5, 1.5, 1.2, 5.)
        departures = branch_departure_directions(field, np.zeros(3), parent, pairs)
        self.assertGreater(np.dot(departures[0], parent), .99)  # AC almost follows AB.
        self.assertLess(np.dot(departures[1], parent), .6)  # BC offers a real fork.
        self.assertGreater(scores[1], scores[0] + .2)
        p = branch_choice_probabilities(scores, .8)
        self.assertGreater(p[1], .75)
        self.assertGreater(p[0], 0)  # Preference stays stochastic.
        np.testing.assert_allclose(branch_choice_probabilities(scores, 0), [.5, .5])
        np.testing.assert_allclose(branch_choice_probabilities([.1, .1], 1), [.5, .5])

    def test_branches_depart_without_waiting_for_turn_response(self):
        from itertools import combinations
        from _stochastic_curves import grow, NoiseLandscape, branch_departure_directions
        params = dict(seed_count=2, curves_per_seed=2, length=12., branch_probability=1,
                      repulsion=0, wandering=0, smoothness=1.2, y_scale=1., seed_pairing=0)
        paths, families, roots, parents = grow(42, **params)
        field = NoiseLandscape(42)
        pairs = list(combinations(range(3), 2))
        forks = np.flatnonzero(parents >= 0)
        self.assertGreater(len(forks), 0)
        angles = []
        for i in forks:
            parent = paths[parents[i]]
            at = np.flatnonzero(np.all(parent == paths[i][0], axis=1))
            self.assertTrue(len(at))
            incoming = parent[at[0]] - parent[at[0]-1]
            incoming /= np.linalg.norm(incoming)
            outgoing = paths[i][1] - paths[i][0]
            outgoing /= np.linalg.norm(outgoing)
            expected = branch_departure_directions(field, paths[i][0], incoming, [pairs[families[i]]])[0]
            self.assertGreater(np.dot(outgoing, expected), .99)
            angles.append(np.degrees(np.arccos(np.clip(np.dot(incoming, outgoing), -1, 1))))
        self.assertGreater(max(angles), 30)
        # Branching cannot redirect already-growing roots when repulsion is off.
        plain = grow(42, **dict(params, branch_probability=0))[0]
        for a, b in zip(plain, paths):
            np.testing.assert_array_equal(a, b)

    def test_stochastic_sources_launch_selected_pairs_at_verified_triples(self):
        from itertools import combinations
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import grow, NoiseLandscape
        for fields, noise in ((3, 0), (4, 0), (4, 1)):
            paths, families, roots, parents = grow(42, field_count=fields, noise_type=noise,
                seed_count=4, curves_per_seed=4, start_spread=0, wandering=0,
                branch_probability=0, repulsion=0, length=1, y_scale=1)
            values, gradients = NoiseLandscape(42, field_count=fields, noise_type=noise).sample(roots)
            self.assertGreaterEqual(len(paths), len(roots))
            self.assertLessEqual(len(paths), 16 * len(roots))
            self.assertTrue((parents == -1).all())
            pairs = list(combinations(range(fields), 2))
            for i, root in enumerate(roots):
                zero_fields = np.flatnonzero(np.abs(values[i]) < 1e-4)
                self.assertGreaterEqual(len(zero_fields), 3)
                initial = np.flatnonzero([np.array_equal(path[0], root) for path in paths])
                launched = families[initial]
                self.assertIn(len(set(launched)), (1, 2))
                for family in set(launched):
                    pair = pairs[family]
                    self.assertTrue(set(pair).issubset(zero_fields))
                    directions = [paths[j][1] - paths[j][0] for j in initial if families[j] == family]
                    axis = np.cross(gradients[i, pair[0]], gradients[i, pair[1]])
                    signs = np.array([np.dot(d, axis) > 0 for d in directions])
                    self.assertLessEqual(np.count_nonzero(signs), 4)
                    self.assertLessEqual(np.count_nonzero(~signs), 4)
        capped = grow(42, seed_count=12, curves_per_seed=4, max_paths=8,
                      branch_probability=0, length=1, start_spread=0, y_scale=1)
        self.assertLessEqual(len(capped[2]), 8)
        self.assertEqual(len(capped[0]), 8)
        for root in capped[2]:
            self.assertTrue(any(np.array_equal(p[0], root) for p in capped[0]))

    def test_junction_launch_counts_are_sparse_uneven_and_reproducible(self):
        from _stochastic_curves import launch_plan
        families, uneven = set(), 0
        for root in range(32):
            plan = launch_plan(42, root, 6)
            self.assertEqual(plan, launch_plan(42, root, 6))
            self.assertEqual(plan, launch_plan(42, root, 12)[:len(plan)])
            counts = np.bincount([slot for _, slot in plan], minlength=6)
            self.assertTrue((counts <= 6).all())
            active = np.flatnonzero(counts.reshape(3, 2).sum(axis=1))
            self.assertIn(len(active), (1, 2))
            families.update(active)
            uneven += np.any(counts[::2] != counts[1::2])
        self.assertEqual(families, {0, 1, 2})
        self.assertGreater(uneven, 20)

    def test_junction_seed_selection_includes_non_ab_triples_and_has_no_pair_fallback(self):
        from unittest.mock import patch
        from _stochastic_curves import seed_centers
        from _branch_curves import intersection_graph
        axis = np.linspace(-1, 1, 9)
        x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
        graph = intersection_graph([x-.13, y+.17, z-.23, x+y+z-.35])
        class Planes:
            scale = 1.
            def sample(self, p):
                values = np.column_stack((p[:, 0]-.13, p[:, 1]+.17, p[:, 2]-.23, p.sum(axis=1)-.35))
                gradients = np.broadcast_to([[1., 0, 0], [0, 1., 0], [0, 0, 1.], [1., 1, 1]], (len(p), 4, 3))
                return values, gradients
        with patch("_stochastic_curves.build_graph", return_value=graph):
            roots, triples = seed_centers(Planes(), 42, 1., 4, 0, 1., 1, .2, 4)
        self.assertEqual(set(map(tuple, triples)), {(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)})
        values, _ = Planes().sample(roots)
        np.testing.assert_allclose(values[np.arange(4)[:, None], triples], 0, atol=1e-10)
        no_junctions = (*graph[:3], np.zeros_like(graph[3]))
        with patch("_stochastic_curves.build_graph", return_value=no_junctions):
            with self.assertRaisesRegex(ValueError, "No triple-zero"):
                seed_centers(Planes(), 42, 1., 4, 0, 1., 1, .2, 4)

    def test_curve_repulsion_uses_other_paths_and_soft_transverse_force(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import CurveRepulsion
        field = CurveRepulsion(.2, capacity=10)
        # A finished segment still repels a later tip. Duplicate samples from the
        # same curve must not multiply its influence; own-curve samples are ignored.
        field.add(np.array([[0., 0, 0]]), np.array([[0., 0, 1]]), np.array([0]))
        positions = np.array([[.05, 0, .5], [.3, 0, .5], [.05, 0, .5]])
        tangent = np.tile([0., 0, 1], (3, 1))
        fallback = np.tile([1., 0, 0], (3, 1))
        owners = np.array([1, 1, 0])
        force = field.force(positions, tangent, owners, fallback)
        self.assertGreater(force[0, 0], 0)
        np.testing.assert_array_equal(force[:, 1:], 0)
        np.testing.assert_array_equal(force[1:], 0)
        field.add(np.array([[0., 0, 0]]), np.array([[0., 0, 1]]), np.array([0]))
        np.testing.assert_array_equal(field.force(positions, tangent, owners, fallback), force)
        # Coincident curves get a reproducible finite separating direction.
        coincident = field.force(np.array([[0., 0, .5]]), tangent[:1], owners[:1], fallback[:1])
        self.assertGreater(coincident[0, 0], 0)
        self.assertLessEqual(np.linalg.norm(coincident), 1)

    def test_curve_repulsion_separates_bundles_without_changing_budgets(self):
        from _stochastic_curves import grow
        from scipy.spatial import cKDTree
        params = dict(seed_count=1, curves_per_seed=4, length=6., length_variation=0,
                      branch_probability=0, y_scale=1., start_spread=.015, wandering=.03)
        original = grow(42, repulsion=0, **params)[0]
        repelled = grow(42, repulsion=.15, **params)[0]
        def clearance(paths):
            distances = []
            for i, path in enumerate(paths):
                other = np.concatenate([p for j, p in enumerate(paths) if i != j])
                distances.extend(cKDTree(other).query(path[len(path)//2:])[0])
            return np.median(distances)
        self.assertGreater(clearance(repelled), clearance(original) * 2)
        self.assertEqual(len(original), len(repelled))
        for a, b in zip(original, repelled):
            np.testing.assert_array_equal(a[0], b[0])
            self.assertAlmostEqual(np.linalg.norm(np.diff(b, axis=0), axis=1).sum(), 6., places=8)
        repeated = grow(42, repulsion=.15, **params)[0]
        for a, b in zip(repelled, repeated):
            np.testing.assert_array_equal(a, b)
        paths, _, _, parents = grow(42, seed_count=2, curves_per_seed=2, length=12.,
                                     branch_probability=1, repulsion=.15, y_scale=1.)
        self.assertTrue((parents >= 0).any())
        for i in np.flatnonzero(parents >= 0):
            parent = paths[parents[i]]
            at = np.flatnonzero(np.all(parent == paths[i][0], axis=1))
            self.assertTrue(len(at))
            outgoing = paths[i][1] - paths[i][0]
            self.assertTrue(np.isfinite(outgoing).all())
            self.assertGreater(np.linalg.norm(outgoing), 0)

    def test_curve_population_spacing_scatter_and_taper(self):
        worker.load_catalog(ROOT / "generators")
        from _population import populate_curves
        paths = [np.array([[0., 0, 0], [2., 0, 0], [10., 0, 0]])]
        colors = [[.2, .4, .6]]
        params = dict(pop_density=100, pop_jitter=0, pop_spread=0, pop_taper=0, pop_colors=1, pop_curve_density_variation=0)
        plain, stats = populate_curves(paths, colors, 42, params)
        np.testing.assert_allclose(plain[0][:, 0], (np.arange(1000) + .5) / 100, atol=1e-6)
        np.testing.assert_array_equal(plain[0][:, 1:], 0)
        np.testing.assert_allclose(plain[1], np.broadcast_to(colors, (1000, 3)))
        self.assertFalse(stats["population_limited"])
        scattered, _ = populate_curves(paths, colors, 42, dict(params, pop_spread=.1))
        np.testing.assert_array_equal(scattered[0][:, 0], plain[0][:, 0])
        self.assertAlmostEqual(float(scattered[0][:, 1:].std()), .1, delta=.01)
        tapered, _ = populate_curves(paths, colors, 42, dict(params, pop_taper=.5))
        indices = np.searchsorted(plain[0][:, 0], tapered[0][:, 0])
        for a, b in zip(plain, tapered):
            np.testing.assert_array_equal(a[indices], b)
        self.assertEqual(np.count_nonzero(tapered[0][:, 0] < 5), 500)
        self.assertLess(np.count_nonzero(tapered[0][:, 0] > 9), 20)
        resized, _ = populate_curves(paths, colors, 42, dict(params, pop_size=.2, pop_size_variation=0))
        np.testing.assert_array_equal(resized[0], plain[0])
        np.testing.assert_allclose(resized[2], .2)
        clumped, _ = populate_curves(paths, colors, 42, dict(params, pop_clumping=1))
        self.assertEqual(len(clumped[0]), len(plain[0]))
        self.assertFalse(np.array_equal(clumped[0], plain[0]))
        capped, stats = populate_curves(paths, colors, 42, params, limit=100)
        self.assertEqual(len(capped[0]), 100)
        self.assertTrue(stats["population_limited"])

    def test_population_density_noise_distribution_and_transverse_independence(self):
        from _population import populate_curves, density_noise
        paths = [np.array([[0., 0, 0], [10., 0, 0]])]
        params = dict(pop_density=1000, pop_spread=.1, pop_taper=0, pop_jitter=0, pop_curve_density_variation=0,
                      pop_clumping=3, pop_clump_scale=1.3, pop_density_octaves=4,
                      pop_density_roughness=.6)
        varied, _ = populate_curves(paths, [[1., 1, 1]], 42, params)
        uniform, _ = populate_curves(paths, [[1., 1, 1]], 42, dict(params, pop_clumping=0))
        self.assertEqual(len(varied[0]), 10000)
        np.testing.assert_array_equal(varied[0][:, 1:], uniform[0][:, 1:])
        np.testing.assert_array_equal(varied[2], uniform[2])
        # Compare the sampled distribution against an independently integrated fine grid.
        grid = np.linspace(0, 10, 100001)
        field = density_noise(grid, 42, 0, 1.3, 4, .6)
        rho = np.exp(3 * field)
        mass = np.r_[0., np.cumsum((rho[:-1] + rho[1:]) / 2)]
        expected = np.interp(np.arange(1, 10), grid, mass / mass[-1])
        actual = np.searchsorted(varied[0][:, 0], np.arange(1, 10)) / 10000
        np.testing.assert_allclose(actual, expected, atol=.0003)
        self.assertGreater(np.std(np.diff(varied[0][:, 0])), .0005)
        # Noise depends on arc length, not world location or polyline tessellation.
        translated = [np.array([[2., 3, 4], [6., 3, 4], [12., 3, 4]])]
        moved, _ = populate_curves(translated, [[1., 1, 1]], 42, params)
        np.testing.assert_allclose(moved[0] - [2, 3, 4], varied[0], atol=1e-6)
        np.testing.assert_array_equal(density_noise(grid, 42, 0, 1.3, 4, 0),
                                      density_noise(grid, 42, 0, 1.3, 1, .6))
        for changes in (dict(pop_density_octaves=1), dict(pop_density_roughness=.1),
                        dict(pop_clump_scale=2), dict(pop_jitter=1)):
            changed, _ = populate_curves(paths, [[1., 1, 1]], 42, dict(params, **changes))
            self.assertEqual(len(changed[0]), len(varied[0]))
            self.assertFalse(np.array_equal(changed[0][:, 0], varied[0][:, 0]))
            np.testing.assert_array_equal(changed[0][:, 1:], varied[0][:, 1:])
        repeated, _ = populate_curves(paths, [[1., 1, 1]], 42, params)
        for a, b in zip(varied, repeated):
            np.testing.assert_array_equal(a, b)

    def test_population_curves_have_independent_mean_densities(self):
        from _population import populate_curves
        paths = [np.array([[0., i, 0], [10., i, 0]]) for i in range(32)]
        colors = np.column_stack((np.arange(32) / 32, np.zeros(32), np.ones(32)))
        params = dict(pop_density=10, pop_taper=0, pop_colors=1, pop_curve_density_variation=.5)
        varied, _ = populate_curves(paths, colors, 42, params)
        def counts(generated):
            return np.unique(generated[1][:, 0], return_counts=True)[1]
        numbers = counts(varied)
        self.assertEqual(len(numbers), 32)
        self.assertTrue(((numbers >= 50) & (numbers <= 150)).all())
        self.assertGreater(np.ptp(numbers), 60)
        flat, _ = populate_curves(paths, colors, 42, dict(params, pop_curve_density_variation=0))
        np.testing.assert_array_equal(counts(flat), np.full(32, 100))
        along, _ = populate_curves(paths, colors, 42, dict(params, pop_clumping=3))
        np.testing.assert_array_equal(counts(along), numbers)
        repeated, _ = populate_curves(paths, colors, 42, params)
        for a, b in zip(varied, repeated):
            np.testing.assert_array_equal(a, b)

    def test_population_worker_layers_are_independent(self):
        import struct
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "points.bin"
            sidecar = output.with_suffix(".stars.bin")
            params = dict(seed_count=1, curves_per_seed=2, length=2., pop_taper=0, pop_density=5)
            def run(changes):
                result = worker.generate_request(dict(generator="stochastic_filaments", count=1, seed=42,
                    params=dict(params, **changes)), ROOT / "generators", output)
                self.assertTrue(result["ok"], result)
                self.assertTrue(result["population"])
                self.assertEqual(struct.unpack("<8sQ", sidecar.read_bytes()[:16]), (b"FSTAR002", result["star_count"]))
                return output.read_bytes(), sidecar.read_bytes(), result
            curves, stars, base = run({})
            for changes in (dict(pop_density=3), dict(pop_spread=.1), dict(pop_taper=.8), dict(pop_clumping=3), dict(pop_curve_density_variation=0),
                            dict(pp_warp=1), dict(fade=1)):
                other_curves, other_stars, _ = run(changes)
                self.assertEqual(curves, other_curves)
                self.assertNotEqual(stars, other_stars)
            _, unmarked, _ = run(dict(show_seeds=0))
            self.assertEqual(stars, unmarked)  # Seed preview rings never receive stars.
            other_curves, empty, result = run(dict(pop_density=0, fade=1, pp_merge=1))
            self.assertEqual(curves, other_curves)
            self.assertEqual(result["star_count"], 0)
            self.assertEqual(len(empty), 16)

    def test_stochastic_random_lifetimes_and_stable_prefixes(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import grow, lifetime
        params = dict(seed_count=1, curves_per_seed=8, length=8., branch_probability=0., y_scale=1., repulsion=0.)
        fixed = grow(42, length_variation=0., **params)[0]
        varied = grow(42, length_variation=.7, **params)[0]
        lengths = np.array([np.linalg.norm(np.diff(p, axis=0), axis=1).sum() for p in varied])
        self.assertTrue((lengths >= 8*.3 - 1e-8).all())
        self.assertTrue((lengths <= 8*1.7 + 1e-8).all())
        self.assertGreater(np.ptp(lengths), 4.)
        self.assertTrue((lengths < 8).any() and (lengths > 8).any())
        for a, b in zip(fixed, varied):
            # The shorter path has a fractional final step; all earlier vertices match.
            shared = min(len(a), len(b)) - 1
            np.testing.assert_array_equal(a[:shared], b[:shared])
        for i in range(32):
            child = lifetime(42, (i,), 4., .7, child=True)
            self.assertGreaterEqual(child, 4*.3)
            self.assertLessEqual(child, 4.)
            self.assertEqual(child, lifetime(42, (i,), 4., .7, child=True))
            self.assertEqual(lifetime(42, (i,), 4., 0.), 4.)

    def test_stochastic_guidance_is_soft_descent(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import guidance
        values = np.array([[.3, -.2], [-.4, .1]])
        gradients = np.broadcast_to([[1., 0., 0.], [0., 1., 0.]], (2, 2, 3))
        headings = np.array([[0., 0., 1.], [0., 0., -1.]])
        tangent, correction = guidance(values, gradients, np.array([[0, 1], [0, 1]]), headings)
        np.testing.assert_array_equal(tangent, headings)
        descent = (correction[:, :2] * values).sum(axis=1)
        self.assertTrue((descent > 0).all())
        # Finite motion toward the strand leaves a residual; it never projects to zero.
        remaining = values - .1 * correction[:, :2]
        self.assertTrue((np.linalg.norm(remaining, axis=1) < np.linalg.norm(values, axis=1)).all())
        self.assertTrue((np.linalg.norm(remaining, axis=1) > 0).all())

    def test_stochastic_bundles_density_attraction_and_smoothing(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import grow, NoiseLandscape
        params = dict(seed_count=1, length=8., length_variation=0., branch_probability=0., y_scale=1., repulsion=0.)
        thin = grow(42, curves_per_seed=1, **params)
        dense = grow(42, curves_per_seed=3, **params)
        self.assertGreater(len(dense[0]), len(thin[0]))
        for a, b in zip(thin[0], dense[0]):
            np.testing.assert_array_equal(a, b)
        self.assertGreater(np.linalg.norm(dense[0][0] - dense[0][1]), .1)
        for path in dense[0]:
            steps = np.diff(path, axis=0)
            distances = np.linalg.norm(steps, axis=1)
            self.assertAlmostEqual(distances.sum(), 8., places=8)
            directions = steps / distances[:, None]
            angles = np.degrees(np.arccos(np.clip((directions[1:] * directions[:-1]).sum(axis=1), -1, 1)))
            self.assertLess(angles.max(), 17.)  # .06-unit steps with .25-unit angular smoothing.
        field = NoiseLandscape(42)
        def residual(attraction):
            paths, families, _, _ = grow(42, curves_per_seed=3, attraction=attraction, **params)
            pairs = ((0, 1), (0, 2), (1, 2))
            residuals = []
            for path, family in zip(paths, families):
                values, _ = field.sample(path[len(path)//2:])
                residuals.extend(np.linalg.norm(values[:, pairs[family]], axis=1))
            return np.mean(residuals)
        self.assertLess(residual(4.), residual(0.) * .5)
        values, _ = field.sample(np.concatenate(dense[0]))
        self.assertGreater(np.median(np.linalg.norm(values[:, :2], axis=1)), 1e-4)

    def test_stochastic_branch_attachment_and_protocol(self):
        worker.load_catalog(ROOT / "generators")
        from _stochastic_curves import grow
        from stochastic_filaments import generate
        params = dict(seed_count=2, curves_per_seed=2, length=12., y_scale=1., repulsion=0.)
        paths, families, roots, parents = grow(42, branch_probability=1., **params)
        self.assertTrue((parents >= 0).any())
        for i in np.flatnonzero(parents >= 0):
            parent = paths[parents[i]]
            self.assertLess(parents[i], i)
            index = np.flatnonzero(np.all(parent == paths[i][0], axis=1))
            self.assertTrue(len(index))
            outgoing = paths[i][1] - paths[i][0]
            self.assertTrue(np.isfinite(outgoing).all())
            self.assertGreater(np.linalg.norm(outgoing), 0)
        plain = grow(42, branch_probability=0., **params)
        for a, b in zip(plain[0], paths):
            np.testing.assert_array_equal(a, b)
        small = dict(seed_count=1, curves_per_seed=2, length=2.)
        a = generate(1, 42, **small)
        b = generate(1000000, 42, **small)
        for first, second in zip(a, b):
            np.testing.assert_array_equal(first, second)
        for kind in (0, 1):
            p, c, s = generate(1, 42, **small, field_count=4, noise_type=kind, y_scale=0, show_seeds=0)
            self.assertTrue(np.isfinite(p).all())
            self.assertEqual(len(p) % 2, 0)
            np.testing.assert_array_equal(p[:, 1], 0)
        with tempfile.TemporaryDirectory() as temp:
            result = worker.generate_request(dict(generator="stochastic_filaments", count=1, seed=42, params=small),
                                            ROOT / "generators", Path(temp) / "lines.bin")
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["primitive"], "lines")

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
                             0 if entry["primitive"] == "lines" and not entry["population"] else 1)
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
