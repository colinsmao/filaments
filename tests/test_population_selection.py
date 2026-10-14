"""Selection objectives, population identity, caching and worker integration."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'python'), str(ROOT/'generators')]
import worker
from _curve_selection import CurvePool, build_pool, short_candidates
from _population_selection import Sketch, build_sketch, rasterize, gram, greedy, select_population, population_proximity
from _block_population import cell_masses, populate_blocks
from _population_field import field_profiles
import density_population_selection as generator


def settings(**changes):
    catalog, _, errors = worker.load_catalog(ROOT/'generators', block_units=True, density_graph=True)
    assert not errors, errors
    schema = next(e for e in catalog if e['id'] == 'density_population_selection')
    p = {e['key']: e['default'] for e in schema['parameters']}
    p.update(changes)
    return p


def fixture():
    paths = tuple(np.array([[-30., y, 0.], [30., y, 0.]]) for y in (-25., 25.))
    return CurvePool(paths, np.array([[2,3,4], [12,13,14]]), np.ones((9,9,9)), np.full(3,100.))


class PopulationSelection(unittest.TestCase):
    def test_pair_restart_starts_separate_patches_but_not_unsupported_singletons(self):
        pairs=csr_matrix(np.eye(5))
        initial=np.array([-.9,-.7,-.7,-.7,-.4])
        near=csr_matrix([[0.,.9,0.,0.,0.],[.9,0.,0.,0.,0.],
                         [0.,0.,0.,.8,0.],[0.,0.,.8,0.,0.],[0.,0.,0.,0.,0.]])
        args=(pairs,initial,csr_matrix((5,5)),np.ones(5),0.,1.,1.,near,1.)
        before=greedy(*args)
        np.testing.assert_array_equal(before[0],[0,1])
        report={}
        ids,kinds,scores=greedy(*args,restart_patches=True,report=report)
        np.testing.assert_array_equal(ids,[0,1,2,3])
        np.testing.assert_allclose(scores,[-.9,-.6,-.5,-.5])
        self.assertFalse(kinds.any())
        self.assertEqual(report['patch_restarts'],1)

    def test_pair_restart_includes_mutual_overlap_once_and_normalizes_combined_mass(self):
        # Unequal masses: calculate the joint quadratic error directly.
        q=np.array([[1.,0.,0.],[0.,1.,0.],[0.,.4,1.6]])
        target=np.array([1.4,.9,1.4])
        pairs=gram(csr_matrix(q),1.)
        initial=.5*pairs.diagonal()-q@target
        mass=q.sum(axis=1)
        near=csr_matrix([[0.,0.,0.],[0.,0.,.9],[0.,.9,0.]])
        report={}
        ids,roles,scores=greedy(pairs,initial,csr_matrix((3,3)),mass,0.,1.,1.,near,1.,
                               restart_patches=True,report=report)
        np.testing.assert_array_equal(ids,[0,1,2])
        modeled=q[0]
        combined=q[1]+q[2]
        expected=(.5*np.sum((modeled+combined-target)**2)-.5*np.sum((modeled-target)**2)
                  +.1*(mass[1]+mass[2]))/(mass[1]+mass[2])
        np.testing.assert_allclose(scores[1:],[expected,expected])
        self.assertFalse(roles.any())
        self.assertEqual(report['patch_restarts'],1)
        # Two individually attractive duplicates can overfill the same target.
        pairs=csr_matrix([[1.,0.,0.],[0.,1.,1.],[0.,1.,1.]])
        ids,_,_=greedy(pairs,np.array([-.9,-.4,-.4]),csr_matrix((3,3)),np.ones(3),0.,1.,1.,
                       near,1.,restart_patches=True)
        np.testing.assert_array_equal(ids,[0])

    def test_pair_restart_has_no_effect_without_isolation_or_eligible_neighbors(self):
        pairs=csr_matrix(np.eye(3));rod=csr_matrix((3,3))
        initial=np.array([-.9,-.4,-.4]);near=csr_matrix([[0.,0.,0.],[0.,0.,1.],[0.,1.,0.]])
        args=(pairs,initial,rod,np.ones(3),0.,1.,1.,near,0.)
        for a,b in zip(greedy(*args),greedy(*args,restart_patches=True)):
            np.testing.assert_array_equal(a,b)
        # A zero-mass neighbor cannot justify starting a patch.
        ids,_,_=greedy(pairs,initial,rod,np.array([1.,1.,0.]),0.,1.,1.,near,1.,restart_patches=True)
        np.testing.assert_array_equal(ids,[0])
        ids,_,_=greedy(pairs,initial,rod,np.ones(3),0.,1.,1.,csr_matrix((3,3)),1.,restart_patches=True)
        np.testing.assert_array_equal(ids,[0])

    def test_population_proximity_matches_nearest_positive_mass_samples(self):
        points=np.array([[0.,0.,0.],[2.,0.,0.],[0.,0.,0.],[4.,0.,0.],
                         [5.,2.,0.],[100.,0.,0.],[0.,0.,0.]])
        weights=np.array([1.,1.,0.,1.,1.,1.,0.])
        owners=np.array([0,0,1,1,2,3,4])
        sketch=Sketch(points,weights,owners,np.arange(5),None,np.ones(3),np.ones(5))
        actual=population_proximity(sketch,3.).toarray()
        expected=np.zeros((5,5))
        for i in range(5):
            for j in range(i+1,5):
                a=points[(owners==i)&(weights>0)]
                b=points[(owners==j)&(weights>0)]
                if len(a) and len(b):
                    distance=np.linalg.norm(a[:,None]-b,axis=2).min()
                    if distance<12.:
                        expected[i,j]=expected[j,i]=np.exp(-(distance/3.)**2)
        np.testing.assert_allclose(actual,expected,atol=1e-15)
        self.assertEqual(actual[0,1],np.exp(-(2/3.)**2))  # Zero-weight contact ignored.
        with patch('_population_selection.cKDTree',side_effect=AssertionError('Distance cache missed')):
            self.assertIs(population_proximity(sketch,3.),population_proximity(sketch,3.))

    def test_isolation_penalty_bootstraps_then_rejects_floating_curve(self):
        pairs=csr_matrix(np.eye(3))
        initial=np.array([-.9,-.4,-.4])
        near=csr_matrix([[0.,.9,0.],[.9,0.,0.],[0.,0.,0.]])
        args=(pairs,initial,csr_matrix((3,3)),np.ones(3),0.,1.,1.)
        ids,kinds,scores=greedy(*args,near,.7)
        np.testing.assert_array_equal(ids,[0,1])
        np.testing.assert_allclose(scores,[-.9,-.33])
        plain=greedy(*args)
        off=greedy(*args,near,0.)
        for a,b in zip(plain,off):
            np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(plain[0],[0,1,2])

    def test_multiple_contacts_do_not_accumulate_an_attachment_bonus(self):
        near=csr_matrix([[0.,1.,.5],[1.,0.,.5],[.5,.5,0.]])
        ids,_,_=greedy(csr_matrix(np.eye(3)),np.array([-.9,-.8,-.3]),csr_matrix((3,3)),
                       np.ones(3),0.,1.,1.,near,1.)
        np.testing.assert_array_equal(ids,[0,1])

    def test_rod_does_not_anchor_an_isolated_candle(self):
        rod=csr_matrix([[1.,1.,0.],[1.,1.,0.],[0.,0.,0.]])
        near=csr_matrix([[0.,0.,0.],[0.,0.,1.],[0.,1.,0.]])
        ids,kinds,_=greedy(csr_matrix(np.eye(3)),np.array([-1.,.1,-.4]),rod,
                           np.ones(3),.2,1.,1.,near,.75)
        np.testing.assert_array_equal(ids,[0,1])
        np.testing.assert_array_equal(kinds,[0,1])

    def test_isolation_scores_match_direct_recomputation(self):
        rng=np.random.default_rng(871)
        q=rng.uniform(0,1,(12,9))
        q[q<.7]=0
        mass=q.sum(axis=1)
        target=rng.uniform(1.,3.,9)
        weight=1/(target+.02)
        pairs=gram(csr_matrix(q),weight)
        initial=.5*pairs.diagonal()-q@(target*weight)
        coordinates=rng.uniform(0,15,(12,3))
        distance=np.linalg.norm(coordinates[:,None]-coordinates,axis=2)
        near=np.exp(-(distance/5.)**2)
        np.fill_diagonal(near,0.)
        ids,kinds,scores=greedy(pairs,initial,csr_matrix((12,12)),mass,0.,1.,1.,csr_matrix(near),.65)
        chosen=[];reference=[];modeled=np.zeros(9)
        while len(chosen)<12:
            error=.5*np.sum(weight*(modeled-target)**2)
            values={i:(.5*np.sum(weight*(modeled+q[i]-target)**2)-error)/mass[i]
                    +(.65*(1-near[i,chosen].max()) if chosen else 0.)
                    for i in range(12) if i not in chosen and mass[i]>1e-12}
            if not values:
                break
            best=min(values,key=values.get)
            if values[best]>=-1e-10:
                break
            chosen.append(best);reference.append(values[best]);modeled+=q[best]
        np.testing.assert_array_equal(ids,sorted(chosen))
        np.testing.assert_allclose(scores,reference,atol=1e-12)
        self.assertFalse(kinds.any())

    def test_short_length_mixture_preserves_roots_and_each_independent_trajectory(self):
        cells = np.array([[x,y,z] for x in (-25,0,25) for y in (-25,25) for z in (-25,25)])
        density, half = np.ones((9,9,9)), np.full(3,100.)
        p = settings(strand_length=40.,short_curve_length=12.,length_variation=.4)
        field = tuple((e['key'],p[e['key']]) for e in generator.FIELD_PARAMETERS)
        def pool(**changes):
            values = dict(p,**changes)
            return build_pool(28,field,tuple((e['key'],values[e['key']]) for e in generator.LOCAL_PARAMETERS))
        build_pool.cache_clear()
        with patch('_curve_selection.build_field',return_value=(density,None,half)):
            with patch('_curve_selection.block_seeds',return_value=cells):
                long = pool(short_curve_fraction=0.)
                short = pool(short_curve_fraction=1.)
                mixed = pool(short_curve_fraction=.65)
                # A dormant short length cannot change the old single-length pool.
                disabled = pool(short_curve_fraction=0.,short_curve_length=7.)
        mask = short_candidates(cells,28,.65)
        self.assertTrue(mask.any() and (~mask).any())
        np.testing.assert_array_equal(mixed.owners,cells)
        for i,path in enumerate(mixed.paths):
            np.testing.assert_array_equal(disabled.paths[i],long.paths[i])
            np.testing.assert_allclose(path,(short if mask[i] else long).paths[i],atol=1e-12,rtol=0)
            arc = np.linalg.norm(np.diff(path,axis=0),axis=1).sum()
            mean = 12. if mask[i] else 40.
            self.assertGreaterEqual(arc,mean*.6-1e-9)
            self.assertLessEqual(arc,mean*1.4+1e-9)
        # Increasing the fraction changes class only in a nested, stable subset.
        self.assertTrue(np.all(~mask | short_candidates(cells,28,.85)))

    def test_incremental_candle_scores_match_direct_density_error(self):
        rng = np.random.default_rng(29)
        q = rng.uniform(0,1,(9,7))
        q[q < .6] = 0
        mass = q.sum(axis=1)
        target = rng.uniform(.3,1.5,7)
        weight = 1/(target+.02)
        pairs = gram(csr_matrix(q), weight)
        initial = .5*pairs.diagonal()-q@(target*weight)
        ids, kinds, scores = greedy(pairs, initial, csr_matrix((9,9)), mass, 0., .5, 5.)
        modeled = np.zeros(7)
        expected, expected_scores = [], []
        available = set(np.flatnonzero(mass > 1e-12))
        while available:
            error = .5*np.sum(weight*(modeled-target)**2)
            values = {i:(.5*np.sum(weight*(modeled+q[i]-target)**2)-error)/mass[i] for i in available}
            chosen = min(values, key=values.get)
            if values[chosen] >= -1e-10:
                break
            expected.append(chosen); expected_scores.append(values[chosen])
            modeled += q[chosen]; available.remove(chosen)
        np.testing.assert_array_equal(ids, sorted(expected))
        np.testing.assert_allclose(scores, expected_scores, atol=1e-12)
        self.assertFalse(kinds.any())

    def test_short_turning_leaves_long_paths_roots_and_arc_budgets_unchanged(self):
        cells = np.array([[x,y,z] for x in (-25,0,25) for y in (-25,25) for z in (-25,25)])
        density, half = np.ones((9,9,9)), np.full(3,100.)
        p = settings(strand_length=40.,short_curve_length=24.,short_curve_fraction=.65,
                     growth_response=8.,growth_wander=.15,length_variation=.4)
        field = tuple((e['key'],p[e['key']]) for e in generator.FIELD_PARAMETERS)
        def pool(values):
            return build_pool(28,field,tuple((e['key'],values[e['key']]) for e in generator.LOCAL_PARAMETERS
                                           if e['key'] in values))
        legacy = {k:v for k,v in p.items() if k not in ('short_growth_response','short_growth_wander')}
        build_pool.cache_clear()
        with patch('_curve_selection.build_field',return_value=(density,None,half)):
            with patch('_curve_selection.block_seeds',return_value=cells):
                before = pool(legacy)
                equivalent = pool(dict(p,short_growth_response=8.,short_growth_wander=.15))
                after = pool(dict(p,short_growth_response=2.,short_growth_wander=.8))
                build_pool.cache_clear()
                repeat = pool(dict(p,short_growth_response=2.,short_growth_wander=.8))
        np.testing.assert_array_equal(before.owners,after.owners)
        np.testing.assert_array_equal(after.short_mask,short_candidates(cells,28,.65))
        self.assertFalse(after.short_mask.flags.writeable)
        chord_ratios = [[],[]]
        for i,(old,new) in enumerate(zip(before.paths,after.paths)):
            np.testing.assert_array_equal(equivalent.paths[i],old)
            np.testing.assert_array_equal(repeat.paths[i],new)
            self.assertTrue(np.any(np.all(new==cells[i]+.5,axis=1)))
            old_arc = np.linalg.norm(np.diff(old,axis=0),axis=1).sum()
            new_arc = np.linalg.norm(np.diff(new,axis=0),axis=1).sum()
            self.assertAlmostEqual(old_arc,new_arc,places=9)
            if not after.short_mask[i]:
                np.testing.assert_array_equal(new,old)
            else:
                chord_ratios[0].append(np.linalg.norm(old[-1]-old[0])/old_arc)
                chord_ratios[1].append(np.linalg.norm(new[-1]-new[0])/new_arc)
        self.assertLess(np.median(chord_ratios[1]),np.median(chord_ratios[0])-.04)

    def test_short_rod_penalty_can_reserve_a_candle_without_forcing_acceptance(self):
        candle = csr_matrix(np.eye(3))
        near = csr_matrix(np.ones((3,3)))
        initial = np.array([-2.,-.3,.1])
        args = (candle,initial,near,np.ones(3),.2,.75,1.)
        plain = greedy(*args)
        zero = greedy(*args,rod_penalty=np.zeros(3))
        for a,b in zip(plain,zero):
            np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(plain[1],[0,1,1])
        ids,roles,_ = greedy(*args,rod_penalty=np.array([0.,.5,0.]))
        np.testing.assert_array_equal(ids,[0,1,2])
        np.testing.assert_array_equal(roles,[0,0,1])
        # An unhelpful short candle is rejected instead of being forced in.
        ids,roles,_ = greedy(candle,np.array([-2.,.1,.1]),near,np.ones(3),.2,.75,1.,
                             rod_penalty=np.array([0.,1.,0.]))
        np.testing.assert_array_equal(ids,[0,2])
        np.testing.assert_array_equal(roles,[0,1])

    def test_density_budget_allows_one_to_three_duplicates(self):
        # Identical footprints are allowed only as far as their target warrants.
        q = csr_matrix(np.array([[1.,0.]]*5+[[0.,1.]]*5))
        target = np.array([1.,3.])
        pairs = gram(q, 1/target)
        initial = .5*pairs.diagonal()-q@np.ones(2)
        ids, _, _ = greedy(pairs, initial, csr_matrix((10,10)), np.ones(10), 0., 1., 1.)
        self.assertEqual(sum(ids<5),1)
        self.assertEqual(sum(ids>=5),3)

    def test_overlap_is_mass_weighted_and_accumulates_over_shared_extent(self):
        # Four shared bins cost four times one shared bin: no binary contact flag.
        q = csr_matrix([[1.,1.,1.,1.], [1.,1.,1.,1.], [1.,0.,0.,0.], [2.,2.,2.,2.]])
        k = gram(q, 1.).toarray()
        self.assertEqual(k[0,1],4*k[0,2])
        self.assertEqual(k[0,3],2*k[0,1])
        self.assertEqual(gram(q, .25)[0,1],.25*k[0,1])

    def test_rods_need_candles_and_redundant_rods_lose(self):
        candle = csr_matrix(np.ones((4,4))*10)
        # Candle 0, rods 1/2 have same footprint, candidate 3 is far away.
        near = csr_matrix([[1.,1.,1.,0.], [1.,1.,1.,0.], [1.,1.,1.,0.], [0.,0.,0.,1.]])
        initial = np.array([-2.,1.,1.,1.])
        ids, kinds, _ = greedy(candle, initial, near, np.ones(4), .2, .75, 5.)
        np.testing.assert_array_equal(ids,[0,1])
        np.testing.assert_array_equal(kinds,[0,1])
        ids, _, _ = greedy(candle, np.ones(4), near, np.ones(4), .2, .75, 5.)
        self.assertEqual(len(ids),0)
        ids, kinds, _ = greedy(candle, initial, near, np.ones(4), .2, 0., 5.)
        np.testing.assert_array_equal(ids,[0])
        self.assertFalse(kinds.any())

    def test_raster_mass_conservation_and_smooth_local_interaction(self):
        positions = np.array([[.1,.2,.3], [.2,.2,.3], [8.,8.,8.]])
        sketch = Sketch(positions,np.array([2.,3.,4.]),np.arange(3),np.arange(3),None,np.ones(3),np.array([2.,3.,4.]))
        q, _ = rasterize(sketch,1.)
        np.testing.assert_allclose(np.asarray(q.sum(axis=1)).ravel(),sketch.mass)
        k = gram(q,1.).toarray()
        self.assertGreater(k[0,1],0)
        self.assertEqual(k[0,2],0)

    def test_candidate_and_quadrature_limits_precede_expensive_work(self):
        p=settings()
        with patch('_curve_selection.block_seeds',return_value=np.zeros((3,3),dtype=int)):
            with patch('_curve_selection.build_field',return_value=(np.ones((3,3,3)),None,np.ones(3))):
                with patch('_curve_selection.grow_field',side_effect=AssertionError('Limit was checked after growth')):
                    with self.assertRaisesRegex(ValueError,'candidate seeds'):
                        build_pool(79,tuple((e['key'],p[e['key']]) for e in generator.FIELD_PARAMETERS),
                                   tuple((e['key'],p[e['key']]) for e in generator.LOCAL_PARAMETERS),max_candidates=2)
        pool=fixture()
        too_many=CurvePool(pool.paths*750,np.zeros((1500,3),dtype=int),pool.density,pool.half)
        with self.assertRaisesRegex(ValueError,'sketch samples'):
            build_sketch(too_many,79,(),257)  # 257 rounds up to 512, not 257.

    def test_sketch_shares_mass_profiles_scatter_taper_and_stable_identity(self):
        pool = fixture()
        p = settings(pop_source_density=.5,pop_clumping=1.,pop_taper=.2,pop_spread_xz=2.,
                     pop_spread_y=1.,fade_xz=0,fade_y_enabled=0,pp_warp=0)
        sketch = build_sketch(pool,52,tuple(sorted(p.items())),512)
        # Select just the second path: no renumbered RNG or renormalized density.
        context = dict(p,_curve_ids=sketch.identities,_population_profiles=sketch.profiles,
                       _curve_kinds=np.array([0,1]),_warp_spread=sketch.warp_spread)
        colors = np.ones((2,3))
        cells, masses, rgb, stats = cell_masses(pool.paths,colors,52,context)
        for i in (0,1):
            one = dict(context,_curve_ids=sketch.identities[i:i+1],_population_profiles=sketch.profiles[i:i+1],
                       _curve_kinds=np.array([i]))
            c,m,col,s = cell_masses(pool.paths[i:i+1],colors[i:i+1],52,one)
            mask = stats['_block_owners'] == i
            np.testing.assert_array_equal(c,cells[mask])
            np.testing.assert_array_equal(m,masses[mask])
            np.testing.assert_array_equal(col,rgb[mask])
            ratio = 1. if i == 0 else p['pop_rod_density']
            self.assertAlmostEqual(m.sum(), sketch.mass[i]*ratio, delta=.01*m.sum())
        # Scatter changes the footprint, without changing the mass budget.
        narrow = build_sketch(pool,52,tuple(sorted(dict(p,pop_spread_xz=0.,pop_spread_y=0.).items())),512)
        np.testing.assert_array_equal(narrow.mass,sketch.mass)
        self.assertFalse(np.array_equal(narrow.points,sketch.points))

    def test_explicit_default_identity_preserves_shared_sampler_bytes(self):
        pool=fixture(); colors=np.ones((2,3)); p=settings(pop_source_density=.5,pop_clumping=1.)
        original,stats = populate_blocks(pool.paths,colors,73,p,density_source=(pool.density,pool.half))
        explicit,other = populate_blocks(pool.paths,colors,73,dict(p,_curve_ids=np.arange(2)),density_source=(pool.density,pool.half))
        for a,b in zip(original,explicit):
            np.testing.assert_array_equal(a,b)
        for key in ('_block_shapes','_block_kinds','_fade_groups'):
            np.testing.assert_array_equal(stats[key],other[key])

    def test_viewer_schema_worker_roles_and_selection_cache(self):
        catalog,_,errors=worker.load_catalog(ROOT/'generators',block_units=True,density_graph=True)
        self.assertFalse(errors)
        schema=next(e for e in catalog if e['id']=='density_population_selection')
        controls={e['key']:e for e in schema['parameters']}
        self.assertLessEqual(len(controls),96)
        self.assertEqual(controls['strand_length']['default'],120.)
        self.assertEqual(controls['short_curve_fraction']['default'],.75)
        self.assertEqual(controls['short_growth_response']['default'],2.)
        self.assertEqual(controls['short_growth_wander']['default'],.8)
        self.assertEqual(controls['select_short_rod_penalty']['default'],.5)
        self.assertEqual(controls['select_restart_patches']['default'],1)
        self.assertTrue(controls['short_curve_length']['description'])
        self.assertEqual(controls['pop_spread_xz']['default'],generator.PARAMETER_DEFAULTS['pop_spread_xz'])
        self.assertEqual(controls['extent']['scope'],'density_field')
        for key in generator.OMIT_POPULATION_PARAMETERS:
            self.assertNotIn(key,controls)
        for key,entry in controls.items():
            if key.startswith('select_'):
                self.assertEqual(entry['section'],'selection')
                self.assertTrue(entry['description'])
        params=dict(seed_rate=20.,strand_length=70.,seed_xz=.9,seed_y_pos=.9,seed_y_neg=.9,
                    select_budget=4.,select_density=0.,select_rod_attraction=2.)
        request=dict(generator='density_population_selection',count=100,seed=42,world_units='blocks',
                     density_graph=True,density_field=dict(extent=96.,y_extent=24.,field_resolution=24),params=params)
        build_pool.cache_clear();build_sketch.cache_clear()
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'points.bin'
            first=worker.generate_request(request,ROOT/'generators',file)
            self.assertTrue(first['ok'],first.get('error'))
            with patch('_curve_selection.grow_field',side_effect=AssertionError('Scoring edit retraced curves')):
                with patch('_population_selection.field_profiles',side_effect=AssertionError('Scoring edit rebuilt sketch')):
                    second=worker.generate_request(dict(request,params=dict(params,select_budget=5.,select_short_rod_penalty=1.,select_restart_patches=0)),ROOT/'generators',file)
                self.assertTrue(second['ok'],second.get('error'))
                third=worker.generate_request(dict(request,params=dict(params,pop_spread_xz=2.)),ROOT/'generators',file)
                self.assertTrue(third['ok'],third.get('error'))
            self.assertEqual(first['selection_stats']['candidates'],second['selection_stats']['candidates'])
            self.assertIn('patch_restarts',first['selection_stats'])
            self.assertEqual(second['selection_stats']['patch_restarts'],0)
            self.assertNotIn('_curve_ids',first['params'])
            self.assertEqual(file.with_suffix('.stars.bin').read_bytes()[:8],b'FSTAR003')
            # All-candle comparison really overrides the random material lottery.
            off=worker.generate_request(dict(request,params=dict(params,select_enabled=0)),ROOT/'generators',file)
            self.assertTrue(off['ok'],off.get('error'))
            shapes=np.frombuffer(file.with_suffix('.stars.bin').read_bytes()[16:],'<f4').reshape(-1,10)[:,7:]
            self.assertTrue((shapes[:,1]==6/16).all())
            self.assertEqual(off['selection_stats']['rods'],0)


if __name__ == '__main__':
    unittest.main()
