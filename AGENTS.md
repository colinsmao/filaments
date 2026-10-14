# Continuing this project

Read this file and `README.md` before changing the project. This is a handoff of
the current implementation, not a commitment to continue any particular experiment.

## Purpose and user preferences

- Screenshot parameter trial (2026-10-13): user requested one final parameter
  attempt using estimated build width200–350/height40–70 blocks. Chosen offline
  preset domain275x55x275, shared field wavelength24/width.045/resolution64; other
  field controls retained. Rate450, root XZ.86/Y+/-.65, seed power.8; short fraction.8,
  lengths12/48, variation.7; long response3/pull.4/wander.12, short2/.65. Population
  .85/source.4/curve variation.35; retained narrow spread.2/.1 and lighting.02/.1/1.
  Selection budget4/contrast.5/scale5, isolation.5/reach5, patch restarts on. Rod
  intensity.2/attraction1/repulsion5/scale12, short rod penalty.75;128 sketch samples.
  Edge fades XZ.12/Yends.2 with extra density suppression0. No algorithm/default
  code changes or planets.13 tuned variants plus baseline compared; higher rates,
  wider support, broader field, shorter lengths and stronger short curl tested.
  Current seed1919363634:972 candidates->697 candle(566 short)/150 rod curves;
  7466 candle objects+722 rods vs1550+147 before. Actual bounds267x52x252 blocks.
  Five seeds:894–972 candidates,7394–8188 objects; none integration-limited.
  Candidate-supported16-block XZ-bin coverage96.2–99.2%, not world volume coverage.
  Fresh Python5.7–6.3s; warm selector35–48ms. Native below/oblique renders inspected
  for3 seeds and whole canopy for chosen seed; still regular strings in places,
  no planets/scenery/detailed candle meshes. User visual acceptance not assumed.
  Evidence build/final-scale-tuning/{selected-preset.json,reference-comparison.png,
  chosen-whole.png,verification.json}, frozen requests and local sweep scripts.
  User disputed the density/visual match; this is an applied trial, not an accepted
  screenshot match. Camera/block-size calibration and a measured screenshot density
  target were missing. Starting actual bounds268x53x252 were already near chosen
  bounds; the comparison does not demonstrate a major physical scale correction.
  Full-white diagnostic retains the gaps/strings (render-audit.png/json); lighting
  alone does not explain the mismatch, and physical density accuracy is unverified.
  After user confirmed closure, verified no viewer process, backed up latest config
  to build/final-scale-tuning/plot-before-apply.json, then applied only recipe deltas
  to the active local preset and shared field. Latest camera (changed during this
  pass), inactive controls and other local presets preserved. Regenerating saved
  config produces byte-identical curve/star buffers to balanced-rods comparison;
  applied-validation.json records checks. No viewer launch/rebuild.
  Subsequent user viewer edits saved pop_density=.6 and
  pop_curve_density_variation=.95, plus a new camera. Preserve those latest edits
  in the requested checkpoint; the counts/byte comparisons above describe the
  applied .85/.35 trial, not these later settings.

- Isolation collapse correction (2026-10-13): user reported mostly empty results,
  not errors. Reproduced with frozen seed1697566617, extent137.695/Y40, rate100,
  short fraction.5, density.535, budget2.958, overlap4.031, isolation1/reach6.812.
  Normalized candle benefit is <1; a near-1 isolation penalty prevented distant
  patches from ever starting, sometimes keeping only the first short curve.
  Compared isolation off, lower strength.5, shorts-only isolation and pair restarts
  over11 seeds. Lower strength still lost regions/restored more floaters; shorts-only
  helped but cannot solve all-short pools. Implemented select_restart_patches=1,
  viewer label Allow new candle patches, off restores old stop rule exactly.
  When no candle/rod singleton qualifies, score nearby unused candle pairs using
  (D_i+D_j+K_ij+m_i*I_i+m_j*I_j)/(m_i+m_j), with one mutual-overlap term and
  I_i=w*(1-max(selected affinity_i,pair affinity)). Accept best negative pair
  atomically as candles, resume singles; stop if no improving pair. First candle
  still exempt; no extra singleton exception, roots, forced quotas or random draws.
  Pair graph reuses cached closest-positive-mass-sample affinities; no new distance
  or gradient queries. Scans edges per restart, so dense graphs can cost more.
  Existing geometry, population/lighting formulas and live settings untouched.
  New toggle loaded/autosaved by viewer. No launch, main executable rebuild or restart.
  11 seeds: candle curves1–51 ->49–67; coverage of16-block XZ bins with>1 expected
  candidate candle .4–64% ->64–80% (not whole-world volume coverage). Isolated short
  candles at6.812-block sample distance0–1/result, versus6–16 with isolation off.
  Frozen failing scene490->1694 objects; seed763813 2->1856. All-short seeds1001 /
  763813 recovered1->75 /1->71 candle curves. Legacy toggle-off curve/star binaries
  match build/short-turn-evaluation/short-turns.* byte-for-byte. Warm small-scene
  selector~5–7ms;953-candidate check23->39ms. Native before/after inspected; visual
  acceptance still user's judgment.171 Python tests/native panel startup pass.
  Evidence build/coverage-diagnosis/ holds frozen settings, alternative comparisons,
  native comparison.png, variant-checks.json and verification/results.json. Repeat
  sweep with scripts/evaluate_patch_restarts.py --settings <frozen settings path>.
  This fixes patch bootstrap, not a guarantee of complete coverage or connectivity.

- Short turning / candle preference (2026-10-12): user requested faster turns on
  shorts and fewer shorts consumed by rods. Incremental experiment now exposes
  short_growth_response=2 blocks (1–128) and short_growth_wander=.8 (0–2).
  Existing response/wander relabeled Long; density pull stays shared. Same
  grow_field math, coherent two-octave noise and roots/budgets; short batch gets
  its own controls. Long candidate paths byte-identical. Matching short controls
  to long values restores previous geometry. Other experiments inherit unchanged
  controls. CurvePool carries a read-only short_mask; no new random streams.
  select_short_rod_penalty=.5 (0–2) adds a dimensionless cost to normalized rod
  scores for shorts only. Zero restores equal role rules. Soft preference leaves
  shorts available for density filling; does not force candles or forbid all rods.
  Selection remains candle-proximity/rod-redundancy, not unlit-gap detection.
  Score edits reuse pool/sketch/proximity caches. No population/lighting changes.
  Preserved user's current rate40.271, short fraction.5, variation1, rod intensity
  .101 and all other saved settings; frozen397 candidates,208 short. Response2 /
  wander.8 raised median integrated turning42->163deg, chord/arc .982->.872;
  isolated short growth ~42->59ms. Stronger wander1.5 curls more but selected
  fewer candles, giving a sparser native render, so .8 retained. With rod penalty.5,
  short roles46 candle/94 rod ->91/15; all roles145/159->192/84; final objects
  8315 candles+839 rods ->8964+679. New choices can change selected long roles and
  population through competition; only long candidate geometry is invariant.
  Native below/oblique images inspected; no claim of user visual acceptance.
  168 Python tests and native panel startup pass. Live viewer autosaved all three
  new defaults on Python reload; no config writes, launch, rebuild or restart.
  Evidence: build/short-turn-evaluation/{settings.json,turn-sweep.json,role-sweep.json,
  render-results.json,comparison.png,turn-comparison.png}; local sweep/render scripts
  alongside evidence operate only on the frozen copy.

- Isolation penalty trial (2026-10-12): user found too many floating short strands
  and authorized trying a nearest-population isolation penalty. Incremental selector
  adds select_isolation=.9 (dimensionless,0–2) and select_isolation_distance=8 blocks
  (1–32) in Curve selection. After the first candle, add w*(1-exp(-(d/r)^2)) to
  the mass-normalized candle score; d is closest positive-weight sketch-sample
  distance to selected CANDLE curves. First candle uses old score; rods never
  anchor candles, and rod scoring is unchanged. One approach suffices, multiple
  contacts do not accumulate; geometry/population/lighting formulas unchanged.
  Zero and selection-off bypass proximity computation; zero verified byte-identical
  to prior frozen curve/star outputs. No final-occupancy connectivity guarantee.
  Cached sparse affinities use AABB pruning and batched cKDTree nearest queries,
  not all point pairs. Beyond4r affinity0 (omitted <=exp(-16)); no self edges or
  zero-mass samples.2m directed-edge guard. Strength edits reuse the cache;
  distance edits rebuild. First construction ~.56–1.09s at8 blocks on fixture,
  warm selection~28ms/full Python~2.04s; timings depend on viewer/test contention.
  User had reduced seed rate to50.167; retained that and all other saved settings.
  Frozen624-candidate scene: off471 candle/108 rod curves,12879 objects; on212/153,
  9268 objects. Short candles with no other candle sketch within8 blocks87/375->1/119.
  Actual candle components of <=30 cells at4-block adjacency925->495 (includes
  sampling gaps, not source-curve counts). Average near-parallel multiplicity
  at8-block/30-degree diagnostic1.278->1.284; arc with>3 neighbors .292%->.349%.
  Moderate strength.65 retains10921 objects; high strength/small reach can collapse
  to one cluster. Native below/oblique comparisons inspected, visual acceptance
  pending.166 Python tests/native panel startup pass. Viewer loaded new controls
  through Python reload; live saved settings reproduce tested strong buffers.
  No config writes, visible launch, main viewer rebuild or restart needed.
  Evidence build/isolation-evaluation/{settings.json,sweep.json,render-results.json,
  comparison.png,validation.json}; repeat sweep via scripts/evaluate_isolation_selection.py.

- Screenshot tuning / short candidates (2026-10-12): user requested narrower
  coherent strings, visible rods, dimmer faint candles and short strands in dense
  areas, specifically targeting `Screenshot 2026-10-10 232941` and
  `vlcsnap-2026-10-10-23h47m08s611` in scar/. This authorizes the following lighting
  tuning for the incremental experiment; other accepted lighting remains intact.
  `density_population_selection` adds short_curve_fraction=.75 and
  short_curve_length=24 blocks beside long mean120. Stable root hash chooses
  class; same .6 length variation, density-guided growth and whole-curve selector.
  Independent short/long batches avoid long histories for short roots; zero
  fraction preserves the old single-length pool exactly. Existing scripts do not
  expose/use the mixture. No changed overlap objective, cutting or joining.
  Tuned defaults: rate96, seed power1, response8.276/pull.35/wander.15, root XZ.803
  and Y roughly10.9..86.7 in frozen field; pop density.9, source influence.35,
  curve variation.25, narrow spread XZ.2/Y.1 blocks, rod intensity.2, budget5,
  rod attraction.75/repulsion5, samples128. Shared field unchanged. Lighting
  sky.10/ambient.02/lift1 changes only this script's defaults/preset; formula and
  base palette unchanged. Lavender is still a material choice, not a light-state
  flag. On identical geometry unlit candle mean RGB luminance .636->.347,
  level8+ candles .740->.645, rods .957->.956. Curves/positions/shapes/counts
  byte-identical across lighting comparison.
  Compared single/mixed lengths, short24/36, rate64/96/128, lights.05/.10/.16,
  population density and source-density choices. Chosen frozen scene1169
  candidates ->670 candle/243 rod curves ->15731 candle objects/1824 rods;
  558 candle/197 rod curves short. Normal sampler limit1.63m probes reached;
  diagnostic4.46m probes gives17575 total vs17555 (+.11%), not per-cell convergence.
  Warm selection59–64ms, Python total~2.7s, fresh pool/sketch total~3.4s in one run;
  live-viewer contention gave slower runs. No universal speed guarantee.
  Native close-below, oblique and broad views inspected; more continuous long
  strings than references remain. No claim of a match or user visual acceptance.
  Artifacts: build/narrow-tuning/{selected-preset.json,chosen-request.json,
  chosen.stars.bin,reference-comparison.png,lighting-comparison.png,validation.json}.
  161 Python tests and native panel startup pass. Python reload only; no viewer
  rebuild or auto-launch. After user closed the viewer, applied only the incremental
  local preset; shared density, camera and other presets unchanged. Preserved the
  user's inactive jitter/clump-scale values. Backup:
  build/narrow-tuning/plot-before-screenshot-tuning.json. Re-generating the saved
  config gives byte-identical curve and star buffers to the inspected chosen render.

- Incremental population selection trial (2026-10-12): user authorized a simple
  candle/rod selector after rejecting independent shapes and curve-only overlap.
  New separate `density_population_selection.py` reuses density-guided growth with
  joining off, then selects whole curves using expected population sketches.
  Shared density DAG remains upstream; original/branching/coverage/corpus scripts
  are preserved. Local defaults copied from current curve preset, except seed
  rate32, mean length180 (was320.183), proxies on, rod intensity.2 (was.036).
  Candle score is marginal weighted density error per expected star; target is
  pop_density*grid_spacing*budget*(rho/peak)^contrast, inverse target weight with
  2% peak floor. Rod score rewards candle proximity and penalizes rod redundancy,
  including self cost. Two roles interleave, each candidate used once, stop at
  nonnegative score. No lighting evaluation, curve cutting, joins or swaps.
  Defaults budget4, contrast.5, candle grid8 blocks, rod grid12, attraction.5,
  repulsion5,128 Sobol samples/curve. All controls exposed with descriptions;
  new Curve selection UI section and result counts require native rebuild.
  Toggle off populates entire same pool as candles; rods shown gold in preview.
  Star profiles/scatter/taper/warp and approximate edge survival drive footprints;
  final occupancy and fade suppression remain approximate in selection. Profiles
  normalized across candidate pool, retained through sampling, with seed-cell
  identities preserving per-path randomness under subset changes. Optional private
  population context affects only this experiment; old paths retain index IDs.
  Full-block role omitted; existing accepted lighting settings unchanged.
  Growth/sketch caches separate; score/rod-intensity/lighting changes reuse sketch.
  Local sparse interactions, worst-case quadratic;2048 seed guard before growth,
  524288 sketch samples,2m entries per interaction matrix. No silent pool truncation.
  Frozen scene274 candidates->116 candle/39 rod curves->3946 candle objects/213 rods,
  versus12021 candles with selection off. At8-block/30-degree diagnostic reach,
  99.7% of selected candle arc has1–3 near-parallel candle paths (69.1% all candidates).
  This is measured, not a hard cap or connectivity guarantee. Some thin connections
  disappear; user visual acceptance pending. Compared rates16/32/48/64 and lengths
  120/180/240/320, plus rod weights and128/256 samples. Warm selection7–15ms, full
  Python generation.7–1.2s on fixture, startup excluded. build/incremental-evaluation
  holds frozen preset, sweeps, metrics and inspected native/curve comparisons.
  160 Python tests and native panel startup pass. Viewer rebuilt after user closed
  the locked executable. No live config edits or viewer launch.

- Lighting checkpoint accepted (2026-10-11): user said "close enough, save".
  Preserve the Scar lighting correction and current viewer-autosaved settings
  as the accepted lighting baseline. Do not resume visual tuning automatically.

- Scar lighting correction (2026-10-11, supersedes trial below): user explicitly
  wants the screenshots matched, not another fidelity audit. Native offscreen
  renders of three brighter trials selected sky .35, brightness1, ambient .03,
  sky RGB (.8,.82,1). `_block_lighting.light_colors` now uses Java1.21.8's normal
  warm block RGB ramp, two neutral mixes and quartic lift, plus adjustable extra
  ambient. All canopy cells assumed exposed sky15. No emitter full-bright bypass.
  With extra ambient0, all16 values agree with actual GPU shader within1.04e-7.
  Palette: brighter cream candles, retained gray/lavender contrast, near-white rods,
  pale cream luminous blocks. Worker migrates only untouched old lighting triples
  (.03 or .08,.2,.5) to (.03,.35,1); custom combinations remain. Normal autosave only.
  Same4668 stars and byte-identical curves/positions/shapes/sizes on saved fixture.
  `build/scar-lighting-before-after.png` includes native before/after, another
  camera below canopy and Scar reference. Visually inspected; no exact scene or
  screenshot-settings equivalence claimed. Validation:137 Python tests plus native
  perspective/material and panel startup checks pass. Python-only, no viewer launch/rebuild.

- Block lighting trial (2026-10-11): shared `_block_lighting.py` runs in the
  worker after all proxy survival fades, before legacy display conversion.
  Rods emit14, full blocks15, candles0 (unlit). Max(E-Manhattan distance,0),
  exact nearest-source queries per emission class; no occlusion, colored light,
  relay, sky propagation or bloom. `_block_kinds` now survives sampling as private
  metadata, filtered with shapes by surviving cells; never inferred from RGB.
  pop_lighting defaults on; pop_light_ambient fraction0–1/default.03 adds neutral
  ambient. pop_light_sky0–1/default.2 adds uniform cool (.65,.7,1) sky illumination
  so unlit exposed candles remain visible beyond local source range. Sum ambient,
  sky and L/(60-3L), clamp, then blend with1-(1-C)^4 using pop_light_brightness
  0–1/default.5. Approximation inspired by Java1.21 lightmap, not screenshot-derived
  settings. Sources keep base RGB; renderer face shading retained. Off/ambient1
  restore base RGB exactly. Existing settings (including interim ambient.08) stay.
  No geometry/count/shape/RNG changes, continuous/unit-cube modes bypass.
  FSTAR003 unchanged; Python reload only. No live config edits or viewer launch.
  Fading sources can now darken nearby survivors; base palette stays unchanged.
  Validation:136 Python tests pass, native panel startup passed. Saved scene
  snapshot4668 objects (4287 candles/366 rods/15 blocks):2644 candles have no
  local block light and receive sky/ambient. Lighting ~3.65ms in one run;
  on/off curve bytes, positions, counts, sizes and shapes identical. Appearance
  still needs user judgment; settings snapshot/paired buffers under build/lighting-*.

- Direction-change checkpoint (2026-10-11): user requested saving this state
  before changing direction. Both independent field growth and the separate
  branching script are preserved, along with viewer presets and scar references.
  Neither experiment has visual acceptance. Await the new direction rather than
  continuing to tune merging or branching automatically.

- Separate scripts (2026-10-11, supersedes active replacement below): user meant
  "try branching" as a NEW SCRIPT, not replacing the existing generator. Keep
  experiments separate unless replacement is explicit. `density_filament_curves.py`
  restores independent field growth, seed_rate/strand_length and merge controls.
  `density_filament_branching.py` owns the branching trial and its own preset.
  Worker treats both as native curve consumers of the same upstream density DAG;
  block migration/schema/star processing stay shared. No C++ rebuild required.
  Frozen split check: old field growth4982 vertices/922 stars; new branching1894
  vertices/378 stars, branch curve/star buffers byte-identical to pre-split trial.
  Prior replacement autosave removed the old seed/length/join keys; recovered
  from build/merge-evaluation-settings.json after viewer closed and user explicitly
  approved config repair. Current branch preset preserved separately, latest camera
  and shared density retained. Backup: build/plot-before-script-split.json. Both
  Python suite and native panel checks pass. Never write live settings.

- Rooted branching trial (2026-10-11, supersedes proximity consolidation): user
  rejected merging and authorized branching. Active shared-density curve path
  now calls `_branching_field.grow_branches`; new branch_root_rate=.5 mean roots
  per million blocks, branch_length=1200 total blocks per root, branch_spacing=48
  blocks, branch_angle=45 degrees. Old seed_rate/strand_length/join controls are
  removed from active schema, not reinterpreted; helpers/direct API remain for
  comparison. Same block sampler/seed power/seed zones, sparse roots. Two-way trunk
  uses coordinate-hashed Beta budget; child gets35% of parent's remaining budget,
  parent keeps65%, no new budget. Opportunities at seeded .75–1.25*spacing travel;
  need child budget>=spacing. Eight cone directions, density-weighted selection
  among in-domain/free coarse occupancy probe cells .75*spacing ahead. Child
  field guidance ramps quadratically over one spacing; existing wandering stays.
  Spatial hash size max(response,spacing/4) only gates births and stops tips
  re-entering their own exited cells. No joins, pair guides, neighbor forces or
  post-growth deletion. Exact shared parent vertices; root halves combined for
  shared population/material/taper continuity. Preview colors identify roots.
  Shared stars/fades reused; per-path material choices still separate on branches.
  Explicit2m possible-step guard, existing vertex limit. Hash slabs65536 preserve
  seeds and measured .29->.12s seeding. Frozen scene:4 roots,20 children,arc3856,
  stars378,growth .06s,warm native total .31–.33s,cold1.09s (not universally<1s).
  build/branch-camera-comparison.png shows trial; some density reconvergence
  remains. Python/schema reload only, persistent worker already rebuilt. No live
  config edits or auto-launch. Tests cover junctions, per-root budgets, bounds,
  determinism, departure angles and active dispatch away from merging/guides.

- Proximity consolidation / speed (2026-10-11, supersedes same-block-only joins):
  active `_field_curves.grow_field` uses `_proximity_contacts.py` when exposed
  growth_join_distance>0 (blocks, default16, range0–64); zero restores old block
  contacts. Exact proposed/deposited segment distances and existing angle gate;
  all candidates in radius, no fixed nearest-K cutoff. Fresh fronts yield by
  coordinate-order owner; targets >=2 batches old allow either priority. Source
  ancestry prevents a receiver stopping against its feeder; both feeder tips may
  attach. Six-segment cubic connectors match incident tangents, fit remaining arc
  budgets and domain, and are deposited exactly as rendered. No neighbor forces,
  guides, deleted prefixes, seed changes or budget transfer. Direct helper default
  distance0 preserves legacy tests; active generator default16. Saved85-root scene:
  arc14369->9179, sustained parallel arc4408->958 (-78%, distance8/angle30/runs24+),
  joins69->112, stars1429->922, growth .21->.12s. Saved-camera comparison in
  build/merge-camera-comparison.png; residual separate curves/loops remain.
  `_block_population.unique_cells` packs lexicographic keys for faster unions,
  preserving cell order/inverse indices/probes/random draws; wide-domain fallback.
  GenerationService now owns a persistent stdin-driven Python worker. Source
  fingerprint change (helpers included), cancel, timeout or crash restarts it;
  job close kills descendants. Atomic responses, serial jobs, latest request wins.
  Standalone runGeneration remains one-shot. Warm native total about .9s on scene,
  occasional1.02s with background viewer load; cold about2s, not a universal bound.
  Requires rebuilt viewer for worker reuse. No live config writes or auto-launch.

- Zone region lengths (2026-10-11): range bars now show three labeled positive
  spans in blocks: lower excluded/seed span/upper excluded or lower fade/unfaded
  span/upper fade. Values are (1-neg,neg+pos,1-pos)*halfExtent, summing to full
  axis length even across zero. No-extent fallback is percent of full span.
  Signed coordinate editors remain, now explicitly labeled Lower/Upper. No math,
  saved setting, sampling or layout-group changes; viewer rebuild required.

- Cross-zero ranges / common Y fade (2026-10-11, supersedes earlier UI constraints):
  asymmetric handles may cross zero, never each other. seed_y_pos/neg min=-1,
  lower=-seed_y_neg, upper=seed_y_pos; offset seed intervals use the same sampler.
  Y fade has one fade_y_enabled toggle above its paired bar in Y edge fade group.
  Widths0–2 map to lower=neg_width-1 and upper=1-pos_width. Width0 bypasses that
  end exactly; width>1 starts fading beyond zero. Shared star fade evaluates signed
  directional coordinates without half-space masks, preserving widths<=1 output.
  Old side toggles migrate to common OR; if either was on, disabled ends get width0;
  if both off, saved widths remain. Legacy direct calls with side toggles still work.
  Same hashed draws, per-curve fade thresholds and clump suppression retained.
  Display header now DefaultOpen. Tests:126 Python pass, native range interaction
  and startup pass, cross-zero hidden preview checked in build/zone-bars.png.

- Zone UI correction (2026-10-11, supersedes UI notes below): user rejected
  logarithmic seed rate. Linear slider now 0–100 via slider_max metadata; numeric
  validation/default remain0–10000/500 so existing settings are not clamped.
  Zone numeric inputs now edit signed absolute coordinates from schema zone_extent,
  with percentages underneath; active DAG uses blocks, legacy uses generator units
  or percent fallback without a fixed extent. Stored fractions unchanged. Restored
  separate +Y/-Y fade groups; paired bar at former +Y width slot. Signed seed pair
  inserted at former seed_y slot beside XZ rather than appended. Rebuilt, native
  interaction/startup and Python schema/migration tests pass. Hidden render checked.

- Zone range bars (2026-10-11): `_zone_controls.annotate_zones` marks all existing
  seed-region/fade-width schemas for `src/zone_slider.h`. Signed Y pairs share one
  independent two-handle bar; symmetric controls mirror handles automatically.
  Percent positions span -100..100 with a zero tick, blue central seed interval,
  orange outer fade bands. Fade handles show 1-width, saved semantics unchanged.
  Each side stays on its side of zero, with exact Ctrl-click numeric entry below.
  Y fade groups combined; side toggles and suppression retained. Disabled side
  handles/fields cannot edit. Geometry/RNG/defaults/config untouched by UI change.
  Rebuilt viewer now includes these bars and previously pending log seed slider.
  Hidden widget rendering saved build/zone-bars.png; interaction tests cover
  independent/linked dragging and bounds. Shared-settings panel fixture explicitly
  uses rate5, since mean-normalized default500 with length300 exceeded its10s budget.
  No viewer auto-launch or live config writes. No viewport-edge overview added.

- Signed Y seed bounds (2026-10-11): active DAG UI replaces seed_y with
  seed_y_pos/neg, fractions0–1/default.65, labeled reach from center. Allowed
  central Y interval is [-neg*halfY,+pos*halfY]; roots are excluded outside,
  but curves/stars can extend beyond it. No new taper. Legacy seed_y copies to
  both unless explicit signed values exist; legacy non-DAG retains symmetric UI.
  Equal signed settings exactly preserve old seeds. Region edits affect expected
  count and normalized density weights, not coordinate hashes. Tests cover both
  one-sided bounds, asymmetric normalization, zero volume and migration priority.
  Python reload only. Logarithmic rate slider remains pending native relink while
  viewer is open. Edge seed/fade bars discussed for feasibility, not implemented.

- Seed normalization (2026-10-11, supersedes peak-rate interpretation below):
  seed_rate is now Mean seeds per million blocks. Acceptance is
  hash < rate/1e6 * w/mean(w), w=(trilinear density/peak)^power; mean is over
  all block centers in the fractional seed region. Probabilities saturate at1;
  no refill or forced count. Empty positive-power density gives no seeds. Power0
  is byte-identical uniform sampling. Exact mean uses separable plane interpolation
  with bounded temporary arrays, and hash prefilter uses rate/1e6/mean(w).
  Hash streams, defaults, limits, growth and joining unchanged. Region/power edits
  can redistribute seeds; increasing rate remains nested. Saved rate50/power1:
  0->668 seeds, sampler .40s, worker success4.39s/1336 stars. Focused tests compare
  direct block-center probabilities and fractional-region means across powers.
  Python reload only; no live config writes. Log slider still needs native relink.

- Seed-rate UI (2026-10-11): seed_rate now requests a logarithmic slider via
  schema hint logarithmic=true. Range 0–10000, default500 and sampling are
  unchanged; small positive rates are now mouse-selectable. The old linear
  slider's first pixel could mean ~52 seeds/million. Ctrl-click permits exact
  numeric entry in either viewer. C++ panel change requires rebuild/restart.

- Block contact joining (2026-10-11): _field_curves now uses incremental
  _block_contacts.BlockContacts during active direct growth. growth_join toggle
  defaults on; growth_join_angle degrees 0–90/default30 accepts abs tangent dot,
  including opposite headings. Larger angles permit more contacts/count changes;
  no new RNG. Every positive-length cell span is traversed with DDA, including
  long steps and negative coordinates; mere corner touches are excluded.
  All accepted segments per cell retained, with shared segment records and
  per-cell clipping parameters. First eligible block attaches arriving tip to
  closest target point to entry, clipped to that block and remaining budget.
  Tip stops, existing geometry stays fixed, own source (both halves) excluded.
  Stable seed/half order deposits only accepted proposals immediately, including
  same-step targets. No forces, proximity search radius, speculative segments,
  global tree rebuild, root resampling, post-growth deletion or budget refill.
  Connected branches keep separate path/material identities; contact does NOT
  impose the old guide-interval max-budget bound on entire connected components.
  Saved current scene rate52.083 uniform, length140.193:690 paths retained,
  236 joins, arc91415.56->86476.28; growth .17s off/.89s on. Population remains
  a separate cost; full worker3.42s off/4.27s on, stars15861/15074 after tests.
  Earlier 6557-root timings below predate joins. Tests cover
  DDA, crossing/anti-alignment, long steps, own source, multiple occupants,
  budget refusal, deterministic contacts and surviving outward continuations.
  Python reload only; no configuration edits or viewer launch.

- Guide removal (2026-10-11, supersedes block seed trial geometry below): active
  density_graph requests for density_filament_curves use _field_curves.grow_field.
  Accepted block centers stay as actual roots. No extract_paths, projection,
  interval union, pair assignment, repulsion or child spawning. Block contacts
  were subsequently added as described above. Finite
  two-way growth samples DensityShape's local log-density gradient/Hessian with
  heading persistence and optional VectorNoise. Budgets retain coordinate-hashed
  Beta variation, half per tip; stop only on budget/domain, clipping final segments.
  Density affects births and steering, not lifetime. Three exposed controls:
  growth_response blocks 1–128/default8 (smoothing, response, step=response/2),
  growth_pull 0–2/default.35 (transverse density attraction, not neighbors),
  growth_wander 0–1/default.15 (coherent Perlin perturbation). Each changes
  geometry/counts, never seed draws. No native code changes/config writes.
  Legacy non-DAG callers retain old arc-root geometry for comparison/tests.
  Hash selection now uses axis-product batches, avoiding full XYZ arrays until
  hash acceptance, and samples density only for candidates; identical old seeds.
  Saved density-power1: 69 roots/curves, field .05s, seeds .33s, growth .08s,
  population .55s. Uniform power0 retains6557 curves instead of old131 merged
  intervals, greatly increasing star-population cost; performance there remains
  unresolved. Never silently lower seed rate. 8m possible tip-step guard, plus
  existing binary vertex limit. No visual equivalence/acceptance claimed.

- Block seed trial (2026-10-11): active shared-density-graph curve requests now
  use _grid_density_curves.py instead of arc roots. Hash every unit-block center
  in the existing fractional seed box; accept against rate*1e-6*(rho/peak)^power.
  seed_rate defaults 500 per million peak-density blocks (0–10000),
  seed_density_power defaults 1 (0–4); 0 is uniform, including empty-density cells.
  Selection occurs before guide extraction. Only accepted seeds project onto
  nearest pair-zero guide segments. Thus block centers are sampling identities,
  not the final projected root positions. No taper or post-growth selection.
  Each root's coordinate hash gives Beta(2,2) budget mean*(1+v*(2*Beta-1));
  existing strand_length is now Mean curve length (blocks), and length_variation
  is exposed (0–1, default .5). Density no longer scales these budgets.
  Simultaneous two-tip intervals join on the SAME guide only if combined length
  fits max(component budgets), never their sum. Failed contacts stop tips;
  exhausted tips never restart. Loops wrap. Winning budget's block gives color.
  No fixed curve count; saved scene default gave 69 seeds/40 curves vs old40,
  power0 gave6557/131 (~2.7s seeding/projection/growth each, excluding field/stars).
  Seeds, curve lengths and star counts vary with these controls. Hashes are stable;
  extent/resolution can still alter normalized field and guide projections.
  Guards reject >100m tested cells or >8192 accepted seeds rather than truncate.
  Legacy non-DAG requests retain arc roots. Python reload only; no config writes.
  Seed power is separate from pop_source_density, which controls stars on curves.

- Original density population influence (2026-10-11): stable curves expose
  pop_source_density, dimensionless exponent 0-3, default1. Zero exactly bypasses.
  generate_population_density_source returns the already-built (density, half)
  with the usual source triple; worker uses it only when influence is positive.
  _population_field.field_profiles samples pre-fade density on unwarped curve
  centerlines, raises it to the exponent and normalizes once across all arc
  length. Combined with normalized existing along-curve noise, profile integrals
  change per-curve expected counts and CDFs change local placement in BOTH samplers.
  Dense curves can gain stars; no per-curve normalization erases their contrast.
  Existing variation/material multipliers/taper/occupancy can change final counts.
  No new RNG, geometry, scatter-width or seed changes. Integration uses 4 samples
  per field cell along each path and existing 32 samples per finest density-noise
  scale, each bounded to 262144 intervals per curve plus its vertices. Slider0 keeps previous
  output byte-identical. Python/schema reload only; no config writes/rebuild.

- Corrected upstream density DAG (2026-10-11): _density_field.py owns the
  physical field schema and build_field. Both branches direct sampling and stable
  curve extraction consume identical A/B/C and density arrays at a shared
  field_resolution (migrated from curve_resolution; default48, range24–96).
  The rebuilt viewer sends density_graph=true and one density_field object;
  GeneratorPanel directly edits that object through schema scope=density_field.
  Consumer presets contain only local controls; upstream keys are removed once,
  and no capture/apply bidirectional sync remains. density_settings.h is legacy
  import/removal only. Existing density_field wins; otherwise import curve preset.
  Branches' local sizes/postprocessing lengths migrate once using legacy display
  scale; both active consumers thereafter generate/render directly in blocks.
  Frequency is replaced by the upstream block wavelength. Legacy worker requests
  without density_graph remain compatible with a still-running older viewer.
  Other comparison experiments retain their adapters. Grid resolution now affects
  both consumers; their algorithms/output distributions still differ. Camera and
  curve seed logic unchanged. Rebuild/restart needed; no external config writes.

- Block-coordinate migration (2026-10-11): the rebuilt viewer requests
  world_units=blocks. Active density_filament_curves presets migrate once via
  _world_units.py: lengths multiply by old pop_block_scale (16 if continuous),
  population density divides by it; fractions and random streams stay unchanged.
  Its viewer schema now exposes lengths in blocks and pop_blocks (on/off), with
  no scale control. _block_units=1 is stored preset metadata, not a UI parameter.
  Curve math receives block lengths directly; population uses unit cells and
  emits their centers/sizes directly, with no inverse display conversion.
  Legacy worker requests/direct Python APIs and comparison generators retain
  their old units; the new viewer adapts comparison output at the boundary.
  Plot/control unit flags independently guard one-time camera target/distance,
  clip-plane and movement-speed migration, including partial autosave recovery.
  Only normal viewer autosave writes settings. Rebuild/restart required; an old
  running viewer keeps the legacy protocol until restarted. Saved scene check:
  scale16, 30,404 curve vertices and 2,835 cells/colors/shapes preserved exactly.
  The later block seed trial above replaces arc roots in the active DAG path.

- Material edge fade now shares a seeded threshold per selected source curve
  (2026-10-11 user request), equally for candles, rods and full blocks, carried as
  private _fade_groups through the worker. Low thresholds keep objects farther
  into fade regions. Continuous/unit-cube modes retain independent draws. Existing
  envelopes/clump suppression still apply; no changes to geometry or tip taper.
  Per-star marginal survival stays the same, but correlated decisions change
  fixed-scene counts. Stable density curves now expose fade_y_pos/neg with separate
  width/suppression controls. migrate_signed_y copies old symmetric Y controls into
  both, explicit side keys win. World +Y above / -Y below, not camera-relative.
  Shared star fade accepts both schemas; older density/growth experiments keep
  symmetric controls. Defaults match previous settings; Python reload only.
- Shared transverse spread now has independent pop_spread_xz/pop_spread_y controls
  (2026-10-11 user request), each std-dev scale in generator units, default .035,
  range 0-.5. Old pop_spread migrates to both; explicit new keys win. Continuous
  and block samplers share normal-plane anisotropic Gaussian scaling, keeping
  offsets perpendicular to the tangent. Y=0 adds no vertical scatter; equal values
  exactly preserve old draws/positions. No geometry/count-budget/RNG changes;
  discrete cell occupancy and position-based fading can change final counts.
  Python reload only; no config files edited externally.
- Material proxies (2026-10-11): block sampling defaults to one seeded material
  and candle palette color per source path. Candle/rod/full-block curve weights
  82/15/3 normalize to material probabilities, not final object ratios. At least
  one positive weight required. Old pop_rod_fraction migrates to equivalent weights
  preserving prior seeded material choices. Rod intensity multiplier .4; full-block
  multiplier .05 now makes block curves extremely sparse, per user direction to
  keep everything curve-based. Both apply before integration; 0 removes that type's
  population, 1 matches candles. Shape/scatter/geometry unchanged. Python reload only.
  Crossings choose one source proportional to its cell mass, no mixed materials.
  Per-cell candles 1-4 use widths 2/4/5/6 sixteenths, height 6/16; group probabilities
  .50/.27/.15/.08 (truncate/renormalize at maximum). Rods 1 by 2/16 by 2/16,
  independently equal XYZ axes. Full blocks unit cubes. All cell-centered; no
  flames, caps, placement support, lighting or planets yet. pop_colors overrides
  palette only. pop_block_proxies=0 restores unit-cube comparison. Curve generation
  and continuous sampler unaffected. Fading preserves shape attributes.
  FSTAR003 adds three shape floats; C++ Point/GPU stride40, legacy FSTAR002 stride28
  still read with unit shape. Python parameter limit96 (formerly64). Renderer needs
  rebuild/restart; subsequent Python edits reload. Never overwrite live config.
- Extent correction (2026-10-11): active `density_filament_curves.py` now exposes
  `noise_scale` (generator units, default 9.458/2.505, range .1-60) instead of
  normalized `frequency`. Presets migrate once as extent/frequency; the shared
  density builder receives frequency=extent/noise_scale. XZ/Y bounds therefore
  sample more of a fixed world-space field instead of stretching its features.
  Other generators keep prior conventions; explicit legacy Python frequency
  calls still work. Saved pre-migration scene geometry/colors remain identical.
  Fixed-resolution interpolation, path IDs/root phases, support normalization,
  and fractional seed/fade regions can still change interiors on extent edits:
  this is not immutable append-only star generation. No config writes/rebuild.
- Minecraft direction (2026-10-11): all 21 screenshots in `scar/` are the visual
  target: shallow patchy canopy, fine pale objects, occasional bright rods/cubes,
  dark gaps. Planets are a future milestone and may be larger than stars.
  Keep fitted generator units, then uniformly scale into block coordinates.
  `_population.py` now dispatches an optional cell sampler in `_block_population.py`:
  `pop_block_scale` 0 retains continuous stars exactly; 1-128 is blocks per unit.
  Sobol integration estimates mass per cell from the same curve density/scatter;
  contributions combine before Bernoulli occupancy p=1-exp(-mass). No fixed-count
  promise, finished-star snapping, or collision refill. Half-integer centers,
  unit base sizes and stable per-cell seeded draws inside the sampler. The worker
  divides final block positions/sizes by scale for display; curve preview and
  camera stay in generator units. Scale16 displays a block as 1/16 viewer unit.
  Warp precedes integration cell assignment; point fade follows using scaled bounds.
  Merge/sparse-star alignment must be off (explicit error). Jitter and continuous
  size controls do not apply. Sampler default off, no external config edits.
  Scale changes no longer enlarge the scene. Use display size multiplier 1 for blocks.
  Integration is approximate, globally capped at 2,097,152 probes with a warning;
  very fine grids/large scatter can under-resolve masses even below the cap.
  Saved scene seed 934903968: scale16 yields 1693 cells vs1668 continuous stars,
  ~.94s vs.28s excluding startup. See README; visual acceptance pending.
- Latest direction (2026-10-11): `density_filament_curves.py` grows directly in
  shared density from coordinate-hashed block seeds (see guide removal above).
  XZ/Y edge fade now thins only stars, leaving curves byte-identical.
  Earlier growth is retained as `density_filament_growth.py`; appearance still
  needs user judgment. Shared stars/postprocessing remain the baseline.
- Build visually interesting distributions of stars: galaxies, filaments, voids,
  and other patterns. Appearance matters more than physical accuracy. Minecraft
  may be a later destination; currently this is a math playground and viewer.
- The current baseline is **curve generation -> shared star population -> shared
  postprocessing**. New patterns should primarily change how curves are generated,
  reusing the existing star sampler, controls and postprocessors. Stochastic
  filaments is the current implementation to follow; its particular noise/growth
  algorithm is replaceable. Keep curves and stars independently visible.
- Zel'dovich and the earlier direct-star generators remain comparison experiments.
  Appearance, especially tapering and edge behavior, still needs user judgment.
- Keep math separate from rendering and favor Python edits that reload live.
  Keep existing experiments available for comparison unless asked to remove them.
- Do not launch the viewer automatically. The user often keeps it running. Do not
  stop it to build; ask them to close it if Windows locks the executable. Python
  changes usually require neither a rebuild nor a restart.
- Commit at useful checkpoints, especially before a new direction. Do not commit
  immediately after every edit; leave room for the user's next adjustment. An
  explicit request to save the state is authorization to commit it.
- Use native Windows; WSL is unnecessary. Keep OpenGL 3.3 unless a concrete feature
  requires something newer. Avoid unnecessary dependency/environment changes.
- Y is vertical; XZ is the horizontal plane.
- Explain each new parameter when introducing it: its meaning, units, randomness
  direction and whether it changes star count. Keep along-curve density/spacing
  separate from transverse scatter.

## Architecture

- For new patterns, use `PRIMITIVE = "lines"` and implement
  `generate_population_source(count, seed, **params)` returning
  `(line_attributes, paths, path_colors)`, following `stochastic_filaments.py`.
  Keep `generate` as a wrapper returning the line attributes. Paths are ordered
  polylines, excluding preview markers. Leave star placement in `_population.py`
  and subsequent appearance processing in the shared worker pipeline; do not
  duplicate these stages inside each new curve generator.
- `src/main.cpp`: GLFW/ImGui main loop and cloud upload. `camera.h`,
  `camera_controls.h`, `point_renderer.h`: camera, controls, points/instanced cubes.
  Cubes have simple fixed face shading, no outlines. Points have perspective size.
  Mouse capture versus drag controls, Space/Shift vertical movement, right-click
  FOV zoom, and a center crosshair are already implemented.
- `src/generation.cpp` / `.h`: asynchronous Python subprocess jobs, cancellation,
  source watching and binary transfer. No per-frame Python or embedded interpreter.
  A fresh worker starts for each generation. The old cloud remains visible on error.
- `src/generator_panel.h`: renders the Python-provided schema. `int` and `float`
  entries are sliders; `toggle` makes a checkbox. `group` creates a subsection in
  Postprocessing, and `enabled_if` references another control's 0/1 value. Shared
  control names, groups, ranges and defaults can change in Python without restart.
  New widget types or changes to the C++ panel layout need a rebuild.
- `python/worker.py`: discovers `.py` generators (ignores leading `_` helpers),
  validates schemas/arrays, appends shared postprocessing controls, runs generation
  and postprocessing, and writes `FSTAR002` binary data. Header: 8-byte magic plus
  uint64 count, followed by count XYZ/RGB/size float32 records (28 bytes/star).
  Block proxies use FSTAR003, adding XYZ shape multipliers (40 bytes/star).
  Input count is 1â€“1,000,000. Actual output may be smaller after merging/fading.
  Zero-point primary clouds are rejected. Curve population sidecars may be empty.
  Job timeout defaults to 60 seconds.
- Generators expose `NAME`, `PARAMETERS`, and `generate(count, seed, **params)`.
  Return positions and colors shaped `(count, 3)`, plus scalar/per-star sizes.
  Existing worker support for legacy two-array returns must remain intact.
  Shared control names beginning `pp_` and `pop_` are reserved by the worker.
- Python files under `generators/` and the worker are watched, including new files.
  Worker/schema errors are shown in the GUI without discarding the last valid cloud.

## Current math experiments

- Broad-density trial: checkpoint `b9f9455` snapshots all preceding code and
  saved viewer settings. Shared `noise_filaments_branches.build_density` now
  applies one extra Perlin octave after remapping and before axis fading:
  rho *= exp(broad_strength*(B-max(B))), B at frequency/broad_scale, seed stream
  505. Strength default 4, range 0-12; scale default 2, range 2-8 base wavelengths.
  Strength 0 bypasses exactly (verified against snapshot). A/B/C/clump streams
  and local scales stay unchanged. Both branch stars and density curves share
  the implementation/schema. Counts fixed for direct stars; curve starts/budgets
  fixed but paths and final counts can change. Broad concentration can increase
  overlap locally; no promise of visual acceptance. No external config edits.
  Snapshot-preset comparison in build/broad-density-comparison.png: 1408 ->1413
  stars, pipeline ~1.46 ->1.61s excluding startup, initial one-run comparison.

- Legacy arc-root path in `density_filament_curves.py` / `_stable_density_curves.py`
  (active DAG path now uses the block seed trial above): same branch-density A/B/C streams, all pair intersections extracted
  with existing `_curves.intersect_fields` on a 48^3 tetrahedral grid (24–96 control).
  Exact within that interpolation, not the continuous Perlin function. Fixed
  arc-spaced roots (1 unit) grow finite two-way intervals on their original path;
  lifetime = mean_length*(.5+Beta(2,2))*support. Mean length 2 units.
  Support is unfaded density divided by mean density over all candidate
  roots, clamped to 0..1. Independent XZ/Y seed-region fractions .65 confine roots;
  geometry can extend outside. User requested removal of the unrequested internal
  length taper (2026-10-11): seed regions now only admit/exclude roots, preserving
  travel of retained roots. Star edge fades and density support unchanged. No density-based
  seed resampling, pair changes, wandering, joining, or coverage steering.
  Same-path interval unions prevent duplicate overlap; closed loops wrap.
  Colors derive from original path IDs, not surviving output indices.
  Edge fade was corrected after the seed-only implementation left sharp Y edges:
  POPULATION_AXIS_FADE opts into shared point-stage XZ/Y survival, after merging
  and warp, with postprocess_bounds fixing actual XZ/Y half-extents. Curves and
  raw population no longer depend on fade. Stronger fades retain a subset of
  final stars without moving/recoloring/resizing them. Width 1 tapers from center
  to zero at the boundary. Long curves still hit the box in the line preview.
  Shared population unchanged; density/seed-region edits can still resample stars.
  Saved seed 714462872: Y off/.4/1 gives 1895/1589/944 stars, 265/51/5 in outer
  20% Y; curve buffers byte-identical. Worker pipeline about .34s excluding startup.
  Positive Y extent required (UI minimum .01); previous growth retains flat-Y.
  Saved-scene central seeding reduced outer-20% length 334.9->25.8, stars 630->39,
  with inner-40% length unchanged at 44.89. Central generation plus sampling ~.23s.
  See build/stable-fade-comparison.png and README. Visual acceptance is pending.

- `density_filament_growth.py` / `_density_curves.py`: preserved local-alignment
  experiment, now sharing `noise_filaments_branches.build_density` with the direct
  branch sampler (equal AB/AC/BC, clumps, three-regime remap). No layer continuity
  or connectivity. Independent XZ/Y bounds and shared axis density fades apply
  before roots/guidance; legacy y_scale/shared fade migrate in the worker using
  this experiment's historical defaults. No live config writes. Fading changes
  curve placement/length and therefore star counts, not post-star survival.
  Density-sampled roots grow short two-way strands.
  Each complete path now gets a distinct HSV hue (golden-ratio sequence with
  independent seed stream 82421 phase); joins retain each path's color. Shared
  pop_colors optionally passes these to stars. No geometry/count/size changes.
  CURRENT GUIDANCE: curves now retain an assigned AB/AC/BC family. The builder
  optionally returns its original A/B/C grids via _return_fields, without new
  noise calls. Family drawn at birth proportional to the local pair terms,
  seed stream 82517, fixed for both halves. In 3D PairFilamentShape caches raw
  physical scalar gradients and reuses _stochastic_curves.guidance for pair
  cross-product tangent and regularized normal correction. Combined density
  only supplies roots, coverage and survival envelope, never the tangent.
  Also stop on a tenfold assigned-pair decline, except explicit final contact.
  Steering neighbors must share the pair; actual contact permits any pair/angle
  and terminates the arriving half. No child spawning or silent family changes.
  Tiny-Y fallback uses three separate pair-density Hessians, retaining heights.
  Existing direction_scale is now Filament response length; density_pull is
  Pull toward assigned filament. Finite attraction/wandering remain, not hard
  centerline projection. Colors/shared population unchanged. Saved scene: 175
  paths, family counts 62/56/57; full pipeline ~1.18s excluding startup.
  Mean total strand length now permits 0.2-30 units (formerly capped at 6),
  still split equally between the two halves. Saved values remain literal.
  In the user's short-curve scene, 6 ->12 increased median actual length from
  3.4 ->5.6; box exits and joins dominated stops, not the new pair-support check.
  Close-parallel overlap fix: pair-mode contact no longer waits for load .75
  when the target has the same family and abs dot >=cos(25deg). Use existing
  min(join_radius, join_reach), after two steps, and lower source index priority
  so both tips do not stop against each other's prefixes. Other contact types
  keep the coverage gate. No finished-path deletion or screen-space checks.
  Fixed saved scene: overlapping arc 545 ->285 units (~48% less), total arc
  966 ->769; 175 starts preserved; density+growth ~1.87 ->1.83s. Shared stars
  decrease with removed redundant arc. Regression covers underfilled growth,
  one surviving continuation, radius separation and transverse contacts.
  The following describes the older density-only fallback retained for callers
  of trace_density without pair_fields and for shared star alignment:
  Gaussian-smoothed log-density gradient/Hessian are computed on the physical
  grid; interpolate tensors, then diagonalize. Least-curvature eigenvector
  guides where the eigenvalue gap is clear. Launch Perlin vectors are softly
  projected into low-curvature directions, including planes in sheets. Ongoing
  steering combines confidence-weighted direction, bounded transverse density
  pull, shared/offset Perlin wandering and gradual heading response. Finite
  Beta lifetimes, domain exits and tenfold density decline stop growth.
  Thin Y below direction radius/20 uses Y-averaged XZ analysis, retaining
  sampled heights. 512 strands, mean length 2, direction radius .3, pull .35,
  wandering .15 by default; base density defaults match the user's 2026-10-10
  reference. Shared star pipeline unchanged. No graph, forced connectivity,
  exact density preservation or aesthetic acceptance is implied. See README
  for equations/parameters. Two saved-density comparisons took about .7s each
  for generation plus shared sampling (excluding worker startup).
  The post-growth overlap deletion pass was rejected and is no longer called;
  its controls are retired. Growth now includes local strand joining: nearest
  eligible deposited segment within reach .6, abs tangent dot >=cos(25deg),
  excluding both halves of the same source. j=w*(neighbor_tangent-heading +
  2*transverse_offset/reach), with squared distance falloff and a travel ramp.
  Strength 1 by default; 0 restores independent growth and disables contact.
  Contact radius .08 (capped by reach) locally snaps a proposed tip onto the
  actual segment and stops that half after at least 2 steps; radius 0 retains
  steering only. KD tree refresh every 4 steps, 48 nearest midpoint candidates,
  so some eligible encounters can be missed. No curves deleted afterward, no
  receiving geometry moved, no star budget redistribution. Original seed/noise
  draws unchanged. All curves advance together; dependencies can propagate.
  Tiny-Y planar guidance retains heights except for an actual join's final snap.
  `_curve_coverage.py` adds coverage modes 0 original joining, 1 density capacity
  (default), 2 residual filling. Target curve length = strand_count*strand_length
  *capacity_scale, distributed by original density on a 48^d mass grid. Actual
  accepted segment length is trilinearly deposited, including subdivision of
  contact snaps. Equal physical Gaussian smoothing gives load C/T. Radius .5;
  capacity_scale 1. Joining activates over load .5..1; contact allowed >=.75;
  steps into load >=1 stop unless completing a join. Two initial steps and
  four-step coverage refresh allow limited overshoot; not an exact constraint.
  Mode 2 births in four waves, later roots from T*max(1-load,.001), and adds
  bounded transverse gradient(log(max(1-load,.05))) steering to fill deficits.
  No prescribed swirling/spirals: Perlin/persistence can bend paths through blobs.
  Capacity affects total length/stars; no star-budget transfer or post-growth
  deletion. Curve-length density fidelity is approximate and shared star density
  variation/taper can change the final star distribution. Synthetic bridge/blob
  and saved-noise comparisons are in build/density-coverage-comparison.png;
  filling improved measured shape fidelity but used more length than old joining.
  Saved-scene growth roughly 2.1s capacity / 4.4s filling in the initial comparison.
  Local-check optimization: bound KD queries by reach + longest half-segment;
  retain at most 48 midpoint candidates and exact distance/owner/angle checks.
  Skip steering query when load <=.5, contact query when load <.75 or before
  two steps. Coverage builds deficit gradients only for filling; proposed-step
  checks sample scalar load only. Keep four-step tree/grid refresh and existing
  random draws. On a fixed saved branch field with 512 roots, median three-run
  growth timings: off .62 -> .56s, capacity .65 -> .50s, fill 1.04 -> .85s;
  paths byte-identical before/after in all modes. Excludes noise/stars/startup.


- `guided_walk_filaments.py` / `_guided_walk.py`: latest simple one-pass
  experiment, kept separate from all earlier generators. No noise zeros,
  gradients, field pairs, prescribed blob edges, or reinforcement during growth.
  Blobs are best-candidate random points inside a ball. Random-heading walks
  start at blobs; free filaments start anywhere in that ball and grow both ways.
  Free halves are returned as one continuous polyline for shared star sampling.
  Blob count or walks per blob can be zero; some walk/free filament is required.
  h_new = unit(h + ds/persistence * (wandering*N + guide_strength*G)). N uses
  three value-only Perlin/Simplex fBm fields: 80% shared + 20% per-curve offsets,
  times a fixed factor 2. G is exactly one chosen local blob or filament guide,
  with distance falloff; never a sum. Weighted selection favors proximity and
  filament alignment. Guide hold distance prevents immediate switching; free
  walk probability holds no guide for the same interval. Source blobs and
  filaments from the same source group are excluded. Filament tangent is oriented
  into the heading hemisphere and gets a sideways correction; following does
  not stop or snap the curve. Close arrivals at another blob snap locally and
  stop. One global segment tree refreshes every 8 steps; query 24 candidates,
  deduplicate curve owners and filter alignment >cos(60deg). This search can
  miss eligible guides hidden behind many excluded candidates. All tips advance
  in batches, mitigating first-curve dominance. Step .08 units; total 160k
  candidate-step cap; all metrics before final Y compression. Shared star stage
  and independent curve/star visibility are unchanged. Default growth measured
  about 0.6 seconds for 65 exploratory filaments on two seeds. After growth,
  `_centerline_selection.py` defaults to one shortest discovered route per blob
  pair, arc/chord <=2, plus up to 4 open paths (free starts preferred). No new
  edges are added. Selected curves get 0.2-unit Gaussian arc smoothing with
  fixed endpoints before Y compression. Output mode 0 retains raw walks.
  Aesthetic quality remains experimental; star-strand work is paused pending
  centerline quality. Single-layer generators ignore dual-layer visibility
  preferences; Show curves/stars controls apply only to populated curves.

- `emergent_filaments.py` / `_emergent_network.py`: new local-interaction
  experiment. The user explicitly rejected preselected blob pairs, spanning
  trees, and fixed destination endpoints. The unfinished `relaxed_filaments.py`
  implementation of that rejected model was removed, along with its helper/tests.
  Start free finite curves at triple-noise blobs, using existing soft pair-noise
  guidance and uneven 1-2-pair launch plans; no seed-pair route allocation.
  Wandering uses independent-offset three-component Perlin/Simplex fBm here.
  Nearby aligned segments from other source blobs supply bounded attraction and
  alignment; same-source bundles cannot reward themselves. Direction signs are
  interchangeable for alignment. No forces act beyond the local radius.
  A tip within join radius can attach to another blob or an aligned deposited
  segment; it stops there. All paths start at exact seed centers. Segment trees
  refresh every eight steps, so encounter detection is approximate, not exhaustive.
  Repeated passes retain starts/randomness and use prior geometry as a local
  steering memory, weighting contacted curves 1 and unsupported curves 0.1.
  Actual joins always target the current pass, never old memory geometry.
  Receiving paths with no onward contact trim after their last incoming contact;
  unsupported curves survive with a separate probability. Contact targets are
  retained. If nothing survives, keep one exploration curve for a valid preview.
  No explicit mid-curve spawning yet; junctions arise from shared starts and local
  joins. Contacts do not guarantee global connectivity or monotonically improve
  between passes. Existing spatially separated root selection is still used.
  A total 160k candidate-step budget across passes bounds work and can truncate
  extreme settings. Shared star population/postprocessing remain unchanged.

- `_population.py`: shared optional star sampling for line generators exposing
  `generate_population_source`, returning `(line_attributes, paths, path_colors)`.
  Stochastic filaments currently provides this hook. Density is per displayed
  arc length. Normalized exp(A*f(s)) density uses genuine 1D gradient octave noise
  independently per curve, sampled by inverse CDF; it preserves each curve's
  candidate count. Each curve first gets mean density D*(1+v*(2U-1)) from a
  separate seed stream; Curve density variation v defaults to 0.5 (0 disables).
  These multipliers change counts and are separate from along-curve noise.
  Old pop_clumping/pop_clump_scale keys now control along-curve density
  variation/scale; octaves and roughness add finer noise. Stratified quantile jitter
  controls spacing, transverse Gaussian scatter uses a separate stream, and
  smoothstep tip thinning is applied afterward. Taper can still change final
  counts when density shifts into/out of the tip. Seed markers are excluded. Separate
  random streams preserve surviving attributes when size/taper/color changes.
  The worker appends a Star population panel (`pop_` reserved prefix), runs star
  postprocessing and writes `points.stars.bin` alongside the unchanged curve
  buffer. Both use FSTAR002 except block proxies' FSTAR003; only the sidecar allows zero records. The viewer
  validates both before publishing, uses separate GPU buffers, and persists
  `show_curves` / `show_stars` renderer-only toggles. Population edits regenerate
  deterministic curves; visibility edits do not queue Python jobs.

- `stochastic_filaments.py` / `_stochastic_curves.py`: smooth stochastic line
  bundles around 3-4 noise fields' pairwise zeros (default 3). Seeds are verified
  continuous triple zeros from all triple families, not only AB junctions. Each
  blob selects one or two pairs and stochastically launches unequal counts in
  each direction. Seed pairing bias defaults to 1: walk the initialization graph
  along each fixed pair to the next selected seed; no geometric links are added.
  Rank existing routes by inverse arc length with seeded jitter, admitting at
  most two pair families per blob. Facing ends share per-copy draws with
  p=.65+.3/(1+L/noise_scale), and one launch each; unpaired arms use p=.1.
  Unmatched blobs keep one sparse pair and one guaranteed launch. A lone seed
  retains legacy behavior. Bias 0 restores independent plans; intermediate bias
  mixes decisions. Global curve caps can truncate reciprocal allocations.
  Selection still maximizes seed separation, so selected blobs can have no
  common pair-zero strands in the box. No outside-box route detection or
  guarantee that finite stochastic curves reach each other is provided.
  The third pair can still appear through later branching. `curves_per_seed`
  retains its saved key but is labeled Max curves / direction (default 6): it
  caps candidates rather than forcing full arms. Increasing the cap extends the
  seeded per-blob plan. Budget allocation is round-robin across blobs, with at
  least one launch each. No ordinary-pair fallback; missing triple roots is an error.
  Direct continuous noise and
  finite-difference gradients replace grid tangents. Motion combines tangent,
  finite regularized normal attraction, independent smooth random steering,
  and gradual heading response. Multiple curves per seed remain separate and
  are never deduplicated/snapped. The exact graph initializes seeds and launch
  allocation, but does not prescribe trajectories or supply target attraction.
  Soft inter-curve repulsion defaults to 0.15 with reach 0.2 before Y compression.
  A spatial index queries nearby deposited segments, excludes self, selects one
  closest candidate per other curve, and applies bounded transverse steering
  with squared cutoff falloff. New paths ramp in over twice the reach; existing
  vertices/attachments never move. Zero restores independent trajectories;
  enabled interactions mean count/length/branch edits can affect other paths.
  Per-curve attraction is A*(1-v*U^3), with v=0.9 by default: mostly near A,
  with a smaller weak-attraction tail. Each root/child has an independent fixed
  draw; v=0 restores equal strengths.
  AttractionModulation optionally multiplies it by (1-b*dÂ²/(dÂ²+RÂ²)) and
  (1+c*tanh(3*N(x))). Both amounts default off. d is Euclidean distance from
  the original blob before Y compression, retained by descendants. Positive b
  weakens outward, negative strengthens; R is half-change distance. N is an
  independently seeded shared spatial Perlin/Simplex fBm field with its own
  scale/octaves/roughness; it adds no geometry fields/junctions. Growth and
  branch prediction use the same multipliers. Turn response length (saved `smoothness`)
  smooths ongoing heading changes, not finished geometry or branch departure.
  Soft third-field encounters branch from the parent's position but use their
  own pair tangent as the initial heading (forward-oriented). Divergence
  preference defaults to 0.8: a uniform/softmax mixture favors alternatives
  whose short deterministic probes separate from the parent continuation.
  Probes use per-curve attraction and turn response, without wandering/repulsion;
  the real child keeps those effects. Preference zero is uniform pair selection.
  Hysteresis, travel cooldown, depth/curve/length budgets prevent explosions.
  Seed-region bounds do not clip growth. Y compression happens afterward.
  Independent Beta(2,2) lifetimes taper bundle populations; mean length and
  variation bound root budgets, children use randomized fractions of remaining
  parent travel. Length edits preserve earlier path prefixes with repulsion off. Zero variation
  restores equal root lengths. Star population can additionally fade individual
  tips while retaining full source curves. 440,000 segments cap line output
  below the binary vertex limit.

- `noise_branch_curves.py` / `_branch_curves.py`: line preview tracing 2-4 scalar
  noise fields' pairwise zeros, with probabilistic branching at triple zeros.
  Perlin/OpenSimplex2S is selectable. A fixed 48-cubed tetrahedral interpolation
  gives exact shared junctions within that approximation; no proximity joins or
  prescribed seed links. AB roots grow both ways; alternative families branch
  with a per-junction/family probability and inherit remaining length. Visited
  edges are deduplicated; path/length budgets bound growth. Y compresses the whole
  result. This follows centerlines, not offset-trajectory attraction or star
  sampling. Connectivity is not guaranteed; finite-box endpoints remain.

- `grown_filaments.py`: seed-grown skeleton preview, before star population.
  Persistent tips bend through shared vector noise; optional bounded branching
  starts on parent vertices. No joining/attraction/collision handling yet.
  `PRIMITIVE = "lines"` makes the worker accept geometry-controlled endpoint pairs
  using the existing FSTAR002 buffer and `primitive` response/catalog metadata.
  The GUI hides star count/postprocessing and draws GL_LINES regardless of saved
  star display mode. Last-successful primitive survives errors with the old cloud.
  Line previews bypass shared star processors. Missing PRIMITIVE means points.

- `galaxy.py`, `filaments.py`: original procedural spiral galaxy and manually
  constructed bent links between junctions. Kept as simple references.
- `_noise.py`: compiled FastNoiseLite Perlin/fBm batches and continuous sampling
  of trilinear density grids. Avoid per-star Python loops.
- `noise_clouds.py`: exponentiated noise density.
- `noise_filaments.py`: high density near the intersection of two noise zero
  surfaces, with clump modulation. Its **Layer continuity** weakens the second
  constraint in thin Y regions; this creates sheets, not connected skeletons.
  Generic intersections can produce loops and disconnected paths, not a robust
  branching filament network. The user has already identified this limitation.
  Active direct-star experiment adds `density_low/mid/high` slope controls
  (dimensionless 0.05-3, default 1) to a continuous piecewise-linear transfer
  curve at 1/3 and 2/3 of the input peak. `_postprocess.remap_density` runs in
  `generate` after raw `build_density` and before native edge fade/sampling.
  All ones bypass exactly. High .25 flattens the top while leaving the lower
  two thirds unchanged. Lower-segment edits shift later segment heights to
  preserve continuity. Positive slopes preserve ordering/zeros. No new RNG,
  requested count unchanged; sampling renormalizes weights, colors use the
  processed density, size draws stay independent. Raw density consumers and
  other generators remain unchanged. This is value remapping, not smoothing.
- `noise_filaments_branches.py`: unions several pairwise intersections; preserved
  but visually busy. Now supports the same density remap and Strand continuity
  as `noise_filaments.py` for preset copying. Strand continuity defaults to 0
  here for backward compatibility. Connectivity and Layer continuity are now
  removed from this generator: AB, AC and BC always have equal weight, using
  exp(-(A*A+B*B)/(2*w*w)) and its two permutations. Symmetric under any A/B/C
  permutation; thin Y slices the same 3D field without constraint relaxation.
  Old saved keys are ignored by the worker and pruned on successful generation.
  Original two-field generator retains its controls for comparison.
  `layer_filaments.py`: anisotropic 3D Voronoi-edge experiment.
- `_curves.py`, `noise_filament_curves.py`: explicit tetrahedral surface-intersection
  curves, regular sampling, bundles and per-curve minimum allocations. Not the
  preferred current baseline; do not treat this as an established good solution.
- `_alignment.py`, `noise_filaments_aligned.py`: gently attract an existing noise
  cloud toward extracted guides. Layer-aware guides are heuristic. Open endpoints
  deliberately do not attract stars beyond their ends, preventing endpoint piles.
- `zeldovich.py`: earlier direct-star baseline, retained for comparison. Smoothed Gaussian initial density on a 96Â³
  periodic grid; FFT displacement with divergence(s) = -density; x = q + D*s(q).
  One-shot approximation, not a gravity simulation or convergence iteration.
  Beyond crossings, stars pass through concentrations rather than binding.
  Y scale compresses the entire result (unlike thin-region sampling in noise
  generators). Colors reflect final concentration; per-star sizes use a separate RNG.
  **Void threshold** applies rhoÂ²/(rhoÂ²+thresholdÂ²) as a bounded multiplier before
  resampling. It replaced a density power that overpopulated peaks. Zero bypasses
  resampling exactly. A 64Â³ estimate and at least 262,144 pilot particles are used.

## Shared appearance experiments

The direct two/three-field generators now use `_axis_controls.py`: independent
XZ half-extent (saved `extent`, default 6, range 1-30 units) and `y_extent`
(default 6, range 0-30), plus `fade_xz`/`fade_y` toggles and independent
`fade_*_width` (fraction of respective half-extent) and
`fade_*_density_strength`. Stronger axis attenuation wins, preserving old box
fade when axis settings match; collapsed Y skips Y fade. Worker honors native
schema group/toggle/enabled_if and NATIVE_AXIS_FADE skips the old shared fade
controls. Generator migrate_parameters copies old fade values to both groups
and computes y_extent=extent*y_scale only when new keys are absent, before
schema validation. No external config edit/restart required. Requested count
is unchanged before merging. Physical height no longer scales with XZ extent;
noise frequency remains defined across XZ, so wavelength still follows XZ
extent. Older aligned/extracted-curve comparisons use
`noise_filaments.LEGACY_PARAMETERS` and keep their previous controls;
density_filament_curves now shares the branch schema/helpers instead.
Legacy direct Python calls remain supported.

The two direct noise-filament generators now expose
`generate_density_source(count, seed, **params) -> (attributes, density, half_extents)`.
The worker uses it only for enabled density alignment, passing the remapped,
pre-fade field through shared postprocessing; ordinary `generate` still returns
the original three arrays. `_density_alignment.py` uses `DensityShape` physical
log-density derivatives to take bounded transverse Newton steps toward ridges,
with eigenvalue-gap confidence, uphill backtracking, box bounds, and a 32-step
cap. Direction comes from the field even for one star. Merge runs first and only
unmerged originals move, retaining the original sparse cutoff and its feather.
No count/color/size changes or new randomness. This narrows faint strands but
cannot add stars in empty gaps. Tiny Y uses the existing XZ fallback, retaining
heights. `pp_curves`, strength, sparse fraction and reach are retained; reach is
now labeled Maximum alignment travel for these generators. `pp_density_radius`
is Field smoothing, Gaussian sigma in world units (default .25, range .02-3).
Guide length/colors are omitted from their schemas. Other generators retain
the older sample-based alignment below. Saved-scene comparison in
`build/density-alignment-comparison.png`: 15,963 stars, 9,862 moved, .42s for merge
and alignment excluding startup. Synthetic faint-tube/ring, singleton, movement
bound and worker checks added; visual acceptance remains with the user.

`generators/_appearance.py` owns the shared schemas and operations. All three
experiments default off. Settings may enable them in the user's saved preset.

1. Sparse curves: identify sparse stars by eighth-neighbor distance, choose random
   spatially separated anchors, use local PCA directions to build sinusoidal
   guides, and attract nearby sparse stars with smooth falloff. Optional guide
   colors do not change positions. No guarantee of connectivity or uniform filling.
   Now runs after merging on unmerged originals only. Recompute their neighbor
   spacing/PCA without merged stars, retaining the pre-merge sparse quantile
   cutoff so newly sparse remnants qualify. Merged centers/colors stay fixed.
2. Merge dense stars: randomly oriented bounded bins combine nearby dense stars.
   Use volume-weighted centroids/colors and cube-root summed size-cubed. This
   preserves star volume at Merged size boost 1 and avoids transitive merging of
   whole filaments. `pp_merge_size_boost` defaults to 2 (range 1-8), multiplying
   merged diameters only; no randomness, membership, count or centroid changes.
   Base sizes above 1000 reject merging; visual boost saturates at 1000.
3. Warp: mode 0 is a global swirl about world Y, theta = angle/(1+(r/radius)Â²),
   preserving height and horizontal radius. Mode 1 retains the earlier sum of
   transverse sine waves. Swirl bends structures; it does not attract stars onto
   spiral ridges. All stars participate, with no motion on the rotation axis.

Order: merge, residual sparse alignment, warp, point-stage fade. Warp intentionally runs
after guide assignment/merging: the previous order regenerated guides and colors
when warp changed, making even small changes look like an entirely new pattern.

`generators/_postprocess.py` contains common density functions and edge fading:

- Rectangular fade uses max(abs(normalized position)), not a radial sphere.
  Fade width defaults to 0.8 of each half-extent; bigger means a broader taper.
- **Edge clump suppression** defaults to 1 (0 restores positional fading).
  Corrected to compress only density above T=.25*peak, not relative to the box
  mean. For r=rho/T, q=max(r-1,0), output=T*e*(min(r,1)+q/(1+s*(1-e)*q)).
  Sub-threshold density receives exactly ordinary positional fading, independent
  of suppression strength; full interior is unchanged. Smooth monotone shoulder.
  Empty volume cannot lower T, though a dominant peak can raise it. No new
  control. Point-stage fallback uses .25*max(estimated density at stars).
  Native samplers still renormalize fixed count, so individual positions can
  change; point-stage sparse survivors remain identical for strength-only edits.
  Saved-field check at strength 4: old formula removed another 40% of low-density
  weight after ordinary fade; new formula removes none. Visual acceptance pending.
- Native density generators apply fade before sampling and retain requested count.
  Others use deterministic survival sampling and output fewer stars. For these,
  density is estimated on a smoothed 48-cell grid per active axis, without periodic
  wrapping. Opposite edges do not contribute to one another's density estimates.
- Optional `postprocess_bounds(**params)` returns `(center, half_extents)`; otherwise
  use the generated cloud's bounding box. Known box generators provide the hook.
- Shared stages do not extend filaments or generate graceful new branches beyond
  a finite box. Dense structures abruptly intersecting boundaries remain an open
  artistic problem; the user is free to choose a different construction entirely.

## Settings and local tools

`config/plot.json` and `config/controls.ini` are intentionally tracked. The C++
viewer saves changes automatically (350 ms debounce, bounded 2-second interval
during continuous edits, exit flush), using atomic file replacement. These files
are live user data: don't casually overwrite them with test defaults or revert
their changes. Python scripts never edit themselves. Earlier AppData settings
are obsolete. Actual config/source paths are recorded in the generated build header.

PowerShell commands from the repository root:

```powershell
# Existing configured build; does not launch the app.
& ./.tools/cmake-3.31.6-windows-x86_64/bin/cmake.exe --build build/Release --parallel 4

# All CPU-only checks, including Python; no viewer window.
& ./.tools/cmake-3.31.6-windows-x86_64/bin/ctest.exe --test-dir build/Release -E 'renderer_smoke|point_perspective' --output-on-failure

# Python-only checks.
& C:/Users/colin/miniconda3/envs/py310/python.exe -B tests/test_generators.py
```

Current interpreter: Python 3.10.11, NumPy 1.24.3, SciPy 1.10.1. The compiled noise
wheel is project-local in `.tools/noise-python` (pyfastnoiselite 0.0.7); don't
assume a global import works without the project's path setup. Compiler and Ninja
are also under `.tools/`. See README/bootstrap scripts for a new machine.

`scripts/build.ps1 -Run` launches the app, and `-Test` includes hidden GPU windows.
Use the CPU-only commands above when respecting the no-launch preference.

## Handoff checkpoint (2026-10-10)

The final dynamic GUI-section build was initially blocked by a running EXE; the
viewer has since closed and the final executable was successfully linked during
this checkpoint. No app was launched. There is no outstanding build-lock issue.
The latest Python suite has 25 tests; these cover determinism, schema/protocol,
flow ordering, volume-conserving merges, geometry, and density-aware edge fade.
Visual quality still needs the user's judgment. Tests do not establish that an
experiment looks good. All current approaches and the user's saved settings are
being retained so the next direction can be compared against this baseline.
