"""Whole-path selection preserves useful routes while removing duplicates."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
import worker
from _curve_selection import CurvePool, build_pool, build_coverage, select_curves


def pool(paths):
    return CurvePool(tuple(np.asarray(p, dtype=float) for p in paths),
                     np.zeros((len(paths),3), dtype=int), np.ones((9,9,9)), np.full(3,100.))


class CurveSelection(unittest.TestCase):
    def test_parallel_duplicates_and_crossings(self):
        paths = [[[-40, y, 0], [40, y, 0]] for y in (0., .2, -.2, .4)]
        paths.append([[0,-40,0], [0,40,0]])
        p = pool(paths)
        coverage = build_coverage(p, 2., 30.)
        chosen = select_curves(p, coverage, 1.)
        self.assertEqual(len(chosen), 2)
        self.assertIn(4, chosen)
        self.assertEqual(len(set(chosen)&set(range(4))), 1)

    def test_duplicate_bundle_does_not_outweigh_unique_route(self):
        repeated = [[[-40, y, 0], [40, y, 0]] for y in np.linspace(0,.5,30)]
        unique = [[[-40,20,0], [40,20,0]]]
        p = pool(repeated+unique)
        coverage = build_coverage(p,2.,30.)
        report = {}
        chosen = select_curves(p,coverage,.95,report=report)
        self.assertEqual(len(chosen),2)
        self.assertIn(30,chosen)
        self.assertGreaterEqual(report['coverage'],.95)

    def test_unique_extensions_survive_and_more_coverage_is_nested(self):
        p = pool([[[-40,0,0],[40,0,0]], [[-40,.1,0],[40,.1,0]],
                  [[-40,.2,0],[40,.2,0],[60,20,0]], [[0,0,0],[0,-35,0]]])
        coverage = build_coverage(p,2.,30.)
        all_kept = select_curves(p,coverage,1.)
        less = select_curves(p,coverage,.8)
        self.assertIn(2, all_kept)
        self.assertIn(3, all_kept)
        self.assertTrue(set(less)<=set(all_kept))
        self.assertLess(len(all_kept),len(p.paths))

    def test_sampling_invariant_to_subdivision_and_reverse(self):
        a = np.array([[-40,0,0],[40,0,0]], float)
        b = np.column_stack((np.linspace(40,-40,500),np.ones(500)*.1,np.zeros(500)))
        p = pool([a,b])
        coverage=build_coverage(p,2.,30.)
        self.assertTrue(coverage.matrix.toarray().all())
        chosen=select_curves(p,coverage,1.)
        self.assertEqual(len(chosen),1)

    def test_worker_off_matches_original_and_selection_reuses_growth(self):
        params=dict(_block_units=1,seed_rate=12.,strand_length=100.,seed_xz=.9,seed_y_pos=.9,seed_y_neg=.9,
                    seed_density_power=.5,length_variation=.5,growth_join=0,pop_density=.05)
        request=dict(generator='density_filament_selection',count=100,seed=42,
            world_units='blocks',density_graph=True,density_field=dict(extent=96.,y_extent=24.,field_resolution=24),params=params)
        build_pool.cache_clear()
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'points.bin'
            off=worker.generate_request(dict(request,params=dict(params,selection_enabled=0)),ROOT/'generators',file)
            self.assertTrue(off['ok'],off.get('error'))
            before=file.read_bytes()
            old=worker.generate_request(dict(request,generator='density_filament_curves'),ROOT/'generators',file)
            self.assertTrue(old['ok'],old.get('error'))
            self.assertEqual(before,file.read_bytes())
            with patch('_curve_selection.grow_field',side_effect=AssertionError('Candidate pool unexpectedly regrew')):
                for changes in (dict(selection_radius=6),dict(selection_radius=6,selection_coverage=.99,pop_density=.1)):
                    result=worker.generate_request(dict(request,params=dict(params,**changes)),ROOT/'generators',file)
                    self.assertTrue(result['ok'],result.get('error'))
                    self.assertEqual(result['params']['strand_length'],100.)


if __name__ == '__main__':
    unittest.main()
