"""Population contracts and topology preservation for the separate star trial."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'generators'), str(ROOT / 'python')]
from _block_scaffold import grow
from block_scaffold_stars import population_paths, generate_population_plan
from _block_population import populate_blocks
import worker


class ScaffoldStars(unittest.TestCase):
    def test_population_represents_all_graph_edges_and_no_invented_route(self):
        graph = grow(1001, root_count=1, width=100, height=30, cells_per_root=160)
        paths, colors, ids = population_paths(graph)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(colors.shape, (len(paths), 3))
        lookup = {tuple(c + .5): i for i, c in enumerate(graph.cells)}
        represented = set()
        for path in paths:
            self.assertGreaterEqual(len(path), 2)
            self.assertTrue(np.all(np.abs(np.diff(path, axis=0)).sum(axis=1) == 1))
            for a, b in zip(path, path[1:]):
                represented.add(tuple(sorted((lookup[tuple(a)], lookup[tuple(b)]))))
        self.assertEqual(represented, set(map(tuple, graph.edges)))

    def test_population_controls_preserve_scaffold_and_stable_path_ids(self):
        base = dict(root_count=2, width=60, height=20, cells_per_root=80)
        a = generate_population_plan(1000, 42, **base, mixed_materials=0)
        b = generate_population_plan(1000, 42, **base, mixed_materials=1,
                                     rod_fraction=.4, block_fraction=.1, pop_density=5.,
                                     pop_spread_xz=2.)
        np.testing.assert_array_equal(a['source'][0][0], b['source'][0][0])
        np.testing.assert_array_equal(a['population']['_curve_ids'], b['population']['_curve_ids'])
        self.assertEqual(a['stats'], b['stats'])
        self.assertIsNone(a['source'][3])  # No upstream density source.

    def test_material_mix_changes_shapes_and_light_sources_not_occupancy(self):
        graph = grow(1001, root_count=1, cells_per_root=100, width=80, height=30)
        paths, colors, ids = population_paths(graph)
        base = dict(pop_blocks=1, pop_density=1.3, pop_spread_xz=.35, pop_spread_y=.2,
                    pop_taper=0., _curve_ids=ids, _curve_kinds=np.zeros(len(ids), dtype=np.int8))
        results = []
        for fractions, kind in [([1., 0., 0.], 0), ([0., 1., 0.], 1), ([0., 0., 1.], 2)]:
            stars, stats = populate_blocks(paths, colors, 42, dict(base, _cell_material_fractions=fractions))
            self.assertGreater(len(stars[0]), 20)
            np.testing.assert_array_equal(stats['_block_kinds'], kind)
            results.append(stars[0])
        for result in results[1:]:
            np.testing.assert_array_equal(result, results[0])
        self.assertEqual(len(results[0]), len(np.unique(results[0], axis=0)))
        np.testing.assert_array_equal(np.mod(results[0], 1), .5)
        tinted, _ = populate_blocks(paths, colors, 42,
            dict(base, pop_colors=1, _cell_material_fractions=[0., 1., 0.]))
        np.testing.assert_allclose(tinted[1], np.tile(colors[0], (len(tinted[0]), 1)))
        for fractions in ([.8, .8, 0.], [-.1, .9, .2], [np.nan, 0., 1.], [1., 0.]):
            with self.assertRaises(ValueError):
                populate_blocks(paths, colors, 42, dict(base, _cell_material_fractions=fractions))

    def test_worker_loads_separate_script_and_preserves_geometry_between_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            params = dict(width=60, height=20, root_count=2, cells_per_root=80,
                          pop_density=1.1, pop_spread_xz=.35, pop_spread_y=.2)
            curves = []
            for mode in (0, 1, 1):
                output = tmp / f'case-{len(curves)}.bin'
                response = worker.generate_request(dict(generator='block_scaffold_stars', count=1000,
                    world_units='blocks', seed=1001, params=dict(params, mixed_materials=mode)),
                    ROOT / 'generators', output)
                self.assertTrue(response['ok'], response.get('error'))
                self.assertFalse(response['warnings'])
                self.assertTrue(response['population'])
                curves.append(output.read_bytes())
                self.assertEqual(output.with_suffix('.stars.bin').read_bytes()[:8], b'FSTAR003')
            self.assertEqual(curves[0], curves[1])
            self.assertEqual(curves[1], curves[2])
            self.assertEqual((tmp/'case-1.stars.bin').read_bytes(), (tmp/'case-2.stars.bin').read_bytes())


if __name__ == '__main__':
    unittest.main()
