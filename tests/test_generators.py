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

# Included in the existing Python/CTest suite as well as its standalone runner.
from test_curve_corpus import CurveCorpus
from test_curve_selection import CurveSelection
from test_population_selection import PopulationSelection


class Generators(unittest.TestCase):
    def test_block_light_matches_brute_force_manhattan_maximum(self):
        from _block_lighting import light_levels
        rng = np.random.default_rng(481)
        positions = rng.integers(-20, 21, (300, 3)).astype(float)+.5
        kinds = rng.choice([0, 1, 2], len(positions), p=[.85, .1, .05])
        sources = kinds > 0
        emission = np.where(kinds[sources] == 1, 14, 15)
        distance = np.abs(positions[:, None]-positions[sources]).sum(axis=2)
        expected = np.maximum(0, (emission-distance).max(axis=1))
        np.testing.assert_array_equal(light_levels(positions, kinds), expected)
        # L1 diagonal distance, exact cutoff, negative positions, no light relay.
        points = np.array([[0,0,0], [3,4,5], [-13,0,0], [14,0,0], [15,0,0]])+.5
        np.testing.assert_array_equal(light_levels(points, [1,0,0,0,0]), [14,2,1,0,0])
        np.testing.assert_array_equal(light_levels(points, np.zeros(5)), 0)
        self.assertEqual(light_levels(np.empty((0,3)), np.empty(0)).shape, (0,))
        # More than one query batch, without an all-pairs reference allocation.
        points = np.column_stack((np.arange(65540), np.zeros((65540,2))))+.5
        kinds = np.zeros(len(points), dtype=int)
        kinds[-1] = 2
        np.testing.assert_array_equal(light_levels(points, kinds),
                                      np.maximum(0, 15-(len(points)-1-np.arange(len(points)))))

    def test_block_light_brightness_bypass_and_material_identity(self):
        from _block_lighting import apply_lighting, light_colors
        points = np.array([[0,0,0], [1,0,0], [8,0,0], [20,0,0], [40,0,0]])+.5
        kinds = np.array([1,0,0,0,2])
        colors = np.tile(np.array([.8,.6,.4], np.float32), (5,1))
        before = colors.copy()
        lit = apply_lighting(points, colors, kinds, dict(pop_light_ambient=.1,
                            pop_light_sky=0, pop_light_brightness=0))
        np.testing.assert_allclose(lit[[0,4]], colors[[0,4]]*light_colors(np.array([14,15]),
                                  dict(pop_light_ambient=.1, pop_light_sky=0, pop_light_brightness=0)))
        self.assertTrue((lit[1] > lit[2]).all())
        self.assertTrue((lit[2] > lit[3]).all())
        np.testing.assert_allclose(lit[3], .1548*colors[3])
        np.testing.assert_array_equal(colors, before)
        self.assertIs(apply_lighting(points, colors, kinds, dict(pop_lighting=0)), colors)
        self.assertIs(apply_lighting(points, colors, kinds, dict(pop_light_ambient=1)), colors)
        # Identical colors do not make a candle emit. The lightmap has a baseline.
        dark = apply_lighting(points, colors, np.zeros(5), dict(pop_light_ambient=0,
                             pop_light_sky=0, pop_light_brightness=0))
        np.testing.assert_allclose(dark, colors*.0588, atol=1e-7)

    def test_unlit_candles_receive_sky_without_nearby_emitters(self):
        from _block_lighting import light_colors, apply_lighting
        points = np.array([[.5,.5,.5], [1000.5,.5,.5]])
        colors = np.ones((2,3), np.float32)
        sky_only = dict(pop_light_ambient=0, pop_light_sky=.2, pop_light_brightness=0)
        lit = apply_lighting(points, colors, np.zeros(2), sky_only)
        raw = .2*np.array([.8,.82,1.])*.96+.03
        np.testing.assert_allclose(lit, np.tile(raw*.96+.03, (2,1)), atol=1e-7)
        lifted = apply_lighting(points, colors, np.zeros(2), dict(sky_only, pop_light_brightness=1))
        self.assertTrue((lifted > lit).all())
        np.testing.assert_allclose(lifted, np.tile((1-(1-raw)**4)*.96+.03,(2,1)), atol=1e-7)
        # Brightness stays bounded/monotone and the cold tint fades in strong light.
        ramp = light_colors(np.arange(16), {})
        self.assertTrue((np.diff(ramp, axis=0) >= 0).all())
        self.assertTrue(((ramp >= 0) & (ramp <= 1)).all())
        self.assertGreater(ramp[0,2], ramp[0,0])
        np.testing.assert_allclose(ramp[-1], .99)

    def test_scar_lighting_preset_migration_and_gpu_reference(self):
        from _block_lighting import light_colors, migrate_parameters
        # Values read from the unmodified Minecraft 1.21.8 shader on the GPU:
        # sky factor .35, sky RGB (.8,.82,1), brightness 1, no extra ambient.
        expected = np.array([[.7579195,.766689,.8348941],
                             [.9356154,.9078372,.906943],
                             [.98999995,.98999995,.98999995]])
        np.testing.assert_allclose(light_colors(np.array([0,8,15]),dict(pop_light_ambient=0)),
                                   expected, atol=2e-6)
        for ambient in (.03, .07999999821186066):
            old=dict(pop_light_ambient=ambient,pop_light_sky=.2,pop_light_brightness=.5,pop_lighting=0)
            new=migrate_parameters(old)
            self.assertEqual(new['pop_light_sky'],.35)
            self.assertEqual(new['pop_light_brightness'],1.)
            self.assertEqual(new['pop_lighting'],0)
            self.assertEqual(migrate_parameters(new),new)
            self.assertEqual(old['pop_light_sky'],.2)
        custom=dict(pop_light_ambient=.1,pop_light_sky=.1,pop_light_brightness=.4)
        self.assertEqual(migrate_parameters(custom),custom)

    def test_block_light_worker_uses_surviving_materials_before_display_conversion(self):
        from unittest.mock import patch
        from _block_lighting import apply_lighting, light_colors
        points = np.array([[.5,.5,.5], [2.5,.5,.5], [3.5,.5,.5], [30.5,.5,.5]], np.float32)
        colors = np.tile(np.array([.8,.7,.6], np.float32), (4,1))
        kinds = np.array([1,0,2,0], np.int8)
        shapes = np.array([[1,.125,.125], [.125,.375,.125], [1,1,1], [.25,.375,.25]], np.float32)
        sizes = np.ones(4, np.float32)
        def population(*args, **kwargs):
            return (points.copy(), colors.copy(), sizes.copy()), dict(
                _block_shapes=shapes.copy(), _block_kinds=kinds.copy(),
                _fade_groups=np.arange(4), block_integration_limited=False)
        params = dict(curve_resolution=24, strand_length=5., extent=6., y_extent=2.,
                      pop_block_scale=8, pop_block_proxies=1, fade_xz=0, fade_y=0)
        with tempfile.TemporaryDirectory() as temp, patch.object(worker, 'populate_curves', population):
            output = Path(temp)/'points.bin'
            def run(keep, changes=None, native=False):
                def fade(*args, **kwargs):
                    return tuple(a[keep] for a in args[:3])
                with patch.object(worker, 'apply_to_stars', fade):
                    response = worker.generate_request(dict(generator='density_filament_curves', count=100,
                        seed=42, world_units='blocks' if native else '', params=dict(params, **(changes or {}))),
                        ROOT/'generators', output)
                self.assertTrue(response['ok'], response.get('error'))
                self.assertFalse(any(k.startswith('_') for k in response))
                return output.read_bytes(), np.frombuffer(output.with_suffix('.stars.bin').read_bytes()[16:], '<f4').reshape(-1,10)
            _, complete = run(np.arange(4))
            # Remove the full block: its nearby candle must lose that source's light.
            keep = np.array([0,1,3])
            lines, faded = run(keep)
            np.testing.assert_array_equal(faded[:,:3], points[keep]/8)
            np.testing.assert_array_equal(faded[:,7:], shapes[keep])
            np.testing.assert_array_equal(faded[:,3:6], apply_lighting(points[keep], colors[keep], kinds[keep], {}))
            self.assertTrue((faded[1,3:6] < complete[1,3:6]).all())
            same_lines, unlit = run(keep, dict(pop_lighting=0))
            self.assertEqual(lines, same_lines)
            np.testing.assert_array_equal(faded[:,[0,1,2,6,7,8,9]], unlit[:,[0,1,2,6,7,8,9]])
            np.testing.assert_array_equal(unlit[:,3:6], colors[keep])
            _, native = run(keep, native=True)
            np.testing.assert_array_equal(native[:,:3], points[keep])
            np.testing.assert_array_equal(native[:,3:6], faded[:,3:6])
            _, no_sources = run(np.array([1,3]))
            np.testing.assert_allclose(no_sources[:,3:6], colors[[1,3]]*light_colors(np.zeros(2), {}))
            _, empty = run(np.array([], dtype=int))
            self.assertEqual(empty.shape, (0,10))

    def test_branching_connectivity_budget_bounds_and_determinism(self):
        from unittest.mock import patch
        from _branching_field import grow_branches
        def direction(field, points, preferred=None):
            return np.tile([1.,0.,0.],(len(points),1)), np.zeros_like(points), np.ones(len(points))
        cells = np.array([[0,0,0],[0,70,0]])
        report = {}
        kwargs = dict(length=600.,variation=.5,response=4.,wandering=0.,spacing=24.,angle=45.)
        with patch('_branching_field.DensityShape.sample',direction):
            paths, owners = grow_branches(np.ones((9,9,9)),np.full(3,150.),cells,42,report=report,**kwargs)
            again, other = grow_branches(np.ones((9,9,9)),np.full(3,150.),cells,42,**kwargs)
        self.assertGreater(report['branch_count'],4)
        np.testing.assert_array_equal(owners,other)
        lengths = np.zeros(len(cells))
        for i,(p,q) in enumerate(zip(paths,again)):
            np.testing.assert_array_equal(p,q)
            self.assertTrue((np.abs(p)<=150.+1e-9).all())
            lengths[report['root_ids'][i]] += np.linalg.norm(np.diff(p,axis=0),axis=1).sum()
            parent = report['parents'][i]
            if parent < 0:
                self.assertTrue(np.any(np.all(p==owners[i]+.5,axis=1)))
            else:
                self.assertLess(parent,i)
                self.assertTrue(np.any(np.all(paths[parent]==p[0],axis=1)))
                np.testing.assert_array_equal(owners[parent],owners[i])
                # Initial child segment actually diverges from the X trunk.
                if report['parents'][parent] < 0:
                    h=(p[1]-p[0])/np.linalg.norm(p[1]-p[0])
                    self.assertAlmostEqual(abs(h[0]),np.cos(np.pi/4))
        self.assertTrue((lengths <= report['root_budgets']+1e-8).all())

    def test_branching_active_worker_uses_root_controls_and_shared_population(self):
        from unittest.mock import patch
        catalog,modules,errors=worker.load_catalog(ROOT/'generators',block_units=True,density_graph=True)
        self.assertFalse(errors)
        g=modules['density_filament_branching']
        with patch('_field_curves.grow_field',side_effect=AssertionError('old merging used')), \
             patch('_stable_density_curves.extract_paths',side_effect=AssertionError('guide extraction')), \
             patch.object(g,'block_seeds',return_value=np.array([[0,0,0]])) as birth:
            attributes,paths,colors=g.generate_population_source(1,42,extent=64.,y_extent=32.,noise_scale=30.,
                field_resolution=24,branch_root_rate=.5,branch_length=400.,branch_spacing=24.,seed_rate=999.)
        self.assertEqual(birth.call_args.args[3],.5)
        self.assertGreater(len(paths),1)
        self.assertEqual(len(colors),len(paths))
        self.assertEqual(len(attributes[0]),sum(2*(len(p)-1) for p in paths))

    def test_proximity_contacts_reach_parallel_segments_and_preserve_priority(self):
        from _proximity_contacts import ProximityContacts
        def advance(index, a, b, owner, budget=100.):
            end, hit = index.advance_batch(np.array([a], dtype=float), np.array([b], dtype=float),
                                          np.array([owner]), np.array([budget]))
            return end[0], hit[0]
        contacts = ProximityContacts(4., 30.)
        advance(contacts, (0, 0, 0), (20, 0, 0), 0)
        target, hit = advance(contacts, (4, 3, 0), (12, 3, 0), 1)
        self.assertTrue(hit)
        np.testing.assert_array_equal(target, [4, 0, 0])
        self.assertFalse(advance(contacts, (4, 5, 0), (12, 5, 0), 2)[1])
        self.assertFalse(advance(contacts, (9, -3, 0), (9, 3, 0), 3)[1])
        own = ProximityContacts(4., 30.)
        advance(own, (0, 0, 0), (20, 0, 0), 0)
        self.assertFalse(advance(own, (4, 3, 0), (12, 3, 0), 0)[1])
        budget_contacts = ProximityContacts(4., 30.)
        advance(budget_contacts, (0, 0, 0), (20, 0, 0), 0)
        self.assertFalse(advance(budget_contacts, (4, 3, 0), (12, 3, 0), 4, budget=2.)[1])
        # A long step cannot skip a short eligible segment in its middle.
        contacts = ProximityContacts(2., 30.)
        advance(contacts, (10, 0, 0), (12, 0, 0), 0)
        self.assertTrue(advance(contacts, (0, 1, 0), (30, 1, 0), 1)[1])

    def test_proximity_contacts_allow_old_targets_but_preserve_receiving_route(self):
        from _proximity_contacts import ProximityContacts
        contacts = ProximityContacts(4., 30., np.full(3, 40.))
        def advance(a, b, owner):
            return contacts.advance_batch(np.array([a], dtype=float), np.array([b], dtype=float),
                                          np.array([owner]), np.array([100.]))[1][0]
        advance((0,0,0), (20,0,0), 5)
        # A fresh higher-priority front is not a target yet.
        self.assertFalse(advance((4,3,0), (12,3,0), 0))
        # Once established it may receive a lower-priority owner too.
        self.assertTrue(advance((12,3,0), (16,3,0), 0))
        bridge = contacts.bridges[0]
        np.testing.assert_array_equal(bridge[0], [12,3,0])
        np.testing.assert_array_equal(bridge[-1], [12,0,0])
        self.assertTrue((np.abs(bridge) <= 40.).all())
        # Receiver 5 cannot then join its feeder 0, even after the feeder ages.
        self.assertFalse(advance((20,0,0), (24,0,0), 5))
        self.assertFalse(advance((24,0,0), (28,0,0), 5))
        # The opposite tip of source 0 can still join the same receiver.
        self.assertTrue(advance((4,3,0), (0,3,0), 0))

    def test_proximity_growth_consolidates_parallel_roots_without_losing_main_route(self):
        from unittest.mock import patch
        from _field_curves import grow_field
        def direction(field, points, preferred=None):
            return np.tile([1., 0., 0.], (len(points), 1)), np.zeros_like(points), np.ones(len(points))
        cells = np.array([[0, y, 0] for y in range(0, 12, 3)])
        cfg = dict(response=4., wandering=0., join_distance=12.)
        with patch('_field_curves.DensityShape.sample', direction):
            paths, owners = grow_field(np.ones((9,9,9)), np.full(3,100.), cells, 42, 100., 0., **cfg)
            repeat, _ = grow_field(np.ones((9,9,9)), np.full(3,100.), cells, 42, 100., 0., **cfg)
        lengths = np.array([np.linalg.norm(np.diff(p, axis=0), axis=1).sum() for p in paths])
        self.assertAlmostEqual(lengths[0], 100.)
        self.assertLess(lengths[1:].max(), 25.)
        self.assertLess(lengths.sum(), 160.) # Independent growth would be 400.
        np.testing.assert_array_equal(owners, cells)
        for path, other in zip(paths, repeat):
            np.testing.assert_array_equal(path, other)

    def test_packed_cell_union_preserves_lexicographic_cells_and_inverse(self):
        from _block_population import unique_cells
        rng = np.random.default_rng(392)
        for cells in (rng.integers(-300, 300, (20000,3)), np.zeros((4,3), dtype=np.int64),
                      np.array([[-2**22]*3, [2**22]*3, [0]*3], dtype=np.int64)):
            old = np.unique(cells, axis=0, return_inverse=True)
            new = unique_cells(cells)
            for a,b in zip(old,new):
                np.testing.assert_array_equal(a,b)

    def test_block_contact_traversal_boundaries_and_negative_coordinates(self):
        from _block_contacts import crossed_cells
        def cells(a, b):
            return [c for c, _, _ in crossed_cells(a, b)]
        self.assertEqual(cells((.5,.5,.5), (4.5,.5,.5)), [(i,0,0) for i in range(5)])
        self.assertEqual(cells((0.,.5,.5), (-3.,.5,.5)), [(-1,0,0),(-2,0,0),(-3,0,0)])
        self.assertEqual(cells((.5,.5,.5), (2.5,2.5,2.5)), [(0,0,0),(1,1,1),(2,2,2)])
        self.assertEqual(cells((.5,1.,.5), (2.5,1.,.5)), [(0,1,0),(1,1,0),(2,1,0)])

    def test_block_contact_attaches_aligned_arrivals_but_not_crossings(self):
        from _block_contacts import BlockContacts
        index = BlockContacts(30.)
        end, joined = index.advance((0.2,.2,.5), (8.8,.2,.5), 0, 20.)
        self.assertFalse(joined)
        end, joined = index.advance((7.8,.8,.5), (2.2,.8,.5), 1, 20.)
        self.assertTrue(joined)  # Opposite heading is the same unoriented strand.
        np.testing.assert_allclose(end, (7.8,.2,.5))
        end, joined = index.advance((4.5,-2.,.5), (4.5,3.,.5), 2, 20.)
        self.assertFalse(joined)
        # A long step must see the occupied block in its middle, not just its endpoint.
        index = BlockContacts(30.)
        index.advance((2.2,.2,.5), (2.8,.2,.5), 0, 20.)
        end, joined = index.advance((.5,.8,.5), (5.5,.8,.5), 1, 20.)
        self.assertTrue(joined)
        np.testing.assert_allclose(end, (2.2,.2,.5))
        # Both halves of the same source ignore one another.
        end, joined = index.advance((.5,.8,.5), (5.5,.8,.5), 0, 20.)
        self.assertTrue(joined)  # Can still hit source 1's accepted connector.
        own = BlockContacts(30.)
        own.advance((.5,.5,.5), (2.5,.5,.5), 7, 20.)
        self.assertFalse(own.advance((2.5,.5,.5), (.5,.5,.5), 7, 20.)[1])

    def test_block_contact_priority_budget_and_multiple_occupants(self):
        from _block_contacts import BlockContacts
        index = BlockContacts(30.)
        self.assertFalse(index.advance((.2,.2,.5),(5.8,.2,.5),0,10.)[1])
        self.assertTrue(index.advance((.2,.8,.5),(5.8,.8,.5),1,10.)[1])
        # The accepted first path can continue after the second attaches.
        self.assertFalse(index.advance((5.8,.2,.5),(8.8,.2,.5),0,10.)[1])
        short = BlockContacts(30.)
        short.advance((.2,.1,.5),(.8,.1,.5),0,10.)
        self.assertFalse(short.advance((.2,.9,.5),(.3,.9,.5),1,.1)[1])
        # Store transverse occupants too; they must not hide aligned targets.
        multi = BlockContacts(30.)
        multi.advance((.2,.5,.5),(.8,.5,.5),0,10.)
        multi.advance((.5,.2,.5),(.5,.8,.5),1,10.)
        self.assertTrue(multi.advance((.6,.1,.5),(.6,.9,.5),2,10.)[1])

    def test_block_contact_growth_keeps_outer_continuations_and_shared_contact(self):
        from unittest.mock import patch
        from _field_curves import grow_field
        def direction(field, points, preferred=None):
            return np.tile([1., 0., 0.], (len(points), 1)), np.zeros_like(points), np.ones(len(points))
        rho = np.ones((9, 9, 9))
        half = np.full(3, 100.)
        cells = np.array([[0, 0, 0], [6, 0, 0]])
        config = dict(response=4., wandering=0.)
        with patch('_field_curves.DensityShape.sample', direction):
            separate, _ = grow_field(rho, half, cells, 42, 20., 0., joining=False, **config)
            report = {}
            joined, _ = grow_field(rho, half, cells, 42, 20., 0., joining=True, report=report, **config)
            again, _ = grow_field(rho, half, cells, 42, 20., 0., joining=True, **config)
        self.assertGreater(report['joined_tips'], 0)
        self.assertEqual(len(joined), 2)
        lengths = lambda paths: [np.linalg.norm(np.diff(p, axis=0), axis=1).sum() for p in paths]
        self.assertLess(sum(lengths(joined)), sum(lengths(separate)))
        self.assertTrue(all(length <= 20.+1e-8 for length in lengths(joined)))
        # The two facing tips meet; both outward continuations survive. No
        # receiving geometry moves and the shared portion is not drawn twice.
        self.assertEqual(joined[0][0, 0], separate[0][0, 0])
        self.assertEqual(joined[1][-1, 0], separate[1][-1, 0])
        np.testing.assert_array_equal(joined[0][-1], joined[1][0])
        for a, b in zip(joined, again):
            np.testing.assert_array_equal(a, b)

    def test_direct_field_growth_preserves_roots_and_finite_budgets(self):
        from _field_curves import grow_field
        density = np.ones((17, 17, 17))
        half = np.array([50., 50., 50.])
        cells = np.array([[0, 0, 0], [12, 3, -4]])
        paths, owners = grow_field(density, half, cells, 42, 20., 0., response=4., wandering=0.)
        np.testing.assert_array_equal(owners, cells)
        for path, cell in zip(paths, cells):
            self.assertTrue(np.any(np.all(path == cell+.5, axis=1)))
            self.assertAlmostEqual(np.linalg.norm(np.diff(path, axis=0), axis=1).sum(), 20.)
        single, _ = grow_field(density, half, cells[:1], 42, 20., 0., response=4., wandering=0.)
        np.testing.assert_array_equal(single[0], paths[0])
        bounded, _ = grow_field(density, np.ones(3)*2, cells[:1], 42, 100., 0., response=4., wandering=0.)
        self.assertTrue(np.all(np.abs(bounded[0]) <= 2.+1e-10))
        self.assertTrue(np.any(np.isclose(np.abs(bounded[0][[0, -1]]), 2.)))

    def test_active_field_growth_never_extracts_or_projects_guides(self):
        from unittest.mock import patch
        catalog, modules, errors = worker.load_catalog(ROOT/'generators', block_units=True, density_graph=True)
        self.assertFalse(errors)
        g = modules['density_filament_curves']
        import _grid_density_curves as grid
        cells = np.array([[0, 0, 0], [2, 0, 0]])
        with patch.object(g, 'extract_paths', side_effect=AssertionError('guide extraction')), \
             patch.object(grid, 'project_seeds', side_effect=AssertionError('seed projection')), \
             patch.object(g, 'block_seeds', return_value=cells):
            attributes, paths, colors = g.generate_population_source(10, 42,
                extent=32., y_extent=16., noise_scale=20., field_resolution=24,
                seed_rate=500., strand_length=20.)
        self.assertEqual(len(paths), 2)
        for path, cell in zip(paths, cells):
            self.assertTrue(np.any(np.all(path == cell+.5, axis=1)))
        self.assertTrue(np.isfinite(attributes[0]).all())

    def test_block_curve_seeds_are_stable_density_thresholds(self):
        from _grid_density_curves import block_seeds
        half = np.array([5., 3., 5.])
        density = np.ones((11, 7, 11))
        def selected(rho, rate, power=1, bounds=half):
            return {tuple(p) for p in block_seeds(rho, bounds, 42, rate, power, 1, 1)}
        low = selected(density, 100000)
        high = selected(density, 300000)
        self.assertTrue(low < high)
        self.assertEqual(low, selected(density, 100000))
        uniform = selected(np.zeros_like(density), 100000, 0)
        self.assertEqual(low, uniform)
        from _block_population import cell_uniform
        all_cells = np.stack(np.meshgrid(np.arange(-5, 5), np.arange(-3, 3), np.arange(-5, 5), indexing='ij'), axis=-1).reshape(-1, 3)
        expected = all_cells[cell_uniform(all_cells, 42, stream=17611) < .1]
        self.assertEqual(low, {tuple(p) for p in expected})
        density[:5] = .2
        from _stable_density_curves import sample_support
        from _grid_density_curves import _mean_seed_weight
        for power in (.5, 1., 2., 4.):
            weights = sample_support(density, all_cells+.5, half)**power
            self.assertAlmostEqual(_mean_seed_weight(density, half,
                np.array([-5, -3, -5]), np.array([10, 6, 10]), power), weights.mean())
            expected = all_cells[cell_uniform(all_cells, 42, stream=17611) < .3*weights/weights.mean()]
            self.assertEqual(selected(density, 300000, power), {tuple(p) for p in expected})
            self.assertEqual(selected(density, 300000, power), selected(density*7, 300000, power))
        self.assertFalse(selected(np.zeros_like(density), 300000))
        larger = selected(np.ones_like(density), 100000, bounds=np.array([7., 3., 7.]))
        self.assertTrue(low < larger)
        self.assertTrue(all(-5 <= p[0]+.5 <= 5 and -3 <= p[1]+.5 <= 3 for p in low))

    def test_seed_weight_mean_matches_block_centers_in_fractional_regions(self):
        from _grid_density_curves import _mean_seed_weight
        from _stable_density_curves import sample_support
        density = np.random.default_rng(71).random((7, 9, 11))
        for half in (np.array([2.7, 8.3, 4.1]), np.array([3.6, 2.9, 9.2])):
            region = half*np.array([.8, .6, .8])
            low = np.ceil(-region-.5).astype(int)
            high = np.floor(region-.5).astype(int)
            shape = high-low+1
            centers = np.stack(np.meshgrid(*(np.arange(a,b+1)+.5 for a,b in zip(low,high)), indexing='ij'), axis=-1).reshape(-1,3)
            for power in (.5, 1., 2., 4.):
                expected = np.mean(sample_support(density, centers, half)**power)
                self.assertAlmostEqual(_mean_seed_weight(density, half, low, shape, power), expected)

    def test_signed_y_seed_regions_preserve_symmetric_settings_and_normalize(self):
        from _grid_density_curves import block_seeds
        from _block_population import cell_uniform
        from _stable_density_curves import sample_support
        import density_filament_curves as g
        density = np.random.default_rng(8).random((7, 9, 11))
        half = np.array([5., 4., 5.])
        old = block_seeds(density, half, 42, 200000., 1., 1., .5)
        signed = block_seeds(density, half, 42, 200000., 1., 1.,
                             seed_y_pos=.5, seed_y_neg=.5)
        np.testing.assert_array_equal(old, signed)
        migrated = g.migrate_parameters(dict(seed_y=.3, seed_y_pos=.7))
        self.assertEqual(migrated['seed_y_pos'], .7)
        self.assertEqual(migrated['seed_y_neg'], .3)
        for positive, negative in ((1., 0.), (0., 1.), (.75, .25), (0., 0.), (.75, -.25), (-.25, .75)):
            cells = np.stack(np.meshgrid(np.arange(-5, 5),
                np.arange(int(-4*negative), int(4*positive)), np.arange(-5, 5),
                indexing='ij'), axis=-1).reshape(-1, 3)
            all_selected = block_seeds(density, half, 42, 1e6, 0., 1.,
                                      seed_y_pos=positive, seed_y_neg=negative)
            np.testing.assert_array_equal(cells, all_selected)
            weighted = block_seeds(density, half, 42, 200000., 2., 1.,
                                  seed_y_pos=positive, seed_y_neg=negative)
            weights = sample_support(density, cells+.5, half)**2
            expected = (cells[cell_uniform(cells, 42, stream=17611) < .2*weights/weights.mean()]
                        if len(cells) else cells)
            np.testing.assert_array_equal(weighted, expected)

    def test_curve_joins_use_max_budget_and_stop_at_failed_contact(self):
        from _grid_density_curves import grow_intervals
        merged = grow_intervals(np.array([20., 22.]), np.array([12., 20.]), 100.)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['seeds'], 2)
        self.assertAlmostEqual(merged[0]['right']-merged[0]['left'], 20.)
        separate = grow_intervals(np.array([10., 22.]), np.array([12., 12.]), 100.)
        self.assertEqual(len(separate), 2)
        self.assertAlmostEqual(separate[0]['right'], separate[1]['left'])
        for p in separate:
            self.assertLessEqual(p['right']-p['left'], 12.+1e-8)
        chain = grow_intervals(np.arange(10., 190., 4.), np.full(45, 16.), 200.)
        self.assertGreater(len(chain), 1)
        self.assertTrue(all(p['right']-p['left'] <= 16.+1e-8 for p in chain))
        # Joining cannot restart a previously exhausted outer tip.
        stopped = grow_intervals(np.array([20., 28.]), np.array([4., 20.]), 100.)
        self.assertAlmostEqual(stopped[0]['left'], 18.)

    def test_block_seed_projection_budgets_and_closed_seam(self):
        from _grid_density_curves import seed_curves, grow_intervals
        path = np.array([[-20., 0., 0.], [20., 0., 0.]])
        cells = np.array([[-8, 0, 0], [2, 0, 0], [12, 0, 0]])
        curves, owners, reports = seed_curves([path], cells, 42, 6., 0.)
        self.assertEqual(len(curves), 3)
        for curve, report in zip(curves, reports):
            self.assertAlmostEqual(np.linalg.norm(np.diff(curve, axis=0), axis=1).sum(), 6.)
            self.assertEqual(report['budget'], 6.)
        short, _, report_short = seed_curves([path], cells, 42, 3., .5)
        self.assertTrue(all(np.linalg.norm(np.diff(p, axis=0), axis=1).sum() <= 4.5+1e-8 for p in short))
        closed = grow_intervals(np.array([1., 39.]), np.array([10., 10.]), 40., True)
        self.assertEqual(len(closed), 1)
        self.assertAlmostEqual(closed[0]['right']-closed[0]['left'], 10.)
        loop = np.array([[0., 0., 0.], [10., 0., 0.], [10., 0., 10.], [0., 0., 10.], [0., 0., 0.]])
        curves, _, reports = seed_curves([loop], np.array([[0, 0, 0], [0, 0, 9]]), 42, 50., 0.)
        self.assertEqual(len(curves), 1)
        self.assertAlmostEqual(np.linalg.norm(np.diff(curves[0], axis=0), axis=1).sum(), 40.)

    def test_grid_curve_schema_and_join_invariants(self):
        from _grid_density_curves import grow_intervals
        catalog, _, errors = worker.load_catalog(ROOT/'generators', block_units=True, density_graph=True)
        self.assertFalse(errors)
        schema = next(s for s in catalog if s['id'] == 'density_filament_curves')
        keys = {p['key']: p for p in schema['parameters']}
        self.assertNotIn('seed_spacing', keys)
        self.assertEqual(keys['seed_rate']['default'], 500.)
        self.assertEqual(keys['seed_rate']['slider_max'], 100.)
        self.assertIn('growth_join', keys)
        self.assertIn('strand_length', keys)
        self.assertNotIn('branch_root_rate', keys)
        branching = next(s for s in catalog if s['id'] == 'density_filament_branching')
        branch_keys = {p['key']: p for p in branching['parameters']}
        self.assertEqual(branch_keys['branch_root_rate']['default'], .5)
        self.assertEqual(branch_keys['branch_length']['default'], 1200.)
        self.assertNotIn('seed_rate', branch_keys)
        self.assertNotIn('growth_join', branch_keys)
        self.assertNotIn('strand_length', branch_keys)
        self.assertEqual(branch_keys['extent']['scope'], 'density_field')
        self.assertNotIn('seed_y', keys)
        self.assertEqual(keys['seed_y_pos']['min'], -1.)
        self.assertEqual(keys['seed_y_neg']['default'], .65)
        self.assertEqual(keys['seed_y_pos']['zone_pair'], 'seed_y_neg')
        self.assertTrue(keys['seed_y_neg']['zone_hidden'])
        self.assertEqual(keys['seed_xz']['zone_kind'], 'seed')
        self.assertEqual(keys['fade_y_pos_width']['zone_pair'], 'fade_y_neg_width')
        self.assertEqual(keys['fade_y_pos_width']['group'], 'Y edge fade')
        self.assertNotIn('fade_y_pos', keys)
        self.assertNotIn('fade_y_neg', keys)
        self.assertEqual(keys['fade_y_pos_width']['enabled_if'], 'fade_y_enabled')
        self.assertEqual(keys['fade_y_pos_width']['min'], 0.)
        self.assertEqual(keys['fade_y_neg_width']['max'], 2.)
        self.assertEqual(keys['fade_xz_width']['zone_kind'], 'fade')
        self.assertEqual(keys['seed_y_pos']['zone_extent'], 'y_extent')
        self.assertEqual(keys['seed_xz']['zone_extent'], 'extent')
        order = list(keys)
        self.assertEqual(order[order.index('seed_xz')+1], 'seed_y_pos')
        self.assertEqual(keys['seed_density_power']['min'], 0.)
        self.assertEqual(keys['seed_density_power']['default'], 1.)
        self.assertEqual(keys['length_variation']['default'], .5)
        rng = np.random.default_rng(453)
        for closed in (False, True):
            for _ in range(50):
                roots = np.sort(rng.uniform(0., 100., 30))
                budgets = rng.uniform(1., 60., len(roots))
                parts = grow_intervals(roots, budgets, 100., closed)
                self.assertEqual(sum(p['seeds'] for p in parts), len(roots))
                for part in parts:
                    self.assertLessEqual(part['right']-part['left'], min(part['budget'], 100.)+1e-7)
                    self.assertEqual(part['budget'], budgets[part['owner']])
                for a, b in zip(parts, parts[1:]):
                    self.assertLessEqual(a['right'], b['left']+1e-7)
                if closed:
                    self.assertLessEqual(parts[-1]['right'], parts[0]['left']+100.+1e-7)
                else:
                    self.assertGreaterEqual(parts[0]['left'], -1e-7)
                    self.assertLessEqual(parts[-1]['right'], 100.+1e-7)

    def test_original_density_influence_concentrates_both_samplers(self):
        from _population import populate_curves
        from _block_population import cell_masses
        x = np.linspace(-10, 10, 41)
        rho = .02 + np.exp(-x*x/4)
        source = (np.broadcast_to(rho[:, None, None], (41, 9, 9)).copy(), np.array([10., 2., 2.]))
        paths = [np.array([[-8., .5, .5], [8., .5, .5]])]
        colors = np.ones((1, 3))
        params = dict(pop_density=30., pop_taper=0., pop_spread_xz=0., pop_spread_y=0.,
                      pop_curve_density_variation=0., pop_clumping=0., pop_block_proxies=0)
        fractions, block_fractions = [], []
        for strength in (0., 1., 2.):
            config = dict(params, pop_source_density=strength)
            stars, stats = populate_curves(paths, colors, 42, config, density_source=source)
            fractions.append(np.mean(np.abs(stars[0][:, 0]) < 2))
            self.assertEqual(stats['population_candidates'], 480)
            cells, mass, _, _ = cell_masses(paths, colors, 42, dict(config, pop_blocks=1), density_source=source)
            block_fractions.append(mass[np.abs(cells[:, 0]+.5) < 2].sum()/mass.sum())
        self.assertLess(fractions[0], .3)
        self.assertGreater(fractions[1], .7)
        self.assertGreater(fractions[2], fractions[1]+.08)
        np.testing.assert_allclose(fractions, block_fractions, atol=.02)
        old, _ = populate_curves(paths, colors, 42, params)
        off, _ = populate_curves(paths, colors, 42, dict(params, pop_source_density=0), density_source=source)
        for a, b in zip(old, off):
            np.testing.assert_array_equal(a, b)
        old_cells = cell_masses(paths, colors, 42, dict(params, pop_blocks=1))
        off_cells = cell_masses(paths, colors, 42, dict(params, pop_blocks=1, pop_source_density=0), density_source=source)
        for a, b in zip(old_cells[:3], off_cells[:3]):
            np.testing.assert_array_equal(a, b)

    def test_original_density_changes_mean_rates_between_curves(self):
        from _population import populate_curves
        rho = np.linspace(.1, 1.9, 21)
        source = (np.broadcast_to(rho[:, None, None], (21, 9, 21)).copy(), np.array([5., 2., 5.]))
        paths = [np.array([[x, .5, -4.], [x, .5, 4.]]) for x in (-4., 4.)]
        params = dict(pop_density=100., pop_taper=0., pop_spread_xz=0., pop_spread_y=0.,
                      pop_curve_density_variation=0., pop_source_density=1.)
        stars, _ = populate_curves(paths, np.ones((2, 3)), 42, params, density_source=source)
        self.assertGreater(np.sum(stars[0][:, 0] > 0), 5*np.sum(stars[0][:, 0] < 0))

    def test_original_density_worker_reuses_field_and_preserves_curves(self):
        from unittest.mock import patch
        import _density_field as field
        with tempfile.TemporaryDirectory() as directory, patch.object(field, 'build_density', wraps=field.build_density) as build:
            path = Path(directory)/'points.bin'
            request = dict(generator='density_filament_curves', count=100, seed=42,
                world_units='blocks', density_graph=True, density_field={'field_resolution': 24},
                params={'pop_source_density': 0})
            before = worker.generate_request(request, ROOT/'generators', path)
            self.assertTrue(before['ok'], before.get('error'))
            curves = path.read_bytes()
            old_stars = path.with_suffix('.stars.bin').read_bytes()
            request['params']['pop_source_density'] = 1
            after = worker.generate_request(request, ROOT/'generators', path)
            self.assertTrue(after['ok'], after.get('error'))
            self.assertEqual(path.read_bytes(), curves)
            self.assertNotEqual(path.with_suffix('.stars.bin').read_bytes(), old_stars)
            self.assertEqual(build.call_count, 2)  # One field evaluation per job.

    def test_density_graph_consumers_receive_identical_upstream_arrays(self):
        from unittest.mock import patch
        import _density_field as field
        values = {p['key']: p['default'] for p in field.PARAMETERS}
        values.update(extent=128., y_extent=32., noise_scale=64., field_resolution=24)
        evaluated = []
        original = field.build_density
        def record(*args, **kwargs):
            result = original(*args, **kwargs)
            evaluated.append(result)
            return result
        with tempfile.TemporaryDirectory() as directory, patch.object(field, 'build_density', side_effect=record):
            for name in ('density_filament_curves', 'noise_filaments_branches'):
                response = worker.generate_request(dict(generator=name, count=200, seed=42,
                    world_units='blocks', density_graph=True, density_field=values,
                    params={'_block_units': 1}), ROOT/'generators', Path(directory)/(name+'.bin'))
                self.assertTrue(response['ok'], response.get('error'))
                self.assertEqual(response['density_field'], values)
                self.assertFalse(field.KEYS & response['params'].keys())
                schema = next(s for s in response['catalog'] if s['id'] == name)
                upstream = [p for p in schema['parameters'] if p.get('scope') == 'density_field']
                self.assertEqual(upstream, field.PARAMETERS)
                self.assertNotIn('frequency', [p['key'] for p in schema['parameters']])
        self.assertEqual(len(evaluated), 2)
        for first, second in zip(*evaluated):
            np.testing.assert_array_equal(first, second)

    def test_direct_density_block_migration_preserves_scene_once(self):
        import _density_field as field
        old_params = dict(extent=8., y_extent=2., frequency=2., broad_strength=0.,
                          star_size=.05, width=.08, octaves=3, roughness=.2)
        legacy, _, _ = worker.load_catalog(ROOT/'generators')
        defaults = {p['key']: p['default'] for p in next(s for s in legacy if s['id']=='noise_filaments_branches')['parameters']}
        defaults.update(old_params)
        upstream = {k: defaults[k] for k in field.KEYS if k in defaults}
        upstream.update(extent=128., y_extent=32., noise_scale=64., field_resolution=96)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'points.bin'
            request = dict(generator='noise_filaments_branches', count=300, seed=42, params=old_params)
            before = worker.generate_request(request, ROOT/'generators', path)
            self.assertTrue(before['ok'], before.get('error'))
            old = np.frombuffer(path.read_bytes()[16:], '<f4').reshape(-1, 7)
            request.update(world_units='blocks', density_graph=True, density_field=upstream, legacy_display_scale=16)
            after = worker.generate_request(request, ROOT/'generators', path)
            self.assertTrue(after['ok'], after.get('error'))
            packed = path.read_bytes()
            new = np.frombuffer(packed[16:], '<f4').reshape(-1, 7)
            np.testing.assert_array_equal(new[:, :3], old[:, :3]*16)
            np.testing.assert_array_equal(new[:, 6], old[:, 6]*16)
            np.testing.assert_array_equal(new[:, 3:6], old[:, 3:6])
            request.update(params=after['params'], density_field=after['density_field'])
            again = worker.generate_request(request, ROOT/'generators', path)
            self.assertTrue(again['ok'], again.get('error'))
            self.assertEqual(path.read_bytes(), packed)

    def test_shared_density_preserves_inherited_physical_range(self):
        from unittest.mock import patch
        catalog, modules, errors = worker.load_catalog(ROOT/'generators')
        self.assertFalse(errors)
        module = modules['noise_filaments_branches']
        # Skip expensive density generation; validate the exact parameters passed
        # to the consumer, including outside its historical slider limits.
        with tempfile.TemporaryDirectory() as directory, patch.object(worker, 'load_catalog', return_value=(catalog, modules, [])), patch.object(module, 'generate', return_value=(np.zeros((2, 3)), np.ones((2, 3)), .04)) as generate:
            result = worker.generate_request(dict(generator='noise_filaments_branches', count=2, seed=42,
                params=dict(extent=120., y_extent=.001, frequency=.02), shared_density_field=True),
                ROOT/'generators', Path(directory)/'points.bin')
            self.assertTrue(result['ok'], result.get('error'))
            self.assertEqual(generate.call_args.kwargs['extent'], 120.)
            self.assertEqual(generate.call_args.kwargs['frequency'], .02)
            self.assertEqual(generate.call_args.kwargs['y_extent'], .001)

    def test_native_block_migration_preserves_scene_and_is_idempotent(self):
        import struct
        old_params = dict(extent=8., y_extent=2., noise_scale=3.2,
            curve_resolution=32, strand_length=8., pop_block_scale=8,
            pop_density=5., pop_spread=.04, pop_clumping=1.2,
            pp_warp=1, pp_warp_amount=.1, pp_warp_scale=2.,
            fade_y=1, fade_y_width=.5, fade_y_density_strength=1.)
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory)/'old.bin'
            new = Path(directory)/'new.bin'
            request = dict(generator='density_filament_curves', count=100, seed=42, params=old_params)
            before = worker.generate_request(request, ROOT/'generators', old)
            after = worker.generate_request(dict(request, world_units='blocks'), ROOT/'generators', new)
            self.assertTrue(before['ok'], before.get('error'))
            self.assertTrue(after['ok'], after.get('error'))
            self.assertEqual(before['star_count'], after['star_count'])
            a = np.frombuffer(old.read_bytes()[16:], '<f4').reshape(-1, 7)
            b = np.frombuffer(new.read_bytes()[16:], '<f4').reshape(-1, 7)
            np.testing.assert_allclose(b[:, :3], a[:, :3]*8, atol=1e-5)
            np.testing.assert_array_equal(b[:, 3:6], a[:, 3:6])
            a = np.frombuffer(old.with_suffix('.stars.bin').read_bytes()[16:], '<f4').reshape(-1, 10)
            packed = new.with_suffix('.stars.bin').read_bytes()
            b = np.frombuffer(packed[16:], '<f4').reshape(-1, 10)
            np.testing.assert_array_equal(b[:, :3], a[:, :3]*8)
            np.testing.assert_array_equal(b[:, 3:6], a[:, 3:6])
            np.testing.assert_array_equal(b[:, 6], np.ones(len(b)))
            np.testing.assert_array_equal(b[:, 7:], a[:, 7:])
            np.testing.assert_array_equal(b[:, :3] % 1, np.full((len(b), 3), .5))
            self.assertEqual(after['params']['pop_density'], 5/8)
            self.assertEqual(after['params']['extent'], 64)
            self.assertNotIn('pop_block_scale', after['params'])
            again = worker.generate_request(dict(request, world_units='blocks', params=after['params']), ROOT/'generators', new)
            self.assertTrue(again['ok'], again.get('error'))
            self.assertEqual(again['params'], after['params'])
            self.assertEqual(new.with_suffix('.stars.bin').read_bytes(), packed)

    def test_native_block_schema_defaults_and_legacy_adapter(self):
        catalog, _, errors = worker.load_catalog(ROOT/'generators', block_units=True)
        self.assertFalse(errors)
        schema = next(s for s in catalog if s['id'] == 'density_filament_curves')
        keys = {p['key']: p for p in schema['parameters']}
        self.assertNotIn('pop_block_scale', keys)
        self.assertEqual(keys['pop_density']['default'], .25)
        self.assertEqual(keys['seed_spacing']['default'], 16)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'points.bin'
            request = dict(generator='galaxy', count=100, seed=42, params={})
            before = worker.generate_request(request, ROOT/'generators', path)
            old = np.frombuffer(path.read_bytes()[16:], '<f4').reshape(-1, 7)
            after = worker.generate_request(dict(request, world_units='blocks', legacy_display_scale=8), ROOT/'generators', path)
            self.assertTrue(before['ok'] and after['ok'])
            new = np.frombuffer(path.read_bytes()[16:], '<f4').reshape(-1, 7)
            np.testing.assert_array_equal(new[:, :3], old[:, :3]*8)
            np.testing.assert_array_equal(new[:, 6], old[:, 6]*8)
            np.testing.assert_array_equal(new[:, 3:6], old[:, 3:6])

    def test_stable_extent_migration_preserves_old_geometry_and_freezes_noise_scale(self):
        _, modules, errors = worker.load_catalog(ROOT/'generators')
        self.assertFalse(errors)
        g = modules['density_filament_curves']
        old = dict(extent=8., y_extent=2., frequency=2.5, curve_resolution=32, strand_length=8.)
        migrated = g.migrate_parameters(old)
        self.assertEqual(migrated['noise_scale'], 3.2)
        self.assertEqual(g.migrate_parameters(dict(migrated, extent=12.))['noise_scale'], 3.2)
        self.assertEqual(g.migrate_parameters(dict(extent=12.))['noise_scale'], g._DEFAULT_NOISE_SCALE)
        before = g.generate_population_source(100, 42, **old)[0]
        after = g.generate_population_source(100, 42, **migrated)[0]
        for a, b in zip(before, after):
            np.testing.assert_array_equal(a, b)
        keys = {p['key'] for p in g.PARAMETERS}
        self.assertIn('noise_scale', keys)
        self.assertNotIn('frequency', keys)

    def test_stable_extent_samples_same_noise_at_shared_world_coordinates(self):
        from unittest.mock import patch
        _, modules, _ = worker.load_catalog(ROOT/'generators')
        g = modules['density_filament_curves']
        def fields(extent, resolution):
            with patch.object(g, 'extract_paths', wraps=g.extract_paths) as extraction:
                g.generate_population_source(100, 42, extent=extent, y_extent=2.,
                    noise_scale=3.2, curve_resolution=resolution, strand_length=8.)
                return extraction.call_args.args[0]
        small = fields(6., 25)
        large = fields(12., 49)
        # Equal XZ cell spacing and shared Y nodes. Added bounds sample new
        # noise outside the original box, rather than stretching that box.
        np.testing.assert_allclose(small, large[:, 12:37, ::2, 12:37], atol=1e-5, rtol=0)
        self.assertGreater(np.abs(small-large[:, ::2, ::2, ::2]).mean(), .05)

    def test_block_cell_integrals_scale_overlap_and_negative_coordinates(self):
        from _block_population import cell_masses, populate_blocks
        paths = [np.array([[-4., .25, .25], [4., .25, .25]])]
        params = dict(pop_block_scale=1, pop_block_proxies=0, pop_density=2., pop_spread=0.,
                      pop_taper=0., pop_curve_density_variation=0., pop_colors=1)
        cells, mass, colors, _ = cell_masses(paths, [[1., 0., 0.]], 42, params)
        np.testing.assert_array_equal(cells[:, 0], np.arange(-4, 4))
        np.testing.assert_array_equal(cells[:, 1:], 0)
        np.testing.assert_allclose(mass, 2.)
        fine, fine_mass, _, _ = cell_masses(paths, [[1., 0., 0.]], 42, dict(params, pop_block_scale=2))
        self.assertEqual(len(fine), 16)
        np.testing.assert_allclose(fine_mass, 1.)
        self.assertAlmostEqual(mass.sum(), fine_mass.sum())
        # Sources combine before occupancy, with mass-weighted diagnostic colors.
        both, both_mass, both_colors, _ = cell_masses(paths*2, [[1., 0., 0.], [0., 0., 1.]], 42, params)
        np.testing.assert_array_equal(both, cells)
        np.testing.assert_allclose(both_mass, 4.)
        np.testing.assert_allclose(both_colors, np.tile([.5, 0., .5], (8, 1)))
        dense, _ = populate_blocks(paths*2, [[1., 0., 0.], [0., 0., 1.]], 42, dict(params, pop_density=100.))
        self.assertEqual(len(dense[0]), 8)
        np.testing.assert_array_equal(dense[0], cells+.5)
        np.testing.assert_array_equal(dense[2], 1.)

    def test_block_sampling_distribution_taper_and_appearance_independence(self):
        from _block_population import cell_masses, populate_blocks, cell_uniform
        # Check cell-keyed selection against a known Bernoulli distribution.
        cells = np.column_stack((np.arange(-20000, 20000), np.zeros((40000, 2)))).astype(np.int64)
        probability = -np.expm1(-.2)
        self.assertAlmostEqual(float((cell_uniform(cells, 42) < probability).mean()), probability, delta=.008)
        np.testing.assert_array_equal(cell_uniform(cells[::3], 42), cell_uniform(cells, 42)[::3])
        path = [np.array([[0., 0., 0.], [8., 0., 0.]])]
        params = dict(pop_block_scale=8, pop_block_proxies=0, pop_density=10., pop_spread=.2, pop_taper=0.,
                      pop_curve_density_variation=0.)
        cells, mass, _, _ = cell_masses(path, [[1., 0., 0.]], 42, params)
        np.testing.assert_allclose(mass.sum(), 80.)
        centers = (cells+.5)/8
        # Quantization adds <= half a cell; the physical cross section stays .2.
        for axis in (1, 2):
            self.assertAlmostEqual(np.average(centers[:, axis], weights=mass), 0., delta=.01)
            self.assertAlmostEqual(np.average(centers[:, axis]**2, weights=mass), .2**2, delta=.006)
        _, tapered_mass, _, _ = cell_masses(path, [[1., 0., 0.]], 42, dict(params, pop_taper=1.))
        self.assertAlmostEqual(tapered_mass.sum(), 40., delta=.02)
        original, _ = populate_blocks(path, [[1., 0., 0.]], 42, params)
        changed, _ = populate_blocks(path, [[0., 1., 0.]], 42,
            dict(params, pop_colors=1, pop_jitter=0., pop_size=.4, pop_size_variation=0.))
        np.testing.assert_array_equal(original[0], changed[0])
        np.testing.assert_array_equal(original[2], changed[2])
        self.assertEqual(len(np.unique(original[0], axis=0)), len(original[0]))

    def test_block_worker_preserves_viewer_scale_fades_without_moving_and_bypasses_exactly(self):
        import struct
        catalog, _, errors = worker.load_catalog(ROOT/'generators')
        self.assertFalse(errors)
        for entry in catalog:
            self.assertEqual(any(p['key'] == 'pop_block_scale' for p in entry['parameters']),
                             entry['population'] and not entry.get('native_blocks', False))
        params = dict(curve_resolution=24, extent=6., y_extent=2., strand_length=5., pop_block_proxies=0,
                      pop_density=10., pop_taper=0., pop_spread=.2, fade_xz=0, fade_y=0)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'points.bin'
            def run(changes):
                response = worker.generate_request(dict(generator='density_filament_curves',
                    count=100, seed=42, params=dict(params, **changes)), ROOT/'generators', output)
                self.assertTrue(response['ok'], response.get('error'))
                star_data = output.with_suffix('.stars.bin').read_bytes()
                self.assertEqual(struct.unpack('<8sQ', star_data[:16]), (b'FSTAR002', response['star_count']))
                return output.read_bytes(), star_data, response
            lines, stars, _ = run({})
            off_lines, off_stars, _ = run(dict(pop_block_scale=0))
            self.assertEqual(lines, off_lines)
            self.assertEqual(stars, off_stars)
            block_lines, block_stars, _ = run(dict(pop_block_scale=8))
            self.assertEqual(lines, block_lines)
            def check_grid(data, scale=8):
                blocks = np.frombuffer(data, dtype='<f4', offset=16).reshape(-1, 7)
                np.testing.assert_allclose((blocks[:, :3]*scale) % 1, .5, atol=2e-5)
                np.testing.assert_allclose(blocks[:, 6], 1./scale)
                self.assertEqual(len(np.unique(blocks[:, :3], axis=0)), len(blocks))
                return blocks
            before = check_grid(block_stars)
            for scale in (16, 17):
                other_lines, other_stars, _ = run(dict(pop_block_scale=scale))
                self.assertEqual(lines, other_lines)
                other = check_grid(other_stars, scale)
                self.assertLess(np.abs(other[:, :3]).max(), 10.)
            for mode in (0, 1):
                _, warped, _ = run(dict(pop_block_scale=8, pp_warp=1, pp_flow_mode=mode))
                check_grid(warped)
            fade_lines, faded, _ = run(dict(pop_block_scale=8, fade_y=1, fade_y_width=1., fade_y_density_strength=0.))
            self.assertEqual(block_lines, fade_lines)
            after = check_grid(faded)
            self.assertLess(len(after), len(before))
            self.assertTrue({row.tobytes() for row in after} <= {row.tobytes() for row in before})
            _, empty, _ = run(dict(pop_block_scale=8, pop_density=0.))
            self.assertEqual(len(empty), 16)
            for key in ('pp_merge', 'pp_curves'):
                response = worker.generate_request(dict(generator='density_filament_curves', count=100,
                    params=dict(params, pop_block_scale=8, **{key: 1})), ROOT/'generators', output)
                self.assertFalse(response['ok'])
                self.assertIn('requires Merge dense stars', response['error'])

    def test_block_materials_follow_curves_and_shapes_do_not_resample(self):
        from _block_population import populate_blocks, curve_materials, cell_masses
        paths = [np.array([[0., .25, 2*i+.25], [20., .25, 2*i+.25]]) for i in range(100)]
        colors = np.ones((100, 3))
        params = dict(pop_block_scale=1, pop_block_proxies=1, pop_rod_fraction=.3,
                      pop_density=10., pop_spread=0., pop_taper=0., pop_curve_density_variation=0.)
        kinds, palette = curve_materials(len(paths), 42, params)
        self.assertEqual(set(kinds), {0, 1, 2})
        stars, stats = populate_blocks(paths, colors, 42, params)
        owner = (stars[0][:, 2] / 2).astype(int)
        np.testing.assert_array_equal(stars[1], palette[owner].astype(np.float32))
        np.testing.assert_array_equal(stats['_fade_groups'], owner)
        shapes = stats['_block_shapes']
        candles, rods, blocks = (shapes[kinds[owner] == kind] for kind in range(3))
        self.assertEqual(set(candles[:, 0]), {2/16, 4/16, 5/16, 6/16})
        np.testing.assert_array_equal(candles[:, 1], 6/16)
        self.assertEqual(set(np.argmax(rods, axis=1)), {0, 1, 2})
        np.testing.assert_array_equal(np.sort(rods, axis=1), np.tile([2/16, 2/16, 1.], (len(rods), 1)))
        np.testing.assert_array_equal(blocks, 1.)
        singles, single_stats = populate_blocks(paths, colors, 42, dict(params, pop_candle_max=1))
        for a, b in zip(stars, singles):
            np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(single_stats['_block_shapes'][kinds[owner] == 0, 0], 2/16)
        np.testing.assert_array_equal(single_stats['_block_shapes'][kinds[owner] != 0], shapes[kinds[owner] != 0])
        # Rod density changes integrated placement mass, not transverse spread.
        _, full, _, _ = cell_masses(paths[:1], colors[:1], 42, dict(params, pop_rod_fraction=1., pop_rod_density=1.))
        _, sparse, _, _ = cell_masses(paths[:1], colors[:1], 42, dict(params, pop_rod_fraction=1., pop_rod_density=.4))
        self.assertAlmostEqual(sparse.sum(), full.sum()*.4)
        # Coincident curves choose one source color, never their blended purple.
        crossing = [np.array([[0., .25, .25], [500., .25, .25]])]*2
        _, _, rgb, _ = cell_masses(crossing, [[1., 0., 0.], [0., 0., 1.]], 42,
            dict(params, pop_colors=1, pop_candle_weight=1., pop_rod_weight=0., pop_full_block_weight=0., pop_density=1.))
        self.assertTrue(set(map(tuple, rgb)) == {(1., 0., 0.), (0., 0., 1.)})
        self.assertAlmostEqual(rgb[:, 0].mean(), .5, delta=.08)

    def test_block_proxy_worker_transfer_and_fade_preserve_shapes(self):
        import struct
        params = dict(curve_resolution=24, strand_length=5., extent=6., y_extent=2.,
                      pop_block_scale=8, pop_block_proxies=1, pop_density=10.,
                      pop_spread=.2, fade_xz=0, fade_y=0, pop_lighting=0)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'points.bin'
            def run(changes):
                response = worker.generate_request(dict(generator='density_filament_curves', count=100,
                    seed=42, params=dict(params, **changes)), ROOT/'generators', output)
                self.assertTrue(response['ok'], response.get('error'))
                data = output.with_suffix('.stars.bin').read_bytes()
                self.assertEqual(struct.unpack('<8sQ', data[:16]), (b'FSTAR003', response['star_count']))
                return output.read_bytes(), np.frombuffer(data, dtype='<f4', offset=16).reshape(-1, 10)
            lines, original = run({})
            faded_lines, faded = run(dict(fade_y=1, fade_y_width=1., fade_y_density_strength=0.))
            self.assertEqual(lines, faded_lines)
            self.assertLess(len(faded), len(original))
            self.assertTrue({row.tobytes() for row in faded} <= {row.tobytes() for row in original})
            np.testing.assert_array_equal(original[:, 6], 1/8)
            np.testing.assert_array_equal((original[:, :3]*8) % 1, .5)
            self.assertTrue((original[:, 7:] != 1).any())
            _, empty = run(dict(pop_density=0.))
            self.assertEqual(empty.shape, (0, 10))

    def test_material_weights_and_sparse_full_block_curves(self):
        from _population import migrate_parameters
        from _block_population import curve_materials, cell_masses, populate_blocks
        weights = dict(pop_candle_weight=60., pop_rod_weight=30., pop_full_block_weight=10.)
        kinds, colors = curve_materials(5000, 42, weights)
        np.testing.assert_allclose(np.bincount(kinds)/len(kinds), [.6, .3, .1], atol=.02)
        scaled, scaled_colors = curve_materials(5000, 42, {key: value/10 for key, value in weights.items()})
        np.testing.assert_array_equal(scaled, kinds)
        np.testing.assert_array_equal(scaled_colors, colors)
        for key, value in ((0, 'pop_candle_weight'), (1, 'pop_rod_weight'), (2, 'pop_full_block_weight')):
            only = dict.fromkeys(weights, 0.)
            only[value] = 1.
            np.testing.assert_array_equal(curve_materials(100, 42, only)[0], key)
        with self.assertRaisesRegex(ValueError, 'At least one material'):
            curve_materials(1, 42, dict.fromkeys(weights, 0.))
        migrated = migrate_parameters(dict(pop_rod_fraction=.3))
        self.assertNotIn('pop_rod_fraction', migrated)
        np.testing.assert_allclose(list(migrated.values()), [67.9, 30., 2.1])
        # Preserve each previous material assignment, including its color draw.
        migrated_kinds, _ = curve_materials(100, 42, migrated)
        previous = []
        for i in range(100):
            r, b, _ = np.random.default_rng(np.random.SeedSequence([42, 93281, i])).random(3)
            previous.append(1 if r < .3 else (2 if b < .03 else 0))
        np.testing.assert_array_equal(migrated_kinds, previous)
        paths = [np.array([[0., .25, .25], [100., .25, .25]])]
        params = dict(pop_block_scale=1, pop_block_proxies=1, pop_density=2., pop_spread=0.,
                      pop_taper=0., pop_curve_density_variation=0., pop_candle_weight=0.,
                      pop_rod_weight=0., pop_full_block_weight=1.)
        _, mass, _, _ = cell_masses(paths, [[1, 1, 1]], 42, params)
        self.assertAlmostEqual(mass.sum(), 100*2*.05)
        sparse, stats = populate_blocks(paths, [[1, 1, 1]], 42, params)
        dense, _ = populate_blocks(paths, [[1, 1, 1]], 42, dict(params, pop_full_block_density=1.))
        self.assertGreater(len(sparse[0]), 0)
        self.assertLess(len(sparse[0]), len(dense[0])/4)
        np.testing.assert_array_equal(stats['_block_shapes'], 1.)
        empty, _ = populate_blocks(paths, [[1, 1, 1]], 42, dict(params, pop_full_block_density=0.))
        self.assertEqual(len(empty[0]), 0)
        with tempfile.TemporaryDirectory() as temp:
            response = worker.generate_request(dict(generator='density_filament_curves', count=100,
                seed=42, params=dict(curve_resolution=24, pop_block_scale=8, pop_rod_fraction=.3)),
                ROOT/'generators', Path(temp)/'points.bin')
            self.assertTrue(response['ok'], response.get('error'))
            self.assertNotIn('pop_rod_fraction', response['params'])
            for key, value in migrated.items():
                self.assertEqual(response['params'][key], value)

    def test_signed_y_fade_is_independent_and_migrates_symmetric_settings(self):
        from _axis_controls import migrate_signed_y
        from _postprocess import apply_to_stars
        old = dict(fade_y=1, fade_y_width=.6, fade_y_density_strength=2., fade_xz=0)
        migrated = migrate_signed_y(old)
        for side in ('pos', 'neg'):
            self.assertEqual(migrated['fade_y_'+side], 1)
            self.assertEqual(migrated['fade_y_'+side+'_width'], .6)
            self.assertEqual(migrated['fade_y_'+side+'_density_strength'], 2.)
        self.assertEqual(migrate_signed_y(dict(old, fade_y_neg=0))['fade_y_neg'], 0)
        y = np.linspace(-1.2, 1.2, 12001)
        positions = np.column_stack((np.zeros(len(y)), y, np.zeros(len(y))))
        colors = np.full_like(positions, .8)
        sizes = np.full(len(y), .04)
        def run(params):
            return apply_to_stars(positions, colors, sizes, 42, params,
                bounds=(np.zeros(3), np.ones(3)), allow_empty=True, axis_fade=True)[0]
        np.testing.assert_array_equal(run(old), run(migrated))
        plus = run(dict(fade_y_pos=1, fade_y_pos_width=1., fade_y_pos_density_strength=0., fade_y_neg=0))
        np.testing.assert_array_equal(plus[plus[:, 1] < 0], positions[y < 0])
        self.assertLess(len(plus[plus[:, 1] >= 0]), len(y[y >= 0])/2)
        minus = run(dict(fade_y_neg=1, fade_y_neg_width=1., fade_y_neg_density_strength=0., fade_y_pos=0))
        np.testing.assert_array_equal(minus[minus[:, 1] >= 0], positions[y >= 0])
        self.assertTrue((minus[minus[:, 1] < 0, 1] > -1).all())
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'points.bin'
            response = worker.generate_request(dict(generator='density_filament_curves', count=100,
                seed=42, params=dict(curve_resolution=24, **old)), ROOT/'generators', output)
            self.assertTrue(response['ok'], response.get('error'))
            self.assertNotIn('fade_y', response['params'])
            for side in ('pos', 'neg'):
                self.assertEqual(response['params']['fade_y_'+side+'_width'], .6)
            lines = output.read_bytes()
            response = worker.generate_request(dict(generator='density_filament_curves', count=100,
                seed=42, params=dict(response['params'], fade_y_pos=0, fade_y_neg_width=1.)), ROOT/'generators', output)
            self.assertTrue(response['ok'], response.get('error'))
            self.assertEqual(output.read_bytes(), lines)

    def test_y_fade_crosses_zero_and_zero_width_preserves_disabled_side(self):
        from _postprocess import apply_to_stars, edge_envelope
        from _axis_controls import migrate_signed_y
        y = np.linspace(-1.2, 1.2, 12001)
        positions = np.column_stack((np.zeros(len(y)), y, np.zeros(len(y))))
        colors, sizes = np.ones_like(positions), np.ones(len(y))
        def run(params):
            return apply_to_stars(positions, colors, sizes, 42, params,
                bounds=(np.zeros(3), np.ones(3)), allow_empty=True, axis_fade=True)[0]
        for side in ('pos', 'neg'):
            old = {f'fade_y_{side}': 1, f'fade_y_{side}_width': .6}
            new = migrate_signed_y(old)
            self.assertEqual(new['fade_y_enabled'], 1)
            other = 'neg' if side == 'pos' else 'pos'
            self.assertEqual(new[f'fade_y_{other}_width'], 0.)
            np.testing.assert_array_equal(run(old), run(new))
        base = dict(fade_y_enabled=1, fade_y_pos_width=0., fade_y_neg_width=0.,
                    fade_y_pos_density_strength=0., fade_y_neg_density_strength=0.)
        np.testing.assert_array_equal(run(base), positions)
        draws = np.random.default_rng(np.random.SeedSequence([42, 9401])).random(len(y))
        for side, sign in (('pos', 1), ('neg', -1)):
            result = run(dict(base, **{f'fade_y_{side}_width': 1.5}))
            expected = positions[draws < edge_envelope(sign*y, 1.5)]
            np.testing.assert_array_equal(result, expected)
            self.assertLess(np.count_nonzero(result[:, 1]*sign < 0), np.count_nonzero(y*sign < 0))
        np.testing.assert_array_equal(run(dict(base, fade_y_enabled=0, fade_y_pos_width=2.)), positions)

    def test_material_curve_fade_has_coherent_different_reaches(self):
        from _postprocess import apply_to_stars
        x = np.linspace(0., 1., 101)
        groups = np.repeat(np.arange(12), len(x))
        positions = np.column_stack((np.tile(x, 12), np.repeat(np.linspace(-.5, .5, 12), len(x)), np.zeros(len(groups))))
        colors = np.column_stack((groups/12., np.zeros((len(groups), 2))))
        sizes = np.full(len(groups), .04)
        def run(width, owners):
            return apply_to_stars(positions, colors, sizes, 42,
                dict(fade_xz=1, fade_xz_width=width, fade_xz_density_strength=0.),
                bounds=(np.zeros(3), np.ones(3)), allow_empty=True, axis_fade=True, fade_groups=owners)
        kept = run(1., groups)
        reaches = []
        for group in range(12):
            points = kept[0][kept[1][:, 0] == group/12.]
            self.assertGreater(len(points), 0)
            # Each outward path has one cutoff, never scattered interior holes.
            np.testing.assert_array_equal(points[:, 0], x[:len(points)])
            reaches.append(points[-1, 0])
        self.assertGreater(np.ptp(reaches), .4)
        weaker = run(.5, groups)
        self.assertTrue({row.tobytes() for row in kept[0]} <= {row.tobytes() for row in weaker[0]})
        independent = run(1., None)
        ungrouped = run(1., np.full(len(groups), -1))
        for a, b in zip(independent, ungrouped):
            np.testing.assert_array_equal(a, b)
        mixed = np.where(groups < 6, groups, -1)
        mixed_result = run(1., mixed)
        np.testing.assert_array_equal(mixed_result[0][mixed_result[1][:, 0] >= .5],
                                      independent[0][independent[1][:, 0] >= .5])

    def test_axis_star_fade_is_smooth_independent_and_preserves_survivors(self):
        worker.load_catalog(ROOT/'generators')
        from _postprocess import apply_to_stars, edge_envelope
        y = np.linspace(-1., 1., 40001)
        # X is deliberately outside its bound: Y-only fading must ignore it.
        positions = np.column_stack((np.full(len(y), 5.), y, np.zeros(len(y))))
        colors = np.broadcast_to([.3, .5, .7], positions.shape).copy()
        sizes = np.linspace(.01, .1, len(y))
        def run(width):
            return apply_to_stars(positions, colors, sizes, 42,
                dict(fade_y=1, fade_y_width=width, fade_y_density_strength=0., fade_xz=0),
                bounds=(np.zeros(3), np.ones(3)), axis_fade=True, allow_empty=True)
        weak, strong = run(.4), run(1.)
        self.assertTrue(set(strong[0][:, 1]).issubset(set(weak[0][:, 1])))
        self.assertLess(np.abs(strong[0][:, 1]).max(), 1.)
        ids = np.searchsorted(y, strong[0][:, 1])
        for actual, original in zip(strong, (positions, colors, sizes)):
            np.testing.assert_array_equal(actual, original[ids])
        # Verify survival throughout the whole Y taper, including the final band.
        for lo in np.arange(0., 1., .1):
            band = (np.abs(y) >= lo) & (np.abs(y) < lo+.1)
            kept = ((np.abs(strong[0][:, 1]) >= lo) & (np.abs(strong[0][:, 1]) < lo+.1)).sum()
            expected = edge_envelope(np.abs(y[band]), 1.).mean()
            self.assertAlmostEqual(kept/band.sum(), expected, delta=.025)
        # Swap X and Y, preserving the stream: the other axis must behave identically.
        swapped = positions[:, [1, 0, 2]]
        horizontal = apply_to_stars(swapped, colors, sizes, 42,
            dict(fade_xz=1, fade_xz_width=1., fade_xz_density_strength=0., fade_y=0),
            bounds=(np.zeros(3), np.ones(3)), axis_fade=True, allow_empty=True)
        np.testing.assert_array_equal(horizontal[0], strong[0][:, [1, 0, 2]])

    def test_stable_curve_worker_fades_only_stars_after_merging(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'points.bin'
            params = dict(curve_resolution=32, extent=6., y_extent=2., strand_length=30.,
                seed_xz=1., seed_y=1., broad_strength=0., clumping=0., pop_density=10.,
                pop_taper=0., pop_spread=.2, fade_xz=0, fade_y_density_strength=2.)
            def run(width, merge):
                request = dict(generator='density_filament_curves', count=100, seed=42,
                    params=dict(params, fade_y=int(width>0), fade_y_width=width or .8, pp_merge=merge))
                response = worker.generate_request(request, ROOT/'generators', output)
                self.assertTrue(response['ok'], response)
                stars = np.fromfile(output.with_suffix('.stars.bin'), dtype='<f4', offset=16).reshape(-1, 7)
                return output.read_bytes(), stars
            for merge in (0, 1):
                lines, original = run(0., merge)
                weak_lines, weak = run(.4, merge)
                strong_lines, strong = run(1., merge)
                self.assertEqual(lines, weak_lines)
                self.assertEqual(lines, strong_lines)
                self.assertLess(len(strong), len(weak))
                as_set = lambda data: {row.tobytes() for row in data}
                self.assertTrue(as_set(strong).issubset(as_set(weak)))
                self.assertTrue(as_set(weak).issubset(as_set(original)))
                self.assertTrue((np.abs(strong[:, 1]) < 2.).all())
                self.assertLess((np.abs(strong[:, 1]) > 1.6).sum(), (np.abs(original[:, 1]) > 1.6).sum())

    def test_stable_curve_fade_shortens_outer_intervals_without_moving_interior(self):
        worker.load_catalog(ROOT/'generators')
        from _stable_density_curves import seeded_paths
        from _axis_controls import fade_density_axes
        half = np.array([10., 10., 10.])
        path = np.column_stack((np.linspace(-10., 10., 201), np.zeros((201, 2))))
        density = np.ones((65,)*3)
        def run(width, seed_region=1.):
            faded = fade_density_axes(density, 10., 1, width, 0., 0, .8, 0.)
            return seeded_paths([path], faded, half, 42, spacing=.2, length=2.,
                                seed_xz=seed_region, seed_y=1., reference_scale=1., return_intervals=True)
        original, _, intervals = run(.4)
        faded, _, reduced = run(.8)
        nearby, _, nearby_intervals = run(.801)
        length = lambda records: sum(b-a for _, a, b in records)
        self.assertLess(length(reduced), length(intervals))
        self.assertLess(abs(length(nearby_intervals)-length(reduced)), .1)
        # Every retained interval is a subset of the weaker-fade geometry.
        for owner, a, b in reduced:
            self.assertTrue(any(o == owner and lo <= a+1e-10 and hi >= b-1e-10 for o, lo, hi in intervals))
        interior = lambda paths: np.concatenate([p[np.abs(p[:, 0]) < 2.] for p in paths])
        np.testing.assert_array_equal(interior(original), interior(faded))
        central, _, central_intervals = run(.4, .65)
        self.assertLess(length(central_intervals), length(intervals))
        self.assertLess(np.abs(np.concatenate(central)[:, 0]).max(), 8.)
        # Seed-region bounds admit/exclude roots without shortening their travel.
        center, _ = seeded_paths([path], density, half, 42, spacing=100., length=2., seed_y=.65)
        offset = np.array([0., 6.4, 0.])
        edge, _ = seeded_paths([path+offset], density, half, 42, spacing=100., length=2., seed_y=.65)
        np.testing.assert_allclose(edge[0]-offset, center[0], atol=1e-12)
        outside, _ = seeded_paths([path+[0., 6.6, 0.]], density, half, 42, spacing=100., length=2., seed_y=.65)
        self.assertEqual(outside, [])
        # With all population controls fixed, losing curve length loses stars.
        from _population import populate_curves
        params = dict(pop_density=100., pop_taper=0., pop_curve_density_variation=0., pop_spread=0.)
        stars, _ = populate_curves(original, np.ones((len(original), 3)), 42, params)
        faded_stars, _ = populate_curves(faded, np.ones((len(faded), 3)), 42, params)
        self.assertLess(len(faded_stars[0]), len(stars[0]))
        self.assertLess(np.count_nonzero(np.abs(faded_stars[0][:, 0]) > 7.),
                        np.count_nonzero(np.abs(stars[0][:, 0]) > 7.))

    def test_stable_curve_density_edits_preserve_source_geometry_and_colors(self):
        from unittest.mock import patch
        _, modules, errors = worker.load_catalog(ROOT/'generators')
        self.assertFalse(errors)
        g = modules['density_filament_curves']
        snapshots = []
        for overrides in ({}, dict(clumping=3., broad_strength=2., density_mid=.8),
                          dict(fade_xz=1, fade_xz_width=.8, fade_y=1)):
            with patch.object(g, 'seeded_paths', wraps=g.seeded_paths) as tracer:
                attrs, paths, colors = g.generate_population_source(100, 42,
                    curve_resolution=32, strand_length=8., **overrides)
                snapshots.append(tracer.call_args.args[0])
                self.assertTrue(np.isfinite(attrs[0]).all())
        for paths in snapshots[1:]:
            self.assertEqual(len(paths), len(snapshots[0]))
            for a, b in zip(snapshots[0], paths):
                np.testing.assert_array_equal(a, b)
        a = g.generate_population_source(100, 42, curve_resolution=32, strand_length=8.)
        b = g.generate_population_source(1000, 42, curve_resolution=32, strand_length=8.)
        for x, y in zip(a[0], b[0]):
            np.testing.assert_array_equal(x, y)
        # Retired steering controls are absent, rather than silently inert sliders.
        keys = {p['key'] for p in g.PARAMETERS}
        self.assertFalse(keys & {'strand_count', 'density_pull', 'join_strength', 'coverage_mode'})

    def test_stable_curve_intervals_merge_duplicates_and_wrap_loops(self):
        worker.load_catalog(ROOT/'generators')
        from _stable_density_curves import seeded_paths
        theta = np.linspace(0., 2*np.pi, 65)
        loop = np.column_stack((np.cos(theta), np.sin(theta), np.zeros_like(theta)))
        density = np.ones((8,)*3)
        paths, owners, intervals = seeded_paths([loop], density, [10., 10., 10.], 42,
            spacing=.2, length=20., reference_scale=1., return_intervals=True)
        self.assertEqual(len(paths), 1)
        self.assertEqual(len(intervals), 1)
        np.testing.assert_allclose(paths[0], loop, atol=1e-12)
        np.testing.assert_array_equal(owners, [0])

    def test_parallel_contacts_ignore_capacity_and_keep_one_continuation(self):
        worker.load_catalog(ROOT/'generators')
        from _density_curves import StrandContacts
        line = np.array([[-1., 0., 0.], [1., 0., 0.]])
        # Two halves per source; source 0 is the continuing strand.
        paths = [line, line[:1], line+[0., 0., .02], line[:1]]
        contacts = StrandContacts(paths, families=np.array([0, 0]))
        points = np.array([[0., 0., 0.], [0., 0., .02]])
        headings = np.array([[1., 0., 0.], [-1., 0., 0.]])
        target, _, distance = contacts.query(points, headings, np.array([0, 1]), .08,
            aligned=False, contact_families=np.array([0, 0]), allow_crossings=False)
        self.assertTrue(np.isinf(distance[0]))
        self.assertAlmostEqual(distance[1], .02)
        np.testing.assert_array_equal(target[1], [0., 0., 0.])
        # Other families and transverse crossings retain their coverage gate.
        for family, heading in ((1, [1., 0., 0.]), (0, [0., 0., 1.])):
            args = dict(aligned=False, contact_families=np.array([family]))
            self.assertTrue(np.isinf(contacts.query(points[1:], np.array([heading]), np.array([2]),
                .08, allow_crossings=False, **args)[2]).all())
            self.assertTrue(np.isfinite(contacts.query(points[1:], np.array([heading]), np.array([2]),
                .08, allow_crossings=True, **args)[2]).all())
        # Separation outside the physical radius never triggers consolidation.
        self.assertTrue(np.isinf(contacts.query(np.array([[0., 0., .5]]), headings[1:],
            np.array([2]), .08, aligned=False, contact_families=np.array([0]), allow_crossings=False)[2]).all())

    def test_pair_growth_stops_parallel_duplicate_even_when_capacity_is_underfilled(self):
        from unittest.mock import patch
        worker.load_catalog(ROOT/'generators')
        import _density_curves as growth
        x, y, z = np.meshgrid(*[np.linspace(-2, 2, 25)]*3, indexing='ij')
        fields = np.array([y, z, np.ones_like(x)*5])
        density = np.exp(-(y*y+z*z)/.02)
        roots = np.array([[0., 0., 0.], [0., 0., .02]])
        args = dict(strand_count=2, strand_length=2., direction_scale=.15, density_pull=0.,
                    curve_wander=0., pair_fields=fields, pair_width=.1, coverage_mode=1,
                    join_radius=.08, capacity_scale=1e6)
        with patch.object(growth, 'sample_density', return_value=(roots/2, np.zeros(2,dtype=int))):
            independent = growth.trace_density(density, 42, [2., 2., 2.], **dict(args, join_strength=0.))
            joined = growth.trace_density(density, 42, [2., 2., 2.], **args)
        np.testing.assert_array_equal(joined[0], independent[0])
        length = lambda p: np.linalg.norm(np.diff(p,axis=0),axis=1).sum()
        self.assertLess(length(joined[1]), .25*length(independent[1]))
        np.testing.assert_allclose(joined[1][[0,-1],2], 0., atol=1e-12)

    def test_pair_guidance_keeps_perpendicular_families_at_crossings(self):
        worker.load_catalog(ROOT/'generators')
        from _density_curves import PairFilamentShape, trace_density
        from noise_filaments_branches import _strand_log_density
        half = np.array([2., 1., 2.])
        x, y, z = np.meshgrid(*[np.linspace(-h, h, 33) for h in half], indexing='ij')
        fields = np.array([y, z, x])  # AB follows X; AC follows Z; BC follows Y.
        shape = PairFilamentShape(fields, half, .15, .12)
        points = np.zeros((3, 3))
        tangent, gradient, confidence = shape.sample(points, np.arange(3), np.ones((3, 3)))
        np.testing.assert_allclose(tangent, np.eye(3)[[0, 2, 1]], atol=1e-12)
        np.testing.assert_allclose(gradient, 0., atol=1e-12)
        density = np.exp(_strand_log_density(*fields, .12))
        args = dict(strand_count=64, strand_length=1., direction_scale=.15,
                    density_pull=0., curve_wander=0., join_strength=0.,
                    pair_fields=fields, pair_width=.12, return_families=True)
        paths, families = trace_density(density, 42, half, **args)
        self.assertEqual(set(families), {0, 1, 2})
        again, same_families = trace_density(density, 42, half, **args)
        np.testing.assert_array_equal(families, same_families)
        for p, q, family in zip(paths, again, families):
            np.testing.assert_array_equal(p, q)
            axis = [0, 2, 1][family]
            transverse = [i for i in range(3) if i != axis]
            np.testing.assert_allclose(np.diff(p[:, transverse], axis=0), 0., atol=1e-12)
            self.assertGreater(np.ptp(p[:, axis]), .1)

    def test_pair_join_steering_excludes_other_families_but_contact_allows_crossings(self):
        worker.load_catalog(ROOT/'generators')
        from _density_curves import StrandContacts
        line = np.array([[-1., 0., 0.], [1., 0., 0.]])
        index = StrandContacts([line], families=np.array([0]))
        p = np.array([[0., 0., .02]])
        h = np.array([[1., 0., 0.]])
        owner = np.array([1])
        self.assertTrue(np.isinf(index.query(p, h, owner, .1, families=np.array([1]))[2]).all())
        self.assertTrue(np.isfinite(index.query(p, h, owner, .1, families=np.array([0]))[2]).all())
        perpendicular = np.array([[0., 0., -1.]])
        self.assertTrue(np.isinf(index.query(p, perpendicular, owner, .1)[2]).all())
        target, _, distance = index.query(p, perpendicular, owner, .1, aligned=False)
        np.testing.assert_allclose(target, 0.)
        np.testing.assert_allclose(distance, .02)

    def test_broad_density_reweights_fine_field_without_changing_its_noise(self):
        from unittest.mock import patch
        _, modules, errors = worker.load_catalog(ROOT/'generators')
        self.assertFalse(errors)
        module = modules['noise_filaments_branches']
        params = dict(frequency=2.5, width=.2, clumping=0., strand_continuity=1., y_scale=.2)
        with patch.object(__import__('_density_field'), 'fractal_noise', wraps=__import__('_density_field').fractal_noise) as noise:
            original = module.build_density(42, **params, broad_strength=0.)
            self.assertEqual(noise.call_count, 4)
        np.testing.assert_array_equal(original,
            module.build_density(42, **params, broad_strength=0., broad_scale=8.))
        with patch.object(__import__('_density_field'), 'fractal_noise', wraps=__import__('_density_field').fractal_noise) as noise:
            broad = module.build_density(42, **params, broad_strength=4., broad_scale=2.)
            self.assertEqual(noise.call_count, 5)
            self.assertEqual(noise.call_args.args[2:4], (1.25, 1))
        multiplier = broad/original
        self.assertGreater(float(multiplier.max()/multiplier.min()), 2.)
        self.assertTrue(np.isfinite(broad).all())
        # Fine thickness/detail/remapping changes must not regenerate or alter
        # the independent broad envelope.
        changed = dict(params, width=.25, octaves=3, roughness=.3, density_high=.4)
        plain = module.build_density(42, **changed, broad_strength=0.)
        weighted = module.build_density(42, **changed, broad_strength=4., broad_scale=2.)
        np.testing.assert_allclose(weighted/plain, multiplier, rtol=2e-6)
        a = module.generate(1000, 42, **params, broad_strength=0.)
        b = module.generate(1000, 42, **params, broad_strength=4.)
        self.assertEqual(len(b[0]), len(a[0]))
        self.assertFalse(np.array_equal(a[0], b[0]))
        np.testing.assert_array_equal(a[2], b[2])
        for x, y in zip(b, module.generate(1000, 42, **params, broad_strength=4.)):
            np.testing.assert_array_equal(x, y)

    def test_density_strands_share_branch_field_bounds_and_fade(self):
        from unittest.mock import patch
        _, modules, errors = worker.load_catalog(ROOT/'generators')
        self.assertFalse(errors)
        curves, branches = modules['density_filament_growth'], modules['noise_filaments_branches']
        from _axis_controls import fade_density_axes
        params = dict(extent=8., y_extent=1.5, frequency=2.3, width=.07,
                      octaves=2, roughness=.2, clumping=4., strand_continuity=.6,
                      density_low=.7, density_mid=1.1, density_high=.3,
                      broad_strength=6., broad_scale=3.)
        _, expected, half = branches.generate_density_source(1, 123, **params)
        for fade in (dict(fade_xz=0, fade_y=0), dict(fade_xz=1, fade_y=0),
                     dict(fade_xz=0, fade_y=1)):
            fade.update(fade_xz_width=.5, fade_y_width=.2,
                        fade_xz_density_strength=2., fade_y_density_strength=3.)
            with patch.object(curves, 'trace_density', return_value=[np.zeros((3, 3))]) as trace:
                curves.generate_population_source(100, 123, **params, **fade,
                                                   layer_continuity=1., connectivity=0.)
            np.testing.assert_array_equal(trace.call_args.args[0],
                fade_density_axes(expected, half[1], **fade))
            np.testing.assert_array_equal(trace.call_args.args[2], half)
        old = curves.migrate_parameters(dict(extent=8., y_scale=.2, fade=1, fade_width=.6))
        self.assertEqual(old['y_extent'], 1.6)
        self.assertEqual(old['fade_xz_width'], .6)
        self.assertEqual(old['fade_y'], 1)
        self.assertEqual(curves.migrate_parameters({})['y_extent'], 9.458*.234)
        self.assertEqual(curves.migrate_parameters(dict(extent=8., y_scale=.2, y_extent=3.))['y_extent'], 3.)
        with tempfile.TemporaryDirectory() as temp:
            response = worker.generate_request(dict(generator='density_filament_growth', count=100,
                seed=42, params=dict(strand_count=16, strand_length=.5, extent=8., y_extent=0.,
                                     fade_xz=1, fade_y=1, layer_continuity=1., y_scale=.8)),
                ROOT/'generators', Path(temp)/'points.bin')
            self.assertTrue(response['ok'], response)
            for key in ('layer_continuity', 'connectivity', 'y_scale', 'fade'):
                self.assertNotIn(key, response['params'])
            points = np.fromfile(Path(temp)/'points.bin', dtype='<f4', offset=16).reshape(-1, 7)
            np.testing.assert_array_equal(points[:, 1], 0.)
            self.assertTrue((np.abs(points[:, [0, 2]]) <= 8.).all())

    def test_density_contacts_local_bound_keeps_long_segment_endpoints(self):
        worker.load_catalog(ROOT/'generators')
        from _density_curves import StrandContacts
        # The midpoint lies well outside the query radius, but the endpoint is close.
        line = np.array([[0., 0., 0.], [10., 0., 0.]])
        index = StrandContacts([line])
        points = np.array([[0., .1, 0.], [100., 0., 0.]])
        headings = np.array([[1., 0., 0.]]*2)
        target, tangent, distance = index.query(points, headings, np.array([1, 1]), .2)
        self.assertAlmostEqual(distance[0], .1)
        np.testing.assert_array_equal(target[0], line[0])
        self.assertTrue(np.isinf(distance[1]))
        np.testing.assert_array_equal(target[1], points[1])
        self.assertEqual(len(index.query(points[:0], headings[:0], np.array([], dtype=int), .2)[0]), 0)

    def test_curve_coverage_load_only_matches_full_steering(self):
        worker.load_catalog(ROOT/'generators')
        from _curve_coverage import CurveCoverage
        density = np.ones((16, 16, 16))
        for half in ([2., 0., 2.], [2., 1., 2.]):
            full = CurveCoverage(density, half, .2, 40.)
            load_only = CurveCoverage(density, half, .2, 40., steering=False)
            start, end = np.array([[0., 0., 0.]]), np.array([[1., 0., .1]])
            for field in (full, load_only):
                field.deposit(start, end)
                field.refresh()
            self.assertFalse(hasattr(load_only, 'deficit_gradient'))
            np.testing.assert_array_equal(load_only.sample(start)[0], full.sample(start)[0])
            np.testing.assert_array_equal(full.sample(start, steering=False)[0], full.sample(start)[0])
            np.testing.assert_array_equal(load_only.sample(start)[1], 0.)

    def test_axis_fades_are_independent_and_match_legacy_when_equal(self):
        from _axis_controls import fade_density_axes
        from _postprocess import fade_density
        density = np.ones((25, 25, 25))
        horizontal = fade_density_axes(density, 2., 1, .6, 1., 0, .2, 4.)
        vertical = fade_density_axes(density, 2., 0, .2, 4., 1, .6, 1.)
        np.testing.assert_array_equal(horizontal[:, 0, :], horizontal[:, 12, :])
        np.testing.assert_array_equal(vertical[0, :, 0], vertical[12, :, 12])
        self.assertGreater(horizontal[12, 0, 12], 0)
        self.assertGreater(vertical[0, 12, 0], 0)
        self.assertIs(fade_density_axes(density, 0., 0, .6, 1., 1, .6, 1.), density)
        rng = np.random.default_rng(12)
        uneven = rng.random(density.shape)
        np.testing.assert_allclose(fade_density_axes(uneven, 2., 1, .6, 2., 1, .6, 2.),
                                   fade_density(uneven, .6, 2.), rtol=1e-7, atol=1e-12)

    def test_axis_extent_migration_and_worker_preserve_scene(self):
        from _axis_controls import migrate_parameters
        old = dict(extent=10., y_scale=.2, fade=1, fade_width=.4, fade_density_strength=2.)
        migrated = migrate_parameters(old)
        self.assertEqual(migrated['y_extent'], 2.)
        self.assertEqual(migrated['fade_y_width'], .4)
        self.assertEqual(migrate_parameters(dict(old, y_extent=3., fade_y=0))['y_extent'], 3.)
        self.assertEqual(migrate_parameters(dict(old, y_extent=3., fade_y=0))['fade_y'], 0)
        catalog, modules, errors = worker.load_catalog(ROOT/'generators')
        self.assertFalse(errors)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'stars.bin'
            for name in ('noise_filaments', 'noise_filaments_branches'):
                schema = next(c for c in catalog if c['id'] == name)
                keys = {p['key'] for p in schema['parameters']}
                self.assertTrue({'y_extent', 'fade_xz', 'fade_y'} <= keys)
                self.assertTrue(keys.isdisjoint({'y_scale', 'fade', 'fade_width', 'fade_density_strength'}))
                for axis in ('xz', 'y'):
                    control = next(p for p in schema['parameters'] if p['key'] == f'fade_{axis}_width')
                    self.assertEqual(control['enabled_if'], f'fade_{axis}')
                legacy = modules[name].generate(1000, 42, **old)
                response = worker.generate_request(dict(generator=name, count=1000, seed=42, params=old),
                                                    ROOT/'generators', output)
                self.assertTrue(response['ok'], response)
                actual = np.frombuffer(output.read_bytes(), dtype='<f4', offset=16).reshape(-1, 7)
                np.testing.assert_allclose(actual, np.column_stack(legacy), rtol=1e-6, atol=1e-6)
                self.assertEqual(response['params']['y_extent'], 2.)
                self.assertNotIn('y_scale', response['params'])
                for horizontal_extent in (3., 12.):
                    generated, _, half = modules[name].generate_density_source(1000, 42,
                        extent=horizontal_extent, y_extent=2.)
                    np.testing.assert_array_equal(half, [horizontal_extent, 2., horizontal_extent])
                    self.assertLessEqual(np.abs(generated[0][:, 1]).max(), 2.)
                # Restored settings run through the new density-alignment path too.
                request = dict(generator=name, count=1000, seed=42,
                               params=dict(response['params'], fade_y=0, pp_curves=1))
                self.assertTrue(worker.generate_request(request, ROOT/'generators', output)['ok'])

    def test_density_alignment_concentrates_faint_tube_without_axial_drift(self):
        from _density_alignment import align_to_density
        u = np.linspace(-2., 2., 49)
        x, y, z = np.meshgrid(u, u, u, indexing='ij')
        density = np.exp(-(y*y+z*z)/(.3**2)) * np.exp(x)
        source = (density, [2., 2., 2.])
        points = np.array([[-1., .25, .2], [-.8, -.2, .15], [-.5, .3, -.1]], dtype=np.float32)
        moved = align_to_density(points, source, np.ones(3), 0., .7, .12, 1.)
        self.assertLess(np.linalg.norm(moved[:, 1:], axis=1).max(), .01)
        np.testing.assert_allclose(moved[:, 0], points[:, 0], atol=.002)
        # Even one star gets a field-defined direction: no population PCA.
        single = align_to_density(points[:1], source, np.ones(1), 0., .7, .12, 1.)
        np.testing.assert_array_equal(single, moved[:1])
        limited = align_to_density(points, source, np.ones(3), 0., .05, .12, 1.)
        self.assertLessEqual(np.linalg.norm(limited-points, axis=1).max(), .050001)
        self.assertIs(align_to_density(points, source, np.ones(3), 0., .7, .12, 0.), points)

    def test_density_alignment_follows_curved_flat_ridge_and_leaves_uniform_field(self):
        from _density_alignment import align_to_density
        u = np.linspace(-2., 2., 65)
        x, z = np.meshgrid(u, u, indexing='ij')
        ring = np.exp(-((np.hypot(x, z)-1.)/.13)**2)
        density = np.repeat(ring[:, None, :], 3, axis=1)
        angles = np.linspace(0, 2*np.pi, 13, endpoint=False)
        points = np.column_stack((1.2*np.cos(angles), np.zeros(13), 1.2*np.sin(angles))).astype(np.float32)
        moved = align_to_density(points, (density, [2., 0., 2.]), np.ones(13), 0., .4, .08, 1.)
        np.testing.assert_allclose(np.linalg.norm(moved[:, [0, 2]], axis=1), 1., atol=.025)
        np.testing.assert_array_equal(moved[:, 1], points[:, 1])
        np.testing.assert_allclose(np.arctan2(moved[:, 2], moved[:, 0]), angles - (angles > np.pi)*2*np.pi, atol=.015)
        uniform = align_to_density(points, (np.ones_like(density), [2., 0., 2.]), np.ones(13), 0., .4, .08, 1.)
        np.testing.assert_array_equal(uniform, points)

    def test_density_alignment_worker_preserves_merge_count_attributes_and_centers(self):
        catalog, modules, errors = worker.load_catalog(ROOT / 'generators')
        self.assertFalse(errors)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'stars.bin'
            for name in ('noise_filaments', 'noise_filaments_branches'):
                keys = {p['key'] for item in catalog if item['id'] == name for p in item['parameters']}
                self.assertIn('pp_density_radius', keys)
                self.assertNotIn('pp_curve_length', keys)
                self.assertNotIn('pp_curve_colors', keys)
                native = dict(y_scale=.2, density_high=.25)
                params = dict(native, pp_merge=1, pp_merge_distance=.6, pp_dense_fraction=.5,
                              pp_sparse_fraction=1., pp_curve_strength=1., pp_curve_reach=.6)
                def run(enabled):
                    response = worker.generate_request(dict(generator=name, count=2000, seed=42,
                        params=dict(params, pp_curves=enabled)), ROOT/'generators', output)
                    self.assertTrue(response['ok'], response)
                    return np.frombuffer(output.read_bytes(), dtype='<f4', offset=16).reshape(-1, 7).copy()
                base, aligned = run(0), run(1)
                self.assertEqual(base.shape, aligned.shape)
                np.testing.assert_array_equal(base[:, 3:], aligned[:, 3:])
                displacement = np.linalg.norm(aligned[:, :3]-base[:, :3], axis=1)
                self.assertGreater(np.count_nonzero(displacement > .001), 100)
                self.assertLessEqual(displacement.max(), .60001)
                # Merged stars are larger than any original at this size boost.
                merged = base[:, 6] > .04*1.4
                self.assertTrue(merged.any())
                np.testing.assert_array_equal(aligned[merged], base[merged])
                np.testing.assert_array_equal(run(1), aligned)
                direct = modules[name].generate(2000, 42, **native)
                shared, density, half = modules[name].generate_density_source(2000, 42, **native)
                for a, b in zip(direct, shared):
                    np.testing.assert_array_equal(a, b)

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

    def test_population_separate_xz_y_spread(self):
        from _population import populate_curves, transverse_scatter, migrate_parameters
        from _block_population import cell_masses
        paths = [np.array([[0., 0., 0.], [10., 0., 0.]])]
        colors = [[1., 1., 1.]]
        params = dict(pop_density=1000., pop_taper=0., pop_jitter=0., pop_curve_density_variation=0.)
        old, _ = populate_curves(paths, colors, 42, dict(params, pop_spread=.12))
        equal, _ = populate_curves(paths, colors, 42, dict(params, pop_spread_xz=.12, pop_spread_y=.12))
        for a, b in zip(old, equal):
            np.testing.assert_array_equal(a, b)
        split, _ = populate_curves(paths, colors, 42, dict(params, pop_spread_xz=.2, pop_spread_y=.05))
        np.testing.assert_array_equal(split[0][:, 0], old[0][:, 0])
        np.testing.assert_array_equal(split[1], old[1])
        np.testing.assert_array_equal(split[2], old[2])
        self.assertAlmostEqual(split[0][:, 1].std(), .05, delta=.002)
        self.assertAlmostEqual(split[0][:, 2].std(), .2, delta=.005)
        # Sloping and vertical curves remain transverse; zero Y adds no height.
        rng = np.random.default_rng(42)
        tangent = rng.normal(size=(1000, 3))
        tangent /= np.linalg.norm(tangent, axis=1)[:, None]
        tangent[:2] = [[0, 1, 0], [1, 0, 0]]
        scatter = rng.normal(size=tangent.shape)
        scatter -= (scatter*tangent).sum(axis=1)[:, None]*tangent
        for xz, y in ((.2, .05), (.2, 0.), (0., .2)):
            offsets = transverse_scatter(scatter, tangent, dict(pop_spread_xz=xz, pop_spread_y=y))
            self.assertTrue(np.isfinite(offsets).all())
            np.testing.assert_allclose((offsets*tangent).sum(axis=1), 0., atol=1e-14)
            if y == 0:
                np.testing.assert_allclose(offsets[:, 1], 0., atol=1e-14)
            if xz == 0:
                np.testing.assert_allclose(offsets[:, [0, 2]], 0., atol=1e-14)
        block = dict(params, pop_block_scale=32, pop_block_proxies=0, pop_density=10.)
        before = cell_masses(paths, colors, 42, dict(block, pop_spread=.12))
        after = cell_masses(paths, colors, 42, dict(block, pop_spread_xz=.12, pop_spread_y=.12))
        for a, b in zip(before[:3], after[:3]):
            np.testing.assert_array_equal(a, b)
        cells, mass, _, _ = cell_masses(paths, colors, 42, dict(block, pop_spread_xz=.2, pop_spread_y=0.))
        np.testing.assert_array_equal(cells[:, 1], 0)
        self.assertAlmostEqual(np.average(((cells[:, 2]+.5)/32)**2, weights=mass), .04, delta=.002)
        migrated = migrate_parameters(dict(pop_spread=.12, pop_spread_y=.03))
        self.assertEqual(migrated, dict(pop_spread_xz=.12, pop_spread_y=.03))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'points.bin'
            req = dict(generator='density_filament_curves', seed=42, count=100,
                       params=dict(curve_resolution=24, pop_spread=.12))
            response = worker.generate_request(req, ROOT/'generators', output)
            self.assertTrue(response['ok'], response.get('error'))
            self.assertNotIn('pop_spread', response['params'])
            self.assertEqual(response['params']['pop_spread_xz'], .12)
            self.assertEqual(response['params']['pop_spread_y'], .12)

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
        from _postprocess import density_fade_weights, apply_to_stars, relative_density_at_stars, edge_dense_threshold
        rho = np.array([.1, 1., 100., 10000.])
        np.testing.assert_array_equal(density_fade_weights(1., rho), np.ones(4))
        np.testing.assert_array_equal(density_fade_weights(.2, rho, 0), np.full(4, .2))
        output = rho * density_fade_weights(.2, rho)
        self.assertTrue((output <= .2 * (1 + 1/.8)).all())
        self.assertTrue((np.diff(output) > 0).all())  # No inverted dense/sparse ordering.
        self.assertLess(output[-1] / output[-2], 1.02)  # Edge peaks saturate.
        self.assertLess((rho * density_fade_weights(.02, rho)).max(), output.max() / 8)
        # The extra suppression leaves every sub-threshold density exactly alone.
        for strength in (0, 1, 4):
            np.testing.assert_array_equal(density_fade_weights(.2, np.linspace(0, 1, 101), strength),
                                          np.full(101, .2))
        around_knee = np.array([1-1e-5, 1., 1+1e-5])
        slopes = np.diff(around_knee * density_fade_weights(.2, around_knee, 4)) / 1e-5
        np.testing.assert_allclose(slopes, .2, rtol=1e-4)

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
        self.assertLess(np.count_nonzero(new < 6000), np.count_nonzero(old < 6000) * .75)
        # Sparse stars retain the exact baseline survivors, not just the count.
        np.testing.assert_array_equal(new[(new >= 6000) & (new < 9000)], old[(old >= 6000) & (old < 9000)])
        estimated = relative_density_at_stars(positions)
        self.assertTrue((estimated[6000:9000] <= edge_dense_threshold(estimated)).all())
        np.testing.assert_array_equal(new[new >= 9000], np.arange(9000, 10000))
        # With a shared random stream, the new fade only removes more stars.
        self.assertTrue(np.isin(new, old).all())

    def test_density_edge_suppression_preserves_faint_field_and_ignores_empty_volume(self):
        from _postprocess import fade_density, edge_dense_threshold
        density = np.full((21, 21, 21), .05)
        density[15:19, 8:13, 8:13] = 1.
        density[2:5, 8:13, 8:13] = .2
        sparse = density <= .25
        baseline = fade_density(density, .8, 0)
        for strength in (1, 4):
            faded = fade_density(density, .8, strength)
            np.testing.assert_array_equal(faded[sparse], baseline[sparse])
            self.assertTrue((faded[~sparse] < baseline[~sparse]).all())
            self.assertTrue((faded <= baseline).all())
        self.assertEqual(edge_dense_threshold(density), edge_dense_threshold(np.pad(density, 20)))
        np.testing.assert_allclose(fade_density(density*7, .8, 4), fade_density(density, .8, 4)*7)

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
                                  dict(pp_merge=1, pp_merge_distance=.15, pp_dense_fraction=1,
                                       pp_merge_size_boost=1))
        self.assertLess(len(p), len(positions) // 2)
        self.assertGreater(s.max(), sizes.max())
        before, after = sizes.astype(float)**3, s.astype(float)**3
        np.testing.assert_allclose(before.sum(), after.sum(), rtol=1e-6)
        np.testing.assert_allclose((positions * before[:, None]).sum(axis=0),
                                   (p * after[:, None]).sum(axis=0), atol=1e-8)
        np.testing.assert_allclose((colors * before[:, None]).sum(axis=0),
                                   (c * after[:, None]).sum(axis=0), atol=1e-8)

    def test_merge_boost_only_enlarges_combined_stars(self):
        from _appearance import apply_appearance, merge_dense, neighbor_spacing
        rng = np.random.default_rng(51)
        positions = np.vstack((rng.normal(0, .08, (2000, 3)), [[10, 0, 0]])).astype(np.float32)
        colors = rng.random(positions.shape).astype(np.float32)
        sizes = rng.uniform(.02, .06, len(positions)).astype(np.float32)
        spacing = neighbor_spacing(positions)[1]
        p, c, s, remaining = merge_dense(positions, colors, sizes, 42, spacing, .15, 1)
        self.assertGreater(remaining, 0)
        self.assertLess(remaining, len(p))
        for boost in (1, 2, 8):
            result = apply_appearance(positions, colors, sizes, 42,
                dict(pp_merge=1, pp_merge_distance=.15, pp_dense_fraction=1,
                     pp_merge_size_boost=boost))
            np.testing.assert_array_equal(result[0], p)
            np.testing.assert_array_equal(result[1], c)
            np.testing.assert_array_equal(result[2][:remaining], s[:remaining])
            np.testing.assert_allclose(result[2][remaining:], s[remaining:] * boost)
        # Visual boost saturates at the protocol limit, preserving grouping.
        huge = np.full(len(positions), 400., dtype=np.float32)
        base = merge_dense(positions, colors, huge, 42, spacing, .15, 1, 1)
        boosted = merge_dense(positions, colors, huge, 42, spacing, .15, 1, 8)
        np.testing.assert_array_equal(base[0], boosted[0])
        self.assertLessEqual(boosted[2].max(), 1000)

    def test_alignment_reclassifies_residual_stars_and_keeps_clumps_fixed(self):
        from _appearance import apply_appearance, merge_dense, neighbor_spacing
        rng = np.random.default_rng(21)
        positions = np.vstack((rng.normal(0, .03, (500, 3)), rng.uniform(-2, 2, (4000, 3)))).astype(np.float32)
        colors = rng.random(positions.shape).astype(np.float32)
        sizes = np.full(len(positions), .04, dtype=np.float32)
        tree, spacing = neighbor_spacing(positions)
        cutoff = np.quantile(spacing, .35)
        p, c, s, remaining = merge_dense(positions, colors, sizes, 42, spacing, .7, .6, 2)
        original_ids = tree.query(p[:remaining])[1]
        residual_spacing = neighbor_spacing(p[:remaining])[1]
        newly_sparse = ((spacing[original_ids] < cutoff) & (residual_spacing > cutoff))
        self.assertTrue(newly_sparse.any())
        params = dict(pp_merge=1, pp_merge_distance=.7, pp_dense_fraction=.6,
                      pp_curves=1, pp_curve_reach=.8, pp_sparse_fraction=.65,
                      pp_curve_colors=1)
        moved = apply_appearance(positions, colors, sizes, 42, params)
        distance = np.linalg.norm(moved[0][:remaining] - p[:remaining], axis=1)
        self.assertGreater(np.count_nonzero(distance[newly_sparse] > .001), 0)
        np.testing.assert_array_equal(moved[0][remaining:], p[remaining:])
        np.testing.assert_array_equal(moved[1][remaining:], c[remaining:])
        np.testing.assert_array_equal(moved[2], s)
        for a, b in zip(moved, apply_appearance(positions, colors, sizes, 42, params)):
            np.testing.assert_array_equal(a, b)

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
                             0 if (entry["primitive"] == "lines" and not entry["population"])
                             or getattr(modules[entry['id']], 'NATIVE_AXIS_FADE', False) else 1)
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

    def test_density_curve_is_monotone_local_and_scale_independent(self):
        from _postprocess import remap_density
        density = np.linspace(0., 1., 301)
        self.assertIs(remap_density(density), density)
        compressed = remap_density(density, high=.25)
        np.testing.assert_allclose(compressed[:201], density[:201], atol=1e-15)
        self.assertAlmostEqual(compressed[-1], .75)
        self.assertAlmostEqual(compressed[-1] - compressed[200], (1/3)*.25)
        for slopes in ((.05, 3, .05), (3, .05, 3), (.25, 1, .25)):
            result = remap_density(density, *slopes)
            self.assertEqual(result[0], 0.)
            self.assertTrue((np.diff(result) > 0).all())
            np.testing.assert_allclose(remap_density(7*density, *slopes), 7*result)
        np.testing.assert_array_equal(remap_density(np.zeros(8), high=.25), np.zeros(8))

    def test_noise_density_curve_precedes_fade_and_preserves_count(self):
        from unittest.mock import patch
        from _postprocess import remap_density, fade_density
        _, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        module = modules["noise_filaments"]
        original = module.generate(1000, 42)
        neutral = module.generate(1000, 42, density_low=1, density_mid=1, density_high=1)
        for a, b in zip(original, neutral):
            np.testing.assert_array_equal(a, b)
        # Inspect the actual sampling input to catch wrong order/double remapping.
        base = module.build_density(42)
        expected = fade_density(remap_density(base, .25, 1, .25), .8, 1)
        with patch.object(module, 'sample_density', wraps=module.sample_density) as sample:
            changed = module.generate(1000, 42, fade=1, density_low=.25, density_high=.25)
            np.testing.assert_array_equal(sample.call_args.args[0], expected)
        self.assertEqual(len(changed[0]), 1000)
        self.assertFalse(np.array_equal(changed[0], original[0]))
        np.testing.assert_array_equal(changed[2], original[2])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'stars.bin'
            request = dict(generator='noise_filaments', count=1000, seed=42,
                           params=dict(density_low=.25, density_high=.25, fade=1))
            response = worker.generate_request(request, ROOT / 'generators', output)
            self.assertTrue(response['ok'], response)
            self.assertEqual(response['count'], 1000)
            self.assertEqual(response['params']['density_high'], .25)
            first = output.read_bytes()
            self.assertTrue(worker.generate_request(request, ROOT / 'generators', output)['ok'])
            self.assertEqual(first, output.read_bytes())

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
            density = np.exp(module._strand_log_density(a, b, c, 0.065))
            self.assertTrue((density >= 0.99).all())
        # Being on just one zero surface must not produce a sheet.
        sheet = np.exp(module._strand_log_density(zero, zero + 1, zero + 1, .065))
        self.assertTrue((sheet < 1e-20).all())
        void = np.exp(module._strand_log_density(t * 0 + 1, t * 0 + 1,
                                                t * 0 + 1, 0.065))
        self.assertTrue((void < 1e-20).all())

    def test_three_field_density_is_symmetric_and_retired_controls_are_ignored(self):
        from itertools import permutations
        catalog, modules, errors = worker.load_catalog(ROOT / "generators")
        self.assertFalse(errors)
        module = modules['noise_filaments_branches']
        fields = np.random.default_rng(51).normal(size=(3, 1000))
        expected = module._strand_log_density(*fields, .065)
        for order in permutations(range(3)):
            np.testing.assert_allclose(module._strand_log_density(*fields[list(order)], .065), expected,
                                       rtol=1e-12, atol=1e-12)
        schema = next(entry for entry in catalog if entry['id'] == 'noise_filaments_branches')
        keys = {entry['key'] for entry in schema['parameters']}
        self.assertTrue(keys.isdisjoint({'connectivity', 'layer_continuity'}))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'stars.bin'
            request = dict(generator='noise_filaments_branches', count=1000, seed=42,
                           params=dict(y_scale=.15, density_high=.25))
            response = worker.generate_request(request, ROOT / 'generators', output)
            self.assertTrue(response['ok'], response)
            expected_bytes = output.read_bytes()
            request['params'].update(connectivity=0, layer_continuity=1)
            response = worker.generate_request(request, ROOT / 'generators', output)
            self.assertTrue(response['ok'], response)
            self.assertEqual(expected_bytes, output.read_bytes())
            self.assertNotIn('connectivity', response['params'])
            self.assertNotIn('layer_continuity', response['params'])

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
