"""Block scaffold topology and worker contract; no population or visible window."""
from pathlib import Path
from collections import deque
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'generators'), str(ROOT / 'python')]
from _block_scaffold import grow, preview, STEPS


class BlockScaffold(unittest.TestCase):
    def test_integer_cells_bounds_caps_and_reproducibility(self):
        params = dict(width=81, height=27, root_count=5, cells_per_root=140)
        a, b = grow(763813, **params), grow(763813, **params)
        np.testing.assert_array_equal(a.cells, b.cells)
        np.testing.assert_array_equal(a.edges, b.edges)
        self.assertEqual(a.stats, b.stats)
        self.assertEqual(len(a.cells), len(set(map(tuple, a.cells))))
        self.assertTrue(np.issubdtype(a.cells.dtype, np.integer))
        self.assertTrue(((a.cells >= [-40, -13, -40]) & (a.cells < [41, 14, 41])).all())
        self.assertTrue((np.bincount(a.owners, minlength=5) <= 140).all())
        self.assertFalse(np.array_equal(a.cells, grow(42, **params).cells))

    def test_every_physical_face_contact_is_an_explicit_graph_edge(self):
        for seed in (42, 1001, 763813):
            g = grow(seed, width=80, height=28, root_count=9, cells_per_root=180)
            lookup = {tuple(p): i for i, p in enumerate(g.cells)}
            physical = set()
            for i, p in enumerate(g.cells):
                for d in STEPS:
                    j = lookup.get(tuple(p + d))
                    if j is not None:
                        physical.add(tuple(sorted((i, j))))
            self.assertEqual(set(map(tuple, g.edges)), physical)
            np.testing.assert_array_equal(np.abs(g.cells[g.edges[:, 0]] - g.cells[g.edges[:, 1]]).sum(axis=1), 1)

    def test_child_paths_share_parent_cells_and_use_real_edges(self):
        g = grow(1001, root_count=1, width=120, height=48)
        self.assertGreater(g.stats['forks'], 5)
        edges = set(map(tuple, g.edges))
        for pid, path in enumerate(g.paths):
            parent = g.parents[pid]
            if parent >= 0:
                self.assertLess(parent, pid)
                self.assertIn(path[0], g.paths[parent])
            else:
                self.assertIn(path[0], g.roots)
            for a, b in zip(path, path[1:]):
                self.assertIn(tuple(sorted((int(a), int(b)))), edges)

    def test_no_contact_mode_preserves_one_tree_per_root(self):
        g = grow(42, width=80, height=25, root_count=12, cells_per_root=200, allow_joins=0)
        self.assertEqual(g.stats['components'], 12)
        self.assertEqual(g.stats['cycles'], 0)
        self.assertEqual(g.stats['joins'], 0)
        # Connected components must each contain exactly one seed, including an
        # isolated root if no first step is available in a crowded test scene.
        adjacency = [set() for _ in g.cells]
        for a, b in g.edges:
            adjacency[a].add(b)
            adjacency[b].add(a)
        visited = set()
        for root in g.roots:
            reached, pending = {int(root)}, [int(root)]
            while pending:
                for j in adjacency[pending.pop()]:
                    if j not in reached:
                        reached.add(j)
                        pending.append(j)
            self.assertFalse(visited & reached)
            visited |= reached
        self.assertEqual(len(visited), len(g.cells))

    def test_joins_make_no_tiny_cycles(self):
        g = grow(1001, root_count=1, width=120, height=48)
        self.assertGreater(g.stats['cycles'], 0)
        adjacency = [set() for _ in g.cells]
        for a, b in g.edges:
            adjacency[a].add(b)
            adjacency[b].add(a)
        # Exhaustive short-path check on a small fixture: removing an edge must
        # not leave a return path shorter than nine edges (girth >= ten).
        for a, b in g.edges:
            seen, queue = {int(a)}, deque([(int(a), 0)])
            while queue:
                node, depth = queue.popleft()
                if depth == 8:
                    continue
                for j in adjacency[node]:
                    if node == a and j == b:
                        continue
                    self.assertNotEqual(j, b)
                    if j not in seen:
                        seen.add(j)
                        queue.append((j, depth + 1))

    def test_preview_is_only_the_same_graph_or_unit_wire_cells(self):
        g = grow(42, root_count=1, width=80, height=32)
        p, rgb, size = preview(g, blocks=False)
        np.testing.assert_array_equal(p, (g.cells.astype(np.float32) + .5)[g.edges].reshape(-1, 3))
        self.assertEqual(rgb.shape, p.shape)
        self.assertTrue(((rgb >= 0) & (rgb <= 1)).all())
        wire, _, _ = preview(g, blocks=True)
        self.assertEqual(len(wire), 24 * len(g.cells))
        np.testing.assert_array_equal(wire, np.rint(wire))
        np.testing.assert_array_equal(np.abs(wire[1::2] - wire[::2]).sum(axis=1), 1)
        self.assertTrue((size > 0).all())

    def test_guard_and_quantized_small_turns(self):
        with self.assertRaisesRegex(ValueError, '40,000'):
            grow(42, root_count=64, cells_per_root=5000)
        for height in (4, 5):
            g = grow(42, width=8, height=height, root_count=1, turn_angle=5.)
            self.assertGreaterEqual(len(g.cells), 2)
        for invalid in (0, 9, 1.5):
            with self.assertRaisesRegex(ValueError, 'Axis run'):
                grow(42, axis_run=invalid)

    def test_axis_runs_allow_sustained_vertical_motion_without_new_roots(self):
        old = grow(42, root_count=1, width=120, height=48, axis_run=1)
        new = grow(42, root_count=1, width=120, height=48, axis_run=2)
        np.testing.assert_array_equal(old.cells[old.roots], new.cells[new.roots])
        def vertical_runs(g):
            result = []
            for path in g.paths:
                steps = np.diff(g.cells[path], axis=0)
                length, previous = 0, 0
                for step in steps:
                    current = int(step[1])
                    if current and current == previous:
                        length += 1
                    else:
                        if previous:
                            result.append(length)
                        length = int(bool(current))
                    previous = current
                if previous:
                    result.append(length)
            return result
        self.assertLessEqual(max(vertical_runs(old)), 3)
        self.assertGreaterEqual(max(vertical_runs(new)), 4)
        self.assertGreater(sum(n == 1 for n in vertical_runs(new)), 0)
        # Default equals the chosen local rule and remains deterministic.
        again = grow(42, root_count=1, width=120, height=48)
        np.testing.assert_array_equal(new.cells, again.cells)
        np.testing.assert_array_equal(new.edges, again.edges)

    def test_worker_exposes_only_scaffold_and_ignores_star_count(self):
        import worker
        catalog, _, errors = worker.load_catalog(ROOT / 'generators', block_units=True, density_graph=True)
        self.assertFalse(errors)
        entry = next(e for e in catalog if e['id'] == 'block_scaffold')
        self.assertEqual(entry['primitive'], 'lines')
        self.assertTrue(entry['native_blocks'])
        self.assertFalse(entry['population'])
        self.assertFalse(any(p['key'].startswith(('pop_', 'pp_', 'noise_', 'field_')) for p in entry['parameters']))
        with tempfile.TemporaryDirectory() as directory:
            outputs = []
            for count in (1, 100000):
                output = Path(directory) / f'{count}.bin'
                result = worker.generate_request(dict(generator='block_scaffold', count=count, seed=42,
                    world_units='blocks', density_graph=True, params=dict(root_count=1)), ROOT / 'generators', output)
                self.assertTrue(result['ok'], result)
                self.assertFalse(result.get('population', False))
                self.assertFalse(output.with_suffix('.stars.bin').exists())
                outputs.append(output.read_bytes())
            self.assertEqual(*outputs)

    def test_turn_continuation_preserves_discrete_contact_contract(self):
        params = dict(width=100, height=40, root_count=4, cells_per_root=200,
                      axis_run=1, turn_angle=25., bend_memory=.9)
        a, b = grow(42, **params), grow(42, **params)
        np.testing.assert_array_equal(a.cells, b.cells)
        np.testing.assert_array_equal(a.edges, b.edges)
        plain = grow(42, **dict(params, bend_memory=0.))
        np.testing.assert_array_equal(a.cells[a.roots], plain.cells[plain.roots])
        self.assertFalse(np.array_equal(a.cells, plain.cells))
        self.assertTrue(np.issubdtype(a.cells.dtype, np.integer))
        lookup = {tuple(p): i for i, p in enumerate(a.cells)}
        physical = {tuple(sorted((i, lookup[tuple(p+d)])))
                    for i, p in enumerate(a.cells) for d in STEPS if tuple(p+d) in lookup}
        self.assertEqual(physical, set(map(tuple, a.edges)))
        self.assertTrue((np.bincount(a.owners) <= 200).all())
        for value in (-.1, 1.1, float('nan')):
            with self.assertRaisesRegex(ValueError, 'Bend memory'):
                grow(42, bend_memory=value)

    def test_local_branch_periods_and_child_cap(self):
        params = dict(width=160, height=50, root_count=3, cells_per_root=400,
                      trunk_length=200, axis_run=1, turn_angle=25., bend_memory=.8)
        base = grow(42, **params)
        disabled = grow(42, **params, branch_active_length=30, branch_quiet_length=0)
        np.testing.assert_array_equal(base.cells, disabled.cells)
        np.testing.assert_array_equal(base.edges, disabled.edges)
        changed = dict(params, child_length_cap=24, branch_active_length=24, branch_quiet_length=40)
        a, b = grow(42, **changed), grow(42, **changed)
        np.testing.assert_array_equal(a.cells, b.cells)
        np.testing.assert_array_equal(a.edges, b.edges)
        np.testing.assert_array_equal(a.cells[a.roots], base.cells[base.roots])
        self.assertGreater(sum(a.parents >= 0), 5)
        for path, parent in zip(a.paths, a.parents):
            if parent >= 0:
                self.assertLessEqual(len(path)-1, 24)
                self.assertIn(path[0], a.paths[parent])
        self.assertTrue((np.bincount(a.owners) <= 400).all())
        self.assertFalse(np.array_equal(base.cells, a.cells))


if __name__ == '__main__':
    unittest.main()
