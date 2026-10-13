"""Independent corpus invariants and worker integration; no viewer launch."""
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
import worker
from _curve_corpus import (build_corpus, build_definition, score_corpus, select_candidates,
                           footprints, unpack_paths)


class CurveCorpus(unittest.TestCase):
    def test_independent_geometry_cache_prefix_and_bounds(self):
        args = ((80., 16., 80.), 173, 32.)
        a, ids = build_corpus(*args, per_cell=2, span=100., bend=1.2)
        b, more = build_corpus(*args, per_cell=4, span=100., bend=1.2)
        np.testing.assert_array_equal(ids, more[:len(ids)])
        np.testing.assert_array_equal(a, b[:len(a)])
        self.assertTrue((np.abs(b) <= np.array(args[0])+1e-10).all())
        self.assertFalse(b.flags.writeable)
        self.assertIs(b, build_corpus(*args, per_cell=4, span=100., bend=1.2)[0])
        paths = unpack_paths(a, np.arange(len(a)))
        self.assertTrue(all((np.linalg.norm(np.diff(p, axis=0), axis=1) > 1e-10).all() for p in paths))
        # Density scoring, including a different resolution, never alters points.
        before = a.tobytes()
        score_corpus(a, np.ones((9, 9, 9)), np.array(args[0]))
        score_corpus(a, np.zeros((15, 15, 15)), np.array(args[0]))
        self.assertEqual(before, a.tobytes())

    def test_axis_bias_and_vertical_zero_have_literal_meaning(self):
        points, _ = build_corpus((64., 16., 64.), per_cell=2, span=32., bend=0., vertical=0., axis_bias=1.)
        delta = np.diff(points, axis=1)
        self.assertLess(float(np.abs(delta[:, :, 1]).max()), 1e-12)
        self.assertTrue(np.all(np.minimum(np.abs(delta[:, :, 0]), np.abs(delta[:, :, 2])) < 1e-12))
        # Outside the box, geometry is clipped along the curve, never projected
        # to run along its wall: each half has only repeated endpoint padding.
        for p in points:
            kept = p[np.r_[True, np.linalg.norm(np.diff(p, axis=0), axis=1) > 1e-10]]
            d = np.diff(kept, axis=0)
            self.assertLess(float(np.linalg.norm(np.cross(d, d[0]), axis=1).max()), 1e-9)

    def test_octave_noise_changes_detail_without_changing_anchors(self):
        args = ((128., 32., 128.),)
        broad, ids = build_corpus(*args, per_cell=2, span=64., wavelength=96., octaves=1)
        fine, finer_ids = build_corpus(*args, per_cell=2, span=64., wavelength=96., octaves=3)
        np.testing.assert_array_equal(ids, finer_ids)
        np.testing.assert_allclose(broad[:, broad.shape[1]//2], fine[:, fine.shape[1]//2], atol=1e-12)
        # Non-periodic Perlin profiles are not a fixed bow or common shape.
        self.assertGreater(float(np.std(np.diff(fine, n=2, axis=1))), .001)
        single, _ = build_corpus(*args, per_cell=2, span=64., wavelength=96., octaves=3, roughness=0.)
        np.testing.assert_array_equal(broad, single)

    def test_parametric_evaluation_arbitrary_parameters_and_monotone_projection(self):
        curves = build_definition((80., 24., 80.), per_cell=2, span=64.)
        np.testing.assert_allclose(curves.evaluate([0])[:, 0], curves.centers, atol=1e-12)
        t = np.array([-.413, -.101, .057, .399])
        all_points = curves.evaluate(t)
        np.testing.assert_array_equal(curves.evaluate(t, [1, 3]), all_points[[1, 3]])
        # No growth/state or dependency on the order of evaluation.
        np.testing.assert_array_equal(curves.evaluate(t[::-1]), all_points[:, ::-1])
        projected = np.einsum('ntc,nc->nt', all_points-curves.centers[:, None], curves.directions)
        np.testing.assert_allclose(projected, curves.spans[:, None]*t, atol=1e-12)

    def test_sustained_support_prefers_following_over_crossing(self):
        half = np.ones(3)*10
        xyz = np.linspace(-10, 10, 81)
        density = np.broadcast_to(np.exp(-xyz[None, :, None]**2/2), (81, 81, 81)).copy()
        t = np.linspace(-8, 8, 65)
        along = np.column_stack((t, np.ones_like(t)*1.4, np.zeros_like(t)))
        cross = np.column_stack((np.zeros_like(t), t, np.zeros_like(t)))
        plain, _ = score_corpus(np.array([along, cross]), density, half, power=1., continuity=0.)
        sustained, report = score_corpus(np.array([along, cross]), density, half, power=1., continuity=1.)
        self.assertGreater(plain[0], plain[1])
        self.assertGreater(sustained[0]/sustained[1], plain[0]/plain[1]*3)
        self.assertAlmostEqual(report['support'][0], 1., places=10)
        # Subdividing a polyline preserves arc-based scores, not vertex counts.
        refined = np.array([np.column_stack([np.interp(np.linspace(0, 64, 129), np.arange(65), p[:, k]) for k in range(3)]) for p in (along, cross)])
        finer, _ = score_corpus(refined, density, half, power=1., continuity=1.)
        np.testing.assert_allclose(finer, sustained, rtol=.01)

    def test_selection_nested_zero_binding_and_empty_density(self):
        points, ids = build_corpus((64., 16., 64.), per_cell=4, span=40.)
        scores = np.linspace(.01, 1., len(points))
        small = select_candidates(scores, ids, 7, 14)
        large = select_candidates(scores, ids, 19, 14)
        self.assertTrue(set(small) <= set(large))
        np.testing.assert_array_equal(select_candidates(scores, ids, 7, 14, binding=0),
                                      select_candidates(np.zeros_like(scores), ids, 7, 14, binding=0))
        self.assertEqual(len(select_candidates(np.zeros_like(scores), ids, 7, 14)), 0)
        np.testing.assert_array_equal(large, select_candidates(scores, ids, 19, 14))

    def test_lazy_overlap_selection_matches_exhaustive_greedy(self):
        from scipy.sparse import csr_matrix
        from _block_population import cell_uniform
        ids = np.column_stack((np.arange(18), np.zeros((18, 3), dtype=int))).astype(int)
        rng = np.random.default_rng(21)
        dense = rng.uniform(0, 2, (18, 7))*(rng.random((18, 7)) < .4)
        dense[:, 0] += .1
        scores = rng.uniform(.1, 1, 18)
        matrix = csr_matrix(dense)
        actual = select_candidates(scores, ids, 9, 173, diversity=2., footprint=matrix)
        priority = -np.log(cell_uniform(ids[:, :3], 173, 190001))/(scores/scores.max())
        load, chosen = np.zeros(7), []
        for _ in range(9):
            penalty = (dense/(1+load)**2).sum(axis=1)/dense.sum(axis=1)
            revised = priority/penalty
            revised[chosen] = np.inf
            best = int(revised.argmin())
            chosen.append(best)
            load += dense[best]
        np.testing.assert_array_equal(actual, sorted(chosen))

    def test_worker_native_units_shared_field_and_population_independence(self):
        field = dict(extent=64., y_extent=16., noise_scale=40., field_resolution=24)
        params = dict(corpus_span=48., corpus_copies=4, select_count=12, select_binding=0., pop_density=.1)
        request = dict(generator='density_curve_corpus', count=100, seed=42,
                       world_units='blocks', density_graph=True, density_field=field, params=params)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'lines.bin'
            a = worker.generate_request(request, ROOT/'generators', output)
            self.assertTrue(a['ok'], a.get('error'))
            geometry = output.read_bytes()
            self.assertEqual(a['params']['corpus_span'], 48.)
            self.assertEqual(a['params']['pop_density'], .1)
            self.assertEqual(a['params']['_block_units'], 1)
            self.assertFalse(set(field) & a['params'].keys())
            request['params'] = dict(a['params'], pop_density=.2, pop_spread_xz=1.)
            b = worker.generate_request(request, ROOT/'generators', output)
            self.assertTrue(b['ok'], b.get('error'))
            self.assertEqual(geometry, output.read_bytes())
            # With selection binding off, changing ONLY the upstream noise seed
            # changes filling, but leaves the separate corpus and choice intact.
            request['seed'] = 43
            c = worker.generate_request(request, ROOT/'generators', output)
            self.assertTrue(c['ok'], c.get('error'))
            self.assertEqual(geometry, output.read_bytes())
            schema = next(s for s in a['catalog'] if s['id'] == 'density_curve_corpus')
            self.assertEqual(next(p['default'] for p in schema['parameters'] if p['key']=='pop_density'), .25)
            from _density_field import PARAMETERS
            self.assertEqual([p for p in schema['parameters'] if p.get('scope')=='density_field'], PARAMETERS)

    def test_guards_reject_instead_of_truncating(self):
        with self.assertRaisesRegex(ValueError, 'corpus exceeds'):
            build_corpus((3840., 3840., 3840.), cell_size=8.)
        with self.assertRaisesRegex(ValueError, 'corpus exceeds'):
            build_corpus((128., 128., 128.), span=1024., bend=3., per_cell=128)


if __name__ == '__main__':
    unittest.main()
