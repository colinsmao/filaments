# Filaments

A native C++17 / OpenGL 3.3 star-distribution viewer with live Python/NumPy generators.
Windows runs directly against the installed graphics driver; WSL is not required.

For development context and workflow preferences, read [AGENTS.md](AGENTS.md).
Its core reporting instruction is mandatory: always explain what was actually
done, starting with the baseline, concrete changes and their purpose, then the
observed result and remaining failures. Trial names and linked evidence do not
replace that explanation. Identify the exact candidate shown in each comparison.
For visual iterations, read the cumulative [matching requirements](reference-match-requirements.json).
Every candidate must be reviewed against all existing requirements, and newly
discovered differences added without dropping earlier requirements.
The durable [current review](reference-match-review.json) contains all nine
candidate assessments and evidence hashes. **All nine fail overall.** Run
`python scripts/review_scaffold_stars.py --check` to check requirement coverage,
evidence freshness and candidate inventory; this does not measure visual quality.
New generations start with every criterion marked unreviewed, including when a
candidate name is reused.

## Stars on the unguided scaffold (experiment)

**Work stopped after the final failed attempt on October 14.** The user required
the requested screenshot match or a clear admission of inability and stopping.
Starting from `bending-42`, a four-block exclusion around other paths for new
fork births reduced forks493->408 and occupied cells5068->4821. A separate render
comparison replaced solid candle-group proxies with narrow uneven-height boxes,
keeping occupied cells and lighting fixed. Close, wide, whole and oblique views
still show repetitive strings, crowded groups and the wrong patch/connection
structure. The assistant could not deliver the match. Temporary generator edits
from this final attempt were restored; previous work and settings remain intact.
Evidence: [final comparison and review](build/final-scaffold-attempt/review.json).
Historical experiments and untested suggestions below are preserved as context,
not an active work plan. No further trial is pending.

**Current verdict: the user rejected the first presented population match.**
It forms an unresolved blob in the close comparison, has far too many full
blocks in the wide comparison, and shows excessive right-angle paths. The
implementation and historical trials below are preserved, not accepted defaults
for screenshot fidelity. Current correction trials also remain diagnostic until
they meet the full cumulative requirements, including dense patches and thin
connections as well as resolved curves.

The trial named `gentler-42` bundled several changes; the name did not describe
them adequately. Starting from the rejected seed42 scaffold, maximum heading
change went50 to20 degrees, requested mean axis hold2 to1 block step, mean fork
opportunity interval12 to24 steps, child lifetime fraction.65 to.4, and nominal
two-way trunk allowance120 to180 steps. Heading changes still occurred after
roughly8 steps, with their original interval randomness. Actual positions remained
integer face-neighbor cells, and branch departure angles were unchanged. The trial
also used the placement correction: expected population1.1 to.65 per path block,
XZ/Y scatter.35/.2 to.1/.08 blocks, along-path variation1.5 to.5, and luminous-block
fraction.006 to.0006. These changes produced straighter, more separated strings
but lost dense patches. Because several controls changed together, this result
cannot be attributed to the smaller turn limit alone.

The images in the subsequent review show `bending-42`, a different trial. It uses
the same placement correction, axis hold1, maximum heading turn25 degrees and
turn continuation.9, while retaining the original fork interval12, child fraction
.65 and trunk allowance120. Turn continuation biases successive heading changes
toward continuing the previous bend. That produced some broader bends, but still
failed the dense-region/connection requirements. These are diagnostic trials;
neither changed the user's saved preset.

The correction trials preserve the original camera views and also use a common
close camera at distance55 (previous75). Two clearly identifiable reference cubes
measure approximately20-28 pixels in the comparison; a native cube at the original
target depth measured17x19, versus about23x26 at the revised distance. This corrects
an apparent-size discrepancy, but does not recover the unknown reference camera
or establish physical density. Evidence: `build/scaffold-stars/correction/`,
including `apparent-size-check.json`, `reference-size-probes.png`, and
`reference-bending-42-scale55.png`. No exposure adjustment is applied.

Four optional growth controls are exposed only on the populated experiment; all
default to zero and preserve the previous scaffold when disabled:

| Diagnostic control | Meaning and effect |
| --- | --- |
| Turn continuation | Dimensionless0-1 probability bias toward continuing the previous turn plane. Changes integer slope choices, geometry and star count; no spatial guidance. Zero keeps independent turns. |
| Maximum child lifetime | Cap in block steps after the existing child-lifetime draw. Zero disables. Longer trunks need not make every child longer. Changes geometry and count. |
| Mean branching period | Local tip travel in blocks with fork opportunities, before a quiet span. Each span draws0.5-1.5 times the mean, with a two-step minimum. |
| Mean quiet period | Local travel without new forks. Existing tips continue. Either period set to zero restores continuous branching exactly. Both controls change geometry/count; no patch positions or destinations are prescribed. |

Turn continuation produces some broader bends, but repeated bead rows and crowded
branch groups remain. Active/quiet trials still form clumps because new children
start active and add descendants nearby. A trial with five full blocks in the wide
frame still fails the curve/patch requirements. None of these settings is promoted.
Endpoint/boundary crops, additional seed checks and broader scale calibration remain
explicit review gaps. Fifteen focused tests pass; tests establish mechanics only.

Select **Stars on unguided block scaffold** / `block_scaffold_stars.py`. The user
authorized this next stage on October 14, after the scaffold-only work. It reuses
the existing integer graph and exposes stars and curves as separate layers. The
scaffold-only script and all density-first experiments remain available.

The first population baseline used the existing whole-branch material lottery,
.9 expected stars per block of path, .2/.1-block transverse spreads, .35 variation
between paths, and no tip taper or along-path variation. The branch material
lottery produced luminous-block chains and sparse rod-only branches. The new
**Mix materials within branches** mode instead populates every path with candle
mass, then uses a cell-keyed draw to assign rods and luminous blocks. Material
fractions change shapes, colors and light sources without changing occupied
cells. Candle tint remains coherent along each source path. This mode is opt-in
inside the shared sampler; existing generators keep their prior behavior.

The selected defaults use 1.1 expected stars per block of path, transverse spread
.35 XZ/.2 Y blocks, curve variation .35, along-path variation 1.5 at scale12 blocks,
and zero tip taper. Rods occupy 7.5% and luminous blocks .6% of selected cells in
expectation; the remainder are candles. The whole-branch material weights and
rod/block density multipliers apply only when mixed materials are off. Population
is sampled into unique unit cells with the existing integrated-mass sampler.
All graph paths and extra contact edges are eligible; failed zero-length branches
are excluded. There is no upstream density field, guide or star selection stage.
Lighting uses the existing formula with this script's sky .1/ambient .02/lift1.

The finished screenshots were checked for coherent dotted bends and forks,
irregular spacing/thickness, dense patches, thinner connecting filaments, dark
voids, and the faint-candle/bright-rod hierarchy. **This is not yet a screenshot
match.** Placement produces readable strands and patch/void structure, but the
strings remain too regular, the generated patches do not reproduce the reference
hierarchy, and some inter-patch gaps have no scaffold route. More population
cannot create a coherent route there. Five unchanged scaffolds retain 9–16
components; this is a generator measurement, not the unknown reference component
count. Increasing trunk length120 to180 on seed42 reduced components15 to8;
also increasing the root cell cap600 to1200 reduced them to3, but broadened dense
growth substantially. Those structural variants are saved, not adopted defaults.
The next structural test should separate the allowance for continuing trunks
from local branching bursts, so reaching farther does not automatically enlarge
every patch. That can still be an unguided, local block-growth experiment.

Close-ups also reveal a renderer limitation: candle groups are represented by
solid cuboids. Individual candle meshes, textures, luminous-block glow, dark
decorative blocks and planets are absent. Population parameters cannot reproduce
those silhouettes; a material-rendering pass is needed separately from growth.
Reference cameras and world coordinates are not recovered. Model cameras are
fixed across seeds, and comparison crops/resizes are recorded; no physical
reference-density measurement or pixel-equivalent match is claimed.

`scripts/evaluate_scaffold_stars.py` provides `baseline`, `sweep`, `materials`,
`refine`, `verify`, `compare` and `audit` stages. Evidence is under
`build/scaffold-stars/`: `reference-close-comparison.png`,
`reference-wide-comparison.png`, `five-seed-whole-canopies.png`, frozen requests,
native buffers, graphs, source snapshots and `assessment.json`. All eight frozen
graph arrays match the earlier scaffold results across five seeds. Selected
populations contain 7,967–9,120 occupied cells. The ordinary probe budget is
reached; an unconstrained requested-probe check on two seeds changes counts by
less than .1%, but changes .4–2.4% of occupied cells. This checks sensitivity,
not exact per-cell convergence. All 184 Python tests and native panel startup
pass. No visible viewer launch/rebuild, live preset edits or commit.

## Unguided block scaffold (geometry only)

Select **Unguided block scaffold (no stars)** / `block_scaffold.py` and use
**Fit cloud**. This separate experiment stops at curves and branches. It has no
population callback, star layer, density input or spatial guidance field. The
existing experiments and saved presets are preserved. The viewer renders graph
links, or diagnostic wire unit cells using **Wire block cells**. Branch colors,
red root markers and yellow junction markers change only the preview.

`_block_scaffold.py` grows an integer graph using six face neighbors. An integer
slope specifies proportions of X/Y/Z face steps during each run; accumulated
step deficits choose their order. No continuous curve is generated or rounded.
The chosen axis is held for a geometrically drawn number of steps with requested
mean **2 blocks**. Half the requested holds are one block; longer holds let a
path make sustained horizontal and vertical runs as well as stairs. Heading
changes, launch steps and blocked moves can shorten a hold. Deficits accumulate
through holds, and a separate random stream keeps **Mean axis run = 1** exactly
equivalent to the original single-step implementation.
If a step is blocked, other signed steps of the same slope are tried. Local
random heading changes, finite tip lifetimes and forks build the geometry.
**Vertical direction weight** is a constant statistical preference for flatter
headings, not a spatial field or a compression of the finished geometry.

Each uniformly placed root starts two opposed tips. A branch shares a parent
cell and departs for two or three face steps before ordinary run stepping.
All descendants spend the same root cell allowance; it is a cap, not a target.
Child lifetimes are a randomized fraction of the parent's initial lifetime.
Actual cell contacts either join explicitly and stop that tip, or are refused.
Every face adjacency between diagnostic scaffold cells is represented in the
graph. Joins that would create cycles shorter than ten edges are refused,
including cycles between multiple simultaneous contacts. This is a local design
rule, not a measurement of the reference. Separate components can remain.

| Control | Meaning / initial default |
| --- | --- |
| XZ / Y size | Full domain dimensions, 275 by 55 by 275 blocks. Outside steps are refused. |
| Roots | 24 uniform random roots in the inner 70% of each axis, with a two-cell exclusion; a single root starts at the origin. |
| Cell cap per root | 600 distinct cells shared by both tips and all descendants. The total allowance may not exceed 40,000 cells. |
| Mean two-way trunk length | 120 face steps, multiplied by a 0.7–1.3 draw per root, then divided between its tips. |
| Mean heading run | 8 face steps between heading changes, with a 0.5–1.5 draw. |
| Mean axis run | 2 blocks requested per held face axis, geometrically distributed. Turns and contacts can shorten holds. One restores the original scheduler exactly. Changes geometry and scaffold count; no star stage. |
| Maximum heading turn | 50 degrees; draws use 45–100% of the limit. A very small cone may contain no alternative integer slope. |
| Mean fork opportunity gap | 12 steps, with a 0.5–1.5 draw. Blocked attempts can fail without a new branch. |
| Child lifetime fraction | .65, times a 0.65–1.25 draw, times the parent's initial lifetime. |
| Vertical direction weight | .35; larger permits steeper headings. |
| Allow local contacts | On. Off stops before contacting another path; recent self/parent contacts are refused either way. |

All growth controls can change geometry and scaffold cell count. The generic
star-count input has no effect, and this script exposes no star controls. The
nominal allowances are intentionally explicit: exhausted caps can truncate live
tips, and denied contacts can end branches. Boundary avoidance can also bias
paths along a domain face. No complete coverage or global connection is promised.

`scripts/evaluate_block_scaffold.py` freezes graphs, parameters, source hashes,
stop reasons and cameras, and renders through the existing hidden native
`build/check_lighting.exe` diagnostic. Its binary cube/link records are diagnostic
scaffold geometry; they do not invoke star population. It never edits the viewer
preset or launches the visible application. Use `--phase first`, `variants` or
`verify`; current evidence is in `build/block-scaffold/final/`. The variant views
share fixed cameras; seed sheets fit individual bounds. Reference comparisons
are qualitative, not a recovered camera/geometry match.

The initial five-seed trial had almost no vertical axis runs of four or more
blocks (0–2 per canopy), despite sustained vertical sections in the construction
reference. Comparing mean axis runs 1/2/3/4 with uniform and geometric draws
selected the moderate geometric mean 2. The revised five seeds produce
10,787–12,431 scaffold cells, 9–16 components, 63–83 independent graph cycles
and 78–109 vertical runs of four or more blocks. All five original graphs are
exactly recoverable with axis run 1. The 180 Python tests and native panel
startup check pass.

`scripts/assess_block_scaffold.py` freezes the comparison and exposes `sweep`,
`verify` and `compare` phases. Latest evidence is in
`build/block-scaffold/assessment/selected/`, including `reference-before-after.png`,
`reference-five-seeds.png`, source hashes, crops, cameras and graph measurements.
Before/after local cameras are identical; apparent block size is approximately
matched to one reference region (about 24 pixels). This is not recovered camera
calibration or a quantitative whole-scene density match. Full-scene seed views
share a fixed camera, with no per-seed fitting or omission of gaps.

The assessment supports keeping this as a working unguided scaffold baseline:
the local shape family of runs, bends, forks and loops resembles the construction
reference. Staircases, gaps and disconnected components alone are not evidence
of failure; the reference also contains gaps and stairs, and its 3D connectivity
cannot be read reliably from projected overlaps. Exact scene layout is not
reconstructed. Root budgets still truncate some tips; no coverage or global
connectivity guarantee is made. **Star population remains outside this stage.**

## Incremental candle / rod selection (experiment)

Select **Incremental candle / rod curve selection** (`density_population_selection.py`)
in the generator list. Its **Curve selection** section has the selection controls,
hover explanations, and candidate/candle/rod curve counts. Toggle **Apply incremental
selection** off to populate the same entire candidate pool as candles. Curves and
stars retain their independent visibility controls; selected rod curves are gold
in the line preview. The selection section, tooltips and shared-field UI registration
require the rebuilt viewer. Later Python changes reload normally.

This keeps the existing organic density-guided growth, with joining disabled,
then chooses whole curves. It shares `generator.density_field` with the other
density scripts. The October 12 tuning targets `scar/Screenshot 2026-10-10 232941.png`
and `scar/vlcsnap-2026-10-10-23h47m08s611.png`: coherent narrow strings, short strands
within patches, visible rods and dimmer unlit candles. It retains the shared field
and adds a **short/long candidate mixture** using the same density-guided growth.
Each root gets one length class from a stable hash; both classes use the same
length variation. Separate growth batches avoid storing long histories for short
curves. The existing population selector chooses whole curves from the combined
pool; there is no new overlap score, cutting or joining rule.
The subsequent isolation trial adds a soft candle proximity penalty to selection,
without changing the candidate geometry or population sampler.

The October 13 **saved trial preset** uses the estimated build size of 200–350
blocks wide and 40–70 tall. Its domain is **275 × 55 × 275 blocks** (XZ half-extent
137.5, Y half-extent 27.5). It uses a 24-block density wavelength, support width
.045 and grid resolution 64. These are shared upstream field settings, so they
also affect the other density consumers. Other scripts' local presets stay intact.

| Saved preset control | Value | Reason |
| --- | ---: | --- |
| Candidate seeds per million blocks | 450 | About 900–1,000 candidates at this smaller physical volume, below the 2,048 guard. |
| Seed XZ / lower and upper Y reaches | .86 / .65 / .65 | Spread roots through the canopy; Y roots span 35.75 blocks around its center. |
| Seed density power | .8 | Favor filaments without restricting births to their sharpest peaks. |
| Short fraction / mean short / mean long length | .8 / 12 / 48 blocks | Short groups dominate; long candidates provide connecting strings. |
| Length variation | .7 | Uneven lengths without the longest tails of variation 1. |
| Long response / pull / wandering | 3 / .4 / .12 | Follow the smaller field features. |
| Short response / wandering | 2 / .65 | Short turns remain organic without excessive looping. |
| Population density / source influence / curve variation | .85 / .4 / .35 | Fill narrow curves with uneven local intensity. |
| XZ / Y star spread | .2 / .1 blocks | Preserve coherent individual strings. |
| Selection budget / density contrast / overlap scale | 4 / .5 / 5 blocks | Permit neighboring short groups while comparing local population mass. |
| Isolation penalty / distance / new patches | .5 / 5 blocks / on | Discourage floaters while permitting separate nearby groups to establish. |
| Rod intensity / attraction / repulsion | .2 / 1 / 5 | Keep rods visible; their proximity scale remains 12 blocks. |
| Short-curve rod penalty | .75 | Keep most useful shorts available for candles. |
| XZ / each Y edge fade | .12 / .2 | Soften the domain boundary; extra density suppression is zero. |

After application, the user adjusted the saved population density to **.6** and
per-curve density variation to **.95**. The checkpoint preserves these latest values;
the table and rendered trial measurements describe the preceding .85/.35 settings.

The remaining lighting values stay at ambient .02, sky .10 and lift 1. No new
selection, growth, lighting or planet logic was added for this tuning. Python
fallback defaults below remain unchanged; the tuned values belong to the saved
viewer preset.

Compared 13 tuned variants plus the starting preset using the two references,
native close-below and oblique renders, and a distant whole-canopy view. Wider
density support and shorter wavelength reduced the long ribbon appearance.
Raising seed rate to 600 cost more for little visual gain; broad density strength
2 concentrated the result too strongly; a smaller 350-rate pool lost visible rods.
The selected current seed retains 697 candle curves (566 short) and 150 rod curves,
producing **7,466 candle objects and 722 rods** versus 1,550 and 147 before tuning.
Its occupied bounds are 267 × 52 × 252 blocks, inside the 275 × 55 × 275 domain.

Five seeds produced 7,394–8,188 objects from 894–972 candidates, without hitting
the population integration cap. Selected candle sketches retained 96.2–99.2% of
16-block XZ bins containing more than one expected candidate candle; this measures
retention of candidate-supported regions, not the fraction of world volume filled.
Fresh Python generation took 5.7–6.3 seconds and cached selection 35–48 ms in that
check. The user disputed the visible density match: this trial is not an accepted
reproduction. Camera/block-size calibration and a measured screenshot density target
were missing. The starting scene's actual bounds were already 268 × 53 × 252, so
the comparison does not demonstrate a major physical scale correction. The references'
planets, scenery and detailed candle meshes remain absent; regular strings remain
visible in places. A same-geometry full-white diagnostic (`render-audit.png`) retains
the gaps and strings; lighting alone does not explain the distribution mismatch.

Evidence is in `build/final-scale-tuning/`: `selected-preset.json`,
`reference-comparison.png`, `chosen-whole.png`, `verification.json`, frozen requests,
renders and the local sweep scripts. Cameras in those files are explicit diagnostic
views; the latest saved viewer camera settings are preserved. Applied after the user
closed the viewer, with backup `plot-before-apply.json`. Regeneration from the saved
configuration reproduces the comparison's curve and star buffers byte-for-byte;
`applied-validation.json` records verification. No viewer launch or rebuild was needed.

Python defaults use seed rate **96**, **75% short candidates** averaging **24
blocks**, and **120-block** long candidates. Length variation is .6; growth
response 8.276 blocks and wandering .15 for longs; short response **2 blocks** and
wandering **.8**. Density attraction .35 remains shared. Seed density power
is 1. Narrow transverse spread (.2 XZ/.1 Y blocks) is paired with **.9 expected
stars per block of arc** to avoid making thin strings empty. Per-curve intensity
variation is .25, original-density influence .35, and rod intensity .2.
This experiment's lighting defaults are ambient **.02**, sky **.10**, brightness
lift **1**. The shared lighting formula and material palette are unchanged;
lavender candle colors still exist, but low-light candles are darker. Other
experiments retain their settings and accepted lighting baseline. Existing saved
presets are not overwritten by Python defaults. Material lottery weights/full-block
curves are omitted here because the selector assigns candle and rod roles directly.

Each candidate gets a small deterministic sample of its expected star population,
including source-density variation, along-curve noise, per-curve intensity variation,
transverse scatter, taper, warp and an approximate edge survival envelope. These
weighted samples are deposited smoothly on a coarse grid. A long shared stretch
accumulates more overlap than a brief crossing; larger star mass contributes more.
This is neither a binary intersection test nor a count of nearby centerlines.

The incremental loop starts empty. A candle candidate is scored by how much its
expected population improves the density fit, divided by its expected star mass.
After the first candle curve, add an isolation penalty based on the nearest
positive-mass population sample on any already selected candle curve. Choose the
best negative score, update its neighbors, and repeat. Rod candidates
instead receive a reward near selected candles and a penalty near other rods.
The two roles compete in the same loop; each curve can receive at most one role.
When neither role has a beneficial individual candidate, **Allow new candle
patches** tests nearby pairs of remaining candle candidates together. A pair
must improve the joint score, including mutual overlap and isolation, to start
another patch; ordinary selection then resumes. Stop when neither an individual
nor an eligible pair is beneficial. No lighting propagation is
computed during selection; the existing shared lighting pass runs after sampling.

| Control | Default | Meaning and effect |
| --- | ---: | --- |
| Candidate seeds per million blocks | 96 | Mean roots per million blocks in the seed region. More gives more candidate choices and more work. Increasing only this value preserves existing root locations, but selection and final counts can change. |
| Mean long curve length | 120 blocks | Mean growth budget for the long class, before length variation and domain clipping. Longer paths connect farther but tie useful and redundant stretches together. Changes geometry and counts. |
| Short candidate fraction | .75 | Dimensionless fraction of roots assigned the short length by a stable hash. Increasing it converts a nested subset to short candidates; roots stay fixed, but geometry, selection and star counts change. 0 restores a single length class. |
| Mean short curve length | 24 blocks | Mean total arc budget for the short class, with the same variation and clipping as long curves. Changes geometry/counts, without changing root positions or the class lottery. |
| Short response length | 2 blocks | Short candidates' density smoothing, heading response and integration scale. Smaller turns sooner and costs more steps; noise wavelength is four times this value. Changes short geometry and selection/counts, without resampling roots or changing length budgets. |
| Short wandering strength | .8 | Dimensionless amplitude of the existing coherent two-octave noise for shorts. Higher bends more; 0 keeps only density steering. Same seeded noise, no star scatter changes. Changes geometry and selection/counts. Long response/wandering controls now explicitly apply only to longs. |
| Apply incremental selection | On | Off retains all candidates as candles, for comparison. Changes counts. |
| Density budget multiplier | 5 | Dimensionless amplitude of the desired population. Raise it to usually keep more candle curves/stars; lower it to thin them. It is not a curve-count quota. |
| Density contrast | 0.5 | Exponent on normalized upstream density in the selection target. Higher concentrates retained population into denser areas; 0 makes the target uniform and permits more sparse excursions. Changes selection and counts. |
| Candle overlap scale | 8 blocks | Spacing of the population comparison grid. Shared grid support extends up to twice this spacing per axis, with smoothly varying weight. Larger values compare a broader neighborhood and lose fine detail. Also changes the target's spatial scale, so counts need not vary monotonically. |
| Candle isolation penalty | .9 | Dimensionless maximum extra candle score. Higher discourages floating segments; 0 disables isolation. The first candle curve is exempt. With patch restarts off, strong settings can leave only one cluster. Changes selection/counts without adding random draws. |
| Isolation distance | 8 blocks | Scale of the shortest distance between candidate population samples and selected candle samples. Larger allows wider gaps. At this distance the penalty is 63% of its maximum; one close approach is enough. Changes selection/counts, not candidate geometry. |
| Allow new candle patches | On | When selection would stop, test two nearby unused candle candidates together. They can support each other, but pay their combined density and overlap cost. Off restores the old stopping rule. Changes selection/counts, not roots, geometry, scatter or random draws. No effect with isolation zero. |
| Select rod curves | On | Enables the second role. Requires block population and material proxies. Off selects candles only. |
| Rod proximity scale | 12 blocks | Grid spacing for both rod/candle attraction and rod/rod repulsion. Larger values let more distant populations interact; changes rod choices and possibly candle choices. It is not an exact light radius. |
| Rod attraction to candles | 0.75 | Dimensionless proximity reward. Higher generally selects more rods, and may reserve candidates that would otherwise become candles. Zero selects no rods. |
| Rod repulsion from rods | 5 | Dimensionless redundancy penalty, including the candidate's own population footprint. Higher generally retains fewer rod curves. |
| Short-curve rod penalty | .5 | Dimensionless extra rod score, after mass normalization, for the short class only. Higher reserves more shorts for candle density filling; 0 restores equal rod rules for both classes. Still permits useful short rods, and does not force unwanted candles. Changes roles/counts, not geometry or random draws. |
| Rod density multiplier (Star population) | 0.2 | Rod intensity relative to candle intensity along the same path. Higher puts more rods on each chosen rod curve, but can cause the selector to choose fewer rod curves. It does not alter scatter. |
| Population samples per curve | 128 | Integration quality, rounded up to a power of two, from 32 to 512. More resolves the population footprint better at greater cost; selection and counts may shift. Samples are not rendered objects. |
| Along-curve population density | .9 stars/block | Base expected intensity before source density, curve variation, material ratio and cell occupancy. Higher fills each curve more closely; selection and final counts can change. Does not widen scatter. |
| Transverse spread XZ / Y | .2 / .1 blocks | Gaussian standard-deviation scales perpendicular to the curve. Smaller values keep each string coherent. Random draws stay the same; occupied cells and final counts can change. |
| Night sky illumination | .10 | Dimensionless uniform sky contribution. Lower darkens candles with little local rod light. No random draws or count changes. |
| Ambient brightness | .02 | Dimensionless neutral ambient contribution. Raise to brighten all materials, especially shadows. No random draws or count changes. |

The score controls add no random draws. Root hashes and per-curve population
identities are stable. **Original density influence** in Star population remains
separate from **Density contrast**: the former changes where stars lie on each
candidate, while the latter changes what distribution the selector wants to keep.
Population profiles are normalized over the candidate pool and reused after
selection; rejecting a curve therefore does not renormalize every survivor.
Crossing-cell occupancy, a changed material role, final fades and lighting can
still change surviving objects and their appearance.

For the math, let `q_i[x]` be candidate i's expected candle mass at comparison node
x, `M[x]` the selected candle mass, `rho[x]` the normalized upstream density,
`lambda` the base stars per block, and `h` the candle grid spacing. The target is
`T[x] = lambda * h * budget * rho[x]^contrast`, with weight
`W[x] = 1 / (T[x] + .02 * lambda * h * budget)`. Candle score is the change in
`0.5 * sum(W * (M-T)^2)`, divided by candidate mass. Initially it is
`(0.5 * sum(W*q_i*q_i) - sum(W*q_i*T)) / mass_i`; accepting candle j adds
`sum(W*q_i*q_j) / mass_i` to neighboring candle scores. Thus a star contributes
less crowding penalty where the target is high.

Isolation adds `w * (1 - exp(-(d/r)^2))` to that **already mass-normalized**
candle score, where w is the isolation strength, r its distance scale, and d the
minimum Euclidean distance between the candidate's positive-weight population
samples and those of any selected candle curve. The initial candle selection
uses the original score. Rods do not provide candle attachment, and their scoring
is unchanged. Nearby contacts do not accumulate: keep only the closest one. The
existing density and overlap scores can still justify a new isolated cluster or
reject a redundant nearby route. This is a selection heuristic, not a new global
energy optimum or a guarantee of connected final stars. In particular, a sparse
sampled tail can suggest proximity even when final occupancy leaves a visible gap.

Closest-sample affinities are cached separately from population sketches.
Bounding boxes reject distant pairs; batched nearest-neighbor queries calculate
the rest without constructing all sample pairs. Affinity beyond `4*r` is treated
as zero (omitted affinity at most `exp(-16)`, about 1.13e-7). Zero-weight samples
and self contacts are excluded. Each accepted candle updates only its nearby
candidates using a maximum, and changing strength reuses the cached distances.
Both strength zero and selection off bypass distance construction entirely.

The October 13 correction addresses a failure of the original isolation rule:
the normalized density benefit of an individual candidate is less than 1, so
an isolation penalty near 1 can prevent every distant patch from starting. Only
the first selected cluster grows; sometimes the entire result was one short curve.
Lowering the penalty reduced this failure but also restored more floating shorts.
Applying isolation only to shorts restored broad coverage, but retained the failure
for all-short pools. Pair restarts preserve the same isolation rule for both classes.

If single-candidate selection stalls, consider unused pairs already in the cached
proximity graph. Let `D_i` be the current unnormalized candle density-error change,
`K_ij = sum(W*q_i*q_j)`, `m_i` the candidate mass, and `a_ij` their closest-sample
affinity. For each member use `I_i = w*(1-max(existing_affinity_i, a_ij))`. Score
the pair as `(D_i + D_j + K_ij + m_i*I_i + m_j*I_j)/(m_i+m_j)`.
The best negative pair is admitted atomically as two candle curves. There is
one mutual-overlap cross term, no isolated-singleton exception and no forced
regional quota. The first curve keeps the existing bootstrap exception. This is
still a greedy heuristic: it cannot recover missing candidates or guarantee a
fully populated domain, connected stars, or a global optimum.

On the frozen current preset (rate100, isolation1, reach6.812, overlap scale4.031),
11 seeds previously retained 1–51 candle curves; restarts retained 49–67. Coverage
of 16-block XZ bins containing more than one expected candidate candle rose from
**0.4–64% to 64–80%**. This measures represented candidate regions, not the fraction
of all world volume that should be filled. At the same 6.812-block diagnostic,
isolated short candle curves were 0–1 per result, versus 6–16 with isolation off.
The reported failing scene changed from **490 to 1,694 objects**; another seed
changed from **2 to 1,856**. Two all-short pools recovered from one candle curve
each to 75 and 71. Disabling restarts reproduced the prior frozen short-turn
curve/star buffers byte for byte. Existing growth and population formulas stay
unchanged; additional selected populations can still affect occupancy and lighting.

Pair restarts scan cached nearby edges only when the normal loop stalls; they add
no gradient or distance queries. Each restart can scan the full sparse edge list,
so dense candidate graphs still cost more. Warm selection on the small fixture
was about 5–7 ms; a 953-candidate check changed from 23 to 39 ms. Timings depend on
machine load. Reproduce with `python scripts/evaluate_patch_restarts.py --settings
build/coverage-diagnosis/settings.json`. Frozen alternative sweeps, before/after
native renders and backward-compatibility checks are in `build/coverage-diagnosis/`.
The new default-on control reloads in the viewer; no preset rewrite is needed.
All 171 Python tests and the native panel startup check pass.

The isolation trial used the latest saved seed rate **50.167**, preserving the
user's other settings. On its 624 candidates, strength .9 / distance8 retained
212 candle and 153 rod curves, producing **9,268 objects**, versus 12,879 with the
penalty off. Short candle curves having no other selected candle sample within
8 blocks fell from **87 of 375 to 1 of 119**. In the actual candle population, grouping
by pair distances <=4 blocks reduced components with at most 30 objects from
925 to 495; these include sampling gaps within individual curves and are not a
count of isolated source curves. Strength .65 is a gentler alternative, retaining
10,921 objects. Very strong penalties with small distance scales collapsed to a
single cluster, so those were not selected as defaults. Native below/oblique
comparisons are in `build/isolation-evaluation/comparison.png`; the frozen settings,
numeric sweep, rendered buffers and validation metrics are alongside it. Re-run
the sweep with `python scripts/evaluate_isolation_selection.py --settings
build/isolation-evaluation/settings.json`. It never writes live settings.
Zero penalty reproduced the previous frozen curve/star buffers byte for byte.
Average near-parallel curve multiplicity at an 8-block, 30-degree diagnostic
changed only from 1.278 to 1.284; arc with more than three nearby parallel curves
changed from .292% to .349%. These are geometric checks, not hard overlap limits.
Building the proximity cache took roughly .56–1.09 seconds on this fixture;
warm selection took about 28 ms, with full Python generation about 2.04 seconds.
These timings vary with machine load. All 166 Python tests and the native panel
startup check passed. Python reload exposes the controls without a viewer rebuild.

For rods, compute an unweighted shared-footprint product `K_ij` at the rod scale,
normalized by `lambda * rod_scale`. With rod intensity ratio r, attraction a and
repulsion b, a candidate's score is
`(0.5*b*r*K_ii + b*r*sum_selected_rods(K_ij) - a*sum_selected_candles(K_ij)) / mass_i`.
Candle ranking does not itself get an extra lighting/rod reward. Short candidates
add `select_short_rod_penalty` to this mass-normalized rod score. Long candidates
have no extra cost. This is a greedy
heuristic; it does not perform swaps, cut curves into segments or guarantee a
globally optimal result.

The later short-turning trial keeps the user's current seed rate **40.271**, short
fraction **.5**, mean short length **24**, and all population/lighting settings.
On its **397 candidates (208 short)**, separate short response 2 / wandering .8
increased median accumulated short-curve turning from **42 to 163 degrees**.
Median endpoint distance divided by arc length fell from **.982 to .872**, so this
is actual bending rather than just finer tessellation. Short growth in the isolated
sweep took about **42 to 59 ms**; total generation timings vary with concurrent
viewer load. Long candidate paths and root identities are unchanged. Both classes'
selection and final population can still change as their competitors change.

With a **.5 short-rod penalty**, selected shorts changed from **46 candle / 94 rod**
curves to **91 candle / 15 rod** curves. The full population changed from **8,315
candles + 839 rods** to **8,964 candles + 679 rods**. Short wandering 1.5 gave more
turning but fewer retained candles and a visibly sparser result; .8 is the default.
The penalty does not test whether candles are lit: existing rods still score candle
proximity and rod redundancy. It leaves shorts available for the existing density
objective instead of adding another candle reward. Revert this trial's behavior by
matching short response/wandering to their long values and setting the short-rod
penalty to 0. Existing saved settings are retained; new controls get their defaults
on schema reload. Native before/after views and frozen requests/results are in
`build/short-turn-evaluation/comparison.png` and adjacent files. Visual acceptance
remains the user's judgment.

Before the isolation trial, screenshot tuning compared single-length pools, higher population intensities,
short means 24/36 blocks, seed rates 64/96/128, length mixtures and sky .05/.10/.16.
The chosen frozen scene produced **1,169 candidates -> 670 candle + 243 rod curves
-> 15,731 candle objects + 1,824 rods**. Of the selected curves, **558 candle and
197 rod curves** came from the short class. 256 instead of 128 footprint samples
gave 17,418 total objects versus 17,555: similar aggregate density, different choices.
The higher seed rate offered more short choices but cost more for modest visual gain.
Native renders show narrower strings, local short strands and clearer rod lighting,
but still more continuous long strings than the references. Candle geometry remains
simple cuboid proxies; the reference's planets and scenery are not represented.

On identical geometry the new lighting reduced mean unlit-candle RGB luminance
from .636 to .347, versus .740 to .645 for candles at block-light level 8 or above.
Rods stayed .957 to .956. Counts, positions, shapes, sizes and curve bytes were
identical. The normal final sampler reached its integration budget; a diagnostic
4.46-million-probe run without that cap produced 17,575 objects, just **0.11% more**.
This checks aggregate stability, not exact cell-by-cell convergence.

There is no hard 1–3 curve limit or definition of a filament. Whole-curve selection cannot
guarantee connected components or preserve every thin bridge. The proxy fits
expected mass before final unit-cell occupancy, approximates edge fading, and
does not model density-based fade suppression. The reported density error is over
candidate-covered grid nodes, so it is not a full-domain quality metric and should
not be compared directly between different pools. Appearance still needs user
judgment; some thinner connections can be lost.

Candidate growth and population sketches are cached separately. Selection-only
changes reuse both; rod intensity and lighting changes also reuse the sketch.
On the tuned fixture, warm selection took 59–64 ms and full Python generation took
about 2.7 seconds; a fresh pool/sketch took about 3.4 seconds total. These exclude worker startup and
are not universal bounds. Local sparse grid products avoid exhaustive segment-pair
testing, but crowded pools can still approach quadratic storage/work in candidate
count, and the simple greedy minimum scan is quadratic in the worst case. Guards
reject over 2,048 candidate seeds before growth, over 524,288 sketch samples, or
over two million entries in either interaction matrix, rather than silently
truncating the pool.

Current tuning outputs are in `build/narrow-tuning/`: frozen requests/results,
`chosen.stars.bin`, `chosen-near-below.png`, `chosen-oblique.png`,
`validation.json`, and the reference comparison. No visible viewer was launched
for these native offscreen renders. The tested preset was applied after the viewer
closed, with backup `plot-before-screenshot-tuning.json`; the saved configuration
reproduces both chosen buffers byte for byte. Camera and shared field were preserved.
Earlier single-length evaluation outputs are
in `build/incremental-evaluation/`: `settings.json`,
`pool-sweep.json`, `rod-sweep.json`, `render-results.json`, `final-metrics.json`,
and `selection-comparison.png` (native populated close-up plus curve overview).
Re-run the numeric sweep with `python scripts/evaluate_population_selection.py
--settings build/incremental-evaluation/settings.json`; it writes only diagnostic
outputs, never the viewer's live configuration. The earlier independent corpus
(`density_curve_corpus.py`) and geometric coverage selector
(`density_filament_selection.py`) remain separate comparison experiments.

## Shared noise stage and block coordinates

**density_filament_curves**, **density_filament_branching**, and
**noise_filaments_branches**, and the separate curve-selection experiments consume one upstream
noise/density configuration, stored only in `generator.density_field`. There is
no preset-to-preset syncing. The **Noise / density field** section edits that
same object from each generator. These consumers use block coordinates throughout their
active pipelines; wavelength and XZ/Y half-extents are in blocks.

`_density_field.py` owns the common schema and evaluates A/B/C noise plus density.
The direct path samples that density; the active curve path grows finite curves
directly through that density, then populates them. It no longer extracts zero
guides or projects seeds. The existing grid-resolution control
now belongs to the upstream stage as **Noise grid resolution** (24–96 samples
per axis, dimensionless). Both paths therefore use the same evaluated arrays at
matching settings, rather than different resolutions. Resolution edits affect
interpolation and may change curves and stars. There is no new randomness.

On first launch, the viewer imports the saved curve field (or an already-saved
shared field) and its grid resolution, then removes duplicate upstream keys
from the two consumer presets. Branches' old dimensional settings convert once
to blocks; its old normalized frequency becomes physical wavelength. Subsequent
edits require no copying, coordinate adapter, or restart. Legacy external worker
requests retain compatibility, as do the other historical experiments.

Curve growth, star population, materials, fading and appearance remain local to
each consumer. **Block population** selects unit-cell occupancy for curve stars;
turning it off uses continuous positions in the same block coordinates. Full
blocks have side one; proxy dimensions are fractions of a block. Along-curve
population density is stars per block of curve. Curve seeds now use deterministic
block-center sampling, described below, separately from star population.

**Star population -> Original density influence** controls how the stable curve
population follows the upstream density. It is a dimensionless exponent, range
0-3, default 1: 0 bypasses exactly, 1 gives linear dependence, and 2 squares the
density contrast. The field is sampled along the unwarped curve centerline,
before transverse scatter. A single arc-length-weighted normalization across all
curves preserves the base average intensity, so dense parts and dense curves
gain population at the expense of sparse ones. Existing per-curve variation,
along-curve noise, material multipliers, taper and occupancy still apply; final
counts can change. No new random stream, source-curve change or transverse-width
change is introduced. Both continuous and block samplers use the same weighted
arc profiles. The already-computed upstream field is reused. Python reload only.

Camera position, orbit distance, clipping distances and movement speed use blocks;
their prior one-time migration is retained. Normal viewer autosave writes these
settings. Python does not overwrite live configuration files.

## Rooted branching (separate experiment)

Select **density_filament_branching.py** for the `_branching_field.py` trial.
It has its own local preset. **density_filament_curves.py** retains independent
field growth and its seed-rate, curve-length and joining controls. Switching
scripts does not replace either algorithm or copy their local settings; only
the upstream density field is shared.
Sparse, coordinate-hashed block roots each grow a two-way trunk. New branches
begin at actual parent vertices, forming one connected tree per root, without
guide extraction or any merge search. Existing density guidance, block star
population, materials, scatter and fading remain shared. Independent trees can
cross but do not merge. This is a branching trial, not visual equivalence to the
Minecraft references.

| Control | Meaning and effect |
| --- | --- |
| Mean roots per million blocks | Default .5; linear slider 0–5, numeric range 0–100. Same mean-normalized density-weighted block hash sampler as before. More roots produce more independent structures and usually more stars. No fixed-count promise or fallback root when none pass. Uses a new key `branch_root_rate`; the retired curve seed rate is not reused. |
| Mean total length per root | Default 1200 blocks, range 1–10000; key `branch_length`. Total arc budget for the entire tree, initially divided between the two trunk tips. Existing coordinate-hashed Beta variation applies per root. Longer budgets generally allow longer trunks, more branches and more stars. Old independent-curve `strand_length` is not reused. |
| Branch opportunity spacing | Default 48 blocks, range 4–256. Opportunities occur after seeded distances .75–1.25 times this value along each tip. Smaller spacing permits more, shorter branches from the same finite budget; actual star counts can change. A child needs at least one spacing of remaining budget. |
| Branch departure angle | Default 45 degrees, range 15–80. Initial angle from parent heading. Eight cone directions are tested .75 spacings ahead; seeded selection favors smoothed density among in-domain, unoccupied probe cells. Larger angles spread branches farther sideways; geometry, stops and star counts can change. |

At a successful birth, the child receives 35% of its parent's remaining budget;
the parent retains 65%. No budget is added or recycled after a stop. The child
starts with its departure heading, then restores ordinary density attraction and
alignment quadratically over one branch spacing of travel. Existing coherent
wandering remains. Descendants can branch under the same rules. A coarse spatial
hash (cell size max(response, spacing/4)) rejects crowded birth probes, without
moving or deleting deposited geometry. A tip stops before re-entering its own
previously exited hash cell, limiting loops. Domain exits clip the last step.
These are local occupancy checks, not exhaustive clearance tests; some near
parallel growth can remain where density guidance reconverges.

Field samples are batched. Each tip's random stream is keyed by root block and
branch identity. The two trunk halves are combined into one population path, so
the root does not introduce an artificial material/taper seam. Preview colors
identify root structures; star materials still belong to population paths.
Total possible growth above two million steps fails explicitly rather than
silently truncating or reducing roots. The ordinary binary vertex limit remains.

Frozen-scene trial: four roots, 20 child branches, 3,856 blocks of total arc,
378 stars. Each child start exactly matches a parent vertex and each root's
actual arc stays within its budget. Growth ~.06s; repeated native generation
.31–.33s including request transfer and buffer loading, cold first run ~1.09s.
The smaller 65,536-cell hash batches retain identical seed choices and improve
the saved seed-selection benchmark .29s -> .12s. Performance is scene-dependent;
cold startup is still not reliably under one second. Preview comparison:
`build/branch-camera-comparison.png`. Python/schema reload only; worker reuse
requires the already-rebuilt viewer. No live config writes or viewer auto-launch.

## Independent field growth (density_filament_curves.py)

**Mean seeds per million blocks** uses a linear slider from 0–100.
The existing default 500 and saved larger rates remain valid: `slider_max=100`
only limits the mouse track, while the parameter retains its 0–10000 numeric
range. Ctrl-click the value to type an exact rate. Lower rates retain a deterministic
subset of seed blocks, reducing curve starts and generally star counts. This
changes only the slider mapping, not the sampler or saved values. The slider
update requires a viewer rebuild/restart.

Seed density weights are now normalized by their mean over every eligible block
center: `p = min(1, rate/1e6 * w/mean(w))`, where
`w = (density/peak)**seed_density_power`. Thus the expected number is
`rate * eligible_blocks / 1e6` unless probabilities saturate at one. Power zero
retains the original uniform sampler exactly. Higher powers concentrate placement
without intentionally reducing the expected count; actual counts still vary with
the coordinate hash. Positive power on an entirely empty field yields no seeds.
The normalization uses the same trilinear density as acceptance, with separable
plane interpolation to avoid allocating coordinates for the whole block volume.
Region edits also change the normalization, so existing seed membership can change.
This Python change reloads without restarting; it does not modify joining.

**Y seed bounds** independently set the interval eligible
for seed births: `[-seed_y_neg * Y half-extent, +seed_y_pos * Y half-extent]`.
Saved reaches are fractions -1–1, default .65; the lower coordinate is the
negative of `seed_y_neg`. Either displayed boundary can cross zero, so the entire
interval can lie above or below the origin. Handles cannot pass each other.
The highlighted interval is allowed, not excluded. Within this region,
the density weighting controls placement, with no additional center taper.
Curves can grow outside the seed region and carry stars there; star fading is
separate. Larger fractions increase eligible volume and expected seed count,
and change density normalization. Hash draws stay fixed. Old symmetric `seed_y`
copies to both controls, with explicit signed settings taking precedence.
Equal signed values preserve the symmetric sampler exactly. Python reload only.

Zone controls use a two-handle bar spanning -100% to +100%, with zero marked.
Seed bars highlight the allowed interval in blue. Asymmetric Y controls
move independently across zero, stopping at the other handle. Symmetric XZ/Y controls
link both handles: dragging either changes the same reach on both sides.
Each bar labels the lengths of its three regions in blocks: lower excluded / seed
span / upper excluded, or lower fade / unfaded span / upper fade. These are positive
lengths and sum to the full axis extent, including when handles cross zero.
These are axis lengths, not counts of seeds or stars. Without a fixed physical
extent, region lengths instead use percentages of the full span.
The Lower/Upper fields below show editable signed block coordinates, with percentage
labels underneath; dragging and Ctrl-click numeric entry work in blocks. Legacy
generators use their own units, or percentages when no fixed axis extent exists.
Fade bars instead mark where the edge fade **starts**, with orange
outer bands fading toward the boundaries; moving inward increases fade width.
Y widths now span 0–2 (`upper start=1-pos_width`, `lower start=neg_width-1`),
so fading can begin on either side of zero. A width of zero disables that end;
move its handle to the outer boundary. One **Fade Y edges** checkbox sits above
the paired bar in the Y fade section; clump suppression remains separate per end.
Old enabled sides keep their widths, and an old disabled side becomes width zero
when the other side was enabled. If both were disabled, the common toggle stays
off and their saved widths are retained. The Y seed bar occupies
the former symmetric Y seed slot beside XZ, rather than being appended at the end.
The Y bar is dimmed while its common toggle is off. The shading
shows the configured zone, not measured star occupancy or density suppression.
Shared `_zone_controls.py` schema metadata selects these widgets across all
existing seed/fade zone controls, including symmetric comparison generators.
The range widgets and linear 0–100 seed-rate slider require the rebuilt viewer;
this UI change adds no randomness and does not alter geometry by itself.
The Display section opens by default on launch.

The independent growth script uses `_field_curves.py`. Accepted hashed
block centers are the actual roots. Each grows in two directions with the existing
coordinate-keyed mean-length/variation budget, divided equally between its tips.
The shared density's smoothed log gradient and Hessian supply local transverse
attraction and a preferred direction where the field is elongated. Headings turn
gradually, with optional coherent Perlin wandering. There are no extracted
polylines, nearest-guide projections, pair-family assignments, neighbor forces,
coverage constraints or child spawning. Curves stop at their budgets, the box
boundary, or an eligible nearby segment contact; density is not a lifetime multiplier.

| Control | Meaning and effect |
| --- | --- |
| Growth response length | Blocks, default 8, range 1–128. Sets heading response and density-derivative smoothing; geometric steps are half this value. Larger values produce a coarser, slower-turning response. Changes geometry and potentially star count, without changing seed selection or assigned length budgets. |
| Transverse density attraction | Dimensionless, default .35, range 0–2. Bounded steering toward higher density perpendicular to the current heading. Zero disables that pull; local directional alignment remains. No neighbor attraction. Changes geometry and possibly final counts. |
| Growth wandering | Dimensionless, default .15, range 0–1. Strength of coherent vector noise, with wavelength four response lengths. Its independent component is keyed by the root block. Zero removes wandering. Changes trajectories and possibly counts, not births or budgets. |
| Join nearby curves | On by default. An arriving tip attaches to an accepted segment and stops. Turning it off restores independent growth. No new randomness; shorter geometry changes star counts. |
| Join distance | Blocks, default 16, range 0–64. Positive values permit contact within this 3D distance; zero restores the previous shared-block algorithm. Larger distances consolidate more nearby paths and generally reduce arc length/stars. Seed selection and assigned budgets stay unchanged; no new random draws. |
| Join alignment angle | Degrees, default 30, range 0–90. Maximum difference between unoriented tangents, so opposite headings also qualify. Larger angles permit more contacts, potentially shortening more curves and reducing stars. At 90 even perpendicular crossings qualify. No additional random draws. |

For positive join distance, `_proximity_contacts.py` queries all deposited
segments in range using a midpoint tree and exact segment distances. It tests
the full proposed step, so long steps cannot skip short targets. Same-source
segments are excluded. Fresh parallel fronts yield in coordinate-seed order;
segments at least two batches old can receive either priority. A source ancestry
record prevents a receiving route from subsequently stopping against its own
feeder. Both tips of a feeder may join the receiver. This preserves onward
growth while consolidating independent arrivals.

An arriving tip ends with a short cubic connector matching its incoming heading
and the receiving tangent. The six-piece polyline is the exact geometry deposited,
rendered and populated. Its arc length must fit the remaining tip budget; its
control points stay inside the domain. Targets come from previously accepted
batches. No target geometry moves, no neighbor force bends ongoing growth, and
no already-grown geometry is deleted. Branch material identities stay separate,
and contact neither sums nor replenishes budgets.

At distance zero, `_block_contacts.py` keeps an incremental dictionary of occupied unit blocks.
Each step traverses every positive-length block span, including intermediate
blocks on long steps. Exact boundary/corner-only touches are not occupancy;
negative coordinates and travel use the same half-open grid convention. All
accepted segments in a block are retained, so a transverse crossing cannot hide
an aligned target. Both halves of the same seed are excluded from contact checks.

At the first block with an eligible contact, the tip attaches to the closest
target point to its cell-entry position, constrained to the target's span inside
that block and to the tip's remaining travel budget. No target geometry moves.
Proposals are processed in coordinate-sorted seed order and fixed half order;
later proposals see only geometry already accepted, including earlier proposals
in the same step. No speculative targets, tree rebuilding or long-range attraction.
An attachment creates a geometric junction, not an extra copy of the receiving
path. Already-grown branch paths/material identities remain separate; connected
components do not sum or replenish growth budgets. This does not restore the old
same-guide rule limiting a whole connected component to one seed's maximum budget.

Saved-scene comparison (85 roots, mean length 240.188, saved join angle 90 degrees):
shared-block contacts versus 16-block proximity contacts reduce total arc from
14,369 to 9,179 blocks, with 69 versus 112 stopped tips. Sustained parallel overlap
falls from 4,408 to 958 blocks (78%): measured as runs at least 24 blocks long,
within 8 blocks of another path, with unoriented tangents within 30 degrees.
All 85 roots remain. Stars fall from 1,429 to 922 because redundant arc is removed.
Growth takes about .12s versus .21s. The saved-camera comparison is
`build/merge-camera-comparison.png`. Residual parallel paths and loops remain;
local contact cannot collapse arbitrarily separated paths or delete old prefixes.

No post-growth consolidation is used. Before block contacts were added, uniform seed sampling at rate 500 in the
saved scene produces 6557 curves rather than the earlier 131 merged intervals.
At density power 1 it produces 69 curves. This makes the shared star population
substantially more expensive for the uniform case; guide removal does not solve
that separate cost. Measured power-1 stages: field .05s, seed selection .33s,
growth .08s, population .55s, excluding worker startup. Seed hashing now evaluates
axis products and constructs full XYZ records only for survivors, preserving the
previous hash and selection exactly. Density is sampled only for hash candidates.

Block-contact check on the later saved scene (uniform seed rate 52.083, mean
length 140.193): 690 starts retained, 236 tip contacts, total length
91415.56 -> 86476.28 blocks. Growth off/on measured about .17/.89 seconds.
Full worker generation after tests completed measured 3.42s off / 4.27s on,
with 15861 / 15074 stars respectively (excluding process startup).
Returning 690 paths is expected: contact stops extension, not removal of existing
branches. Those timings exclude field/seeds/population/startup. Visual judgment
is still required; same-cell near-parallel paths can deliberately become junctions
even if their continuous lines never intersect exactly.

Growth rejects more than 8 million possible tip steps rather than silently
reducing seed counts, travel, or resolution. The worker's existing line-vertex
limit still applies. Existing stars/materials/postprocessing are reused. Python
reload only. The old non-DAG arc-root comparison is retained for compatibility;
its historical guide-based description below does not describe the active path.

## Build and run on Windows

From this directory in PowerShell:

**To run an existing build, no compilation is needed:**

```powershell
.\build\Release\filaments.exe
```

You can also double-click that executable in File Explorer. Rebuild after changes
to C++ code. Python generator edits reload while the viewer stays open:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Run
```

The first build downloads a portable x64 Clang/MinGW compiler, CMake, Ninja,
and pinned library sources. Git and curl must be available. Tools are kept in
`.tools/`, dependencies and generated files in `build/`; no administrator install,
global PATH change or Visual Studio workload is needed.
ExecutionPolicy Bypass applies only to that PowerShell process.

Python 3.10+, NumPy, SciPy, and pyfastnoiselite are required for the noise generators.
The current setup uses the existing `py310` Conda interpreter with NumPy 1.24.3;
pyfastnoiselite 0.0.7 is installed separately in `.tools/noise-python` and loaded
automatically by the worker. The Conda environment is unchanged.
On a new machine, use `python -m pip install -r python/requirements.txt`
in your chosen environment. The build discovers and remembers the interpreter;
to select another one, pass `-PythonExecutable C:\path\to\python.exe` to the build
script. This selects an executable, not a Python DLL linked into the viewer.
To install only the compiled noise wheel locally with that interpreter, use
`python -m pip install --only-binary=:all: --no-deps --target .tools/noise-python pyfastnoiselite==0.0.7`.
The local wheel must match the selected Python version and architecture.

Subsequent builds reuse these downloads. Release is the default:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Test
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Configuration Debug -Test
.\build\Release\filaments.exe
```

The executable uses a static C++ runtime and can be launched directly, from any
working directory. It requires a Windows graphics driver supporting OpenGL 3.3.
The executable locates `python/worker.py` and `generators/` at their source-tree
paths recorded during the build, independent of your working directory. Keep
these files and the selected Python environment available. Moving the repository
requires reconfiguring/rebuilding once to refresh these paths. Advanced overrides:
`FILAMENTS_PYTHON` (absolute interpreter path) and `FILAMENTS_GENERATORS`
(absolute generator directory), set before starting the viewer.

## Live generation

Choose **galaxy.py** or **filaments.py**, set the star count and seed,
and adjust the pattern sliders. These are artistic procedural models, not
astrophysical simulations. **Auto-apply parameters** waits 350 ms after the last
edit before generating. **Generate / reload** always reruns the selected script.
**Random seed + regenerate (G)** chooses a different seed and immediately reruns
the current script with the current parameters. Press **G** while controlling the
camera, including in captured first-person mode; typing into GUI fields does not
trigger the shortcut. The seed field shows the new seed for reproducibility.
**Reload on script save** watches Python files every 500 ms, including additions
and deletions. Each script defines its own sliders; adding parameters or a new
pattern does not require a C++ rebuild or an application restart.

While Python works, you can continue moving the camera around the previous cloud.
A newer request cancels an older job; **Cancel** stops generation. Errors and
tracebacks appear in the panel and the previous valid cloud stays visible.
The first successful cloud is framed automatically unless a saved camera is
restored; later updates preserve the camera. Use **Fit cloud** to reframe a
different-sized distribution. Each generator has **Star size (units)** and
**Size variation** controls; changing these leaves star positions unchanged.

Plot settings save automatically to the repository's `config/plot.json`:
selected script, star count, seed, each script's parameters, auto-apply/file-watching
preferences, rendering mode, size scale, round points, axes, background, VSync,
and camera position/direction. The selected plot regenerates from those settings
on the next launch. Point buffers and transient performance statistics are not
saved. The original spatial algorithms are preserved in `galaxy.py` and
`filaments.py` for comparison with the noise-based patterns.

The C++ viewer writes settings 350 ms after edits settle, including when
Auto-apply is off or generation fails/cancels. Continuous camera movement saves
at least every two seconds while edits are pending. Normal exit flushes remaining
edits. Files are replaced atomically; a failed save leaves the previous file
intact and is retried, with an error shown in the panel. Idle frames do not write.
Python scripts define control schemas/defaults and never edit themselves.

`config/plot.json` and `config/controls.ini` belong in version control, so commits
can preserve and share a chosen configuration. Atomic-save `config/*.tmp` files
are ignored. Settings changes appear as ordinary Git changes until committed.
The latest settings from the earlier `%LOCALAPPDATA%\Filaments` location were
copied into `config/`; the viewer now uses the repository copies. Like the script
paths, the absolute config directory is recorded at build time, so launching
from another working directory works and moving the repository requires a rebuild.

Two additional scripts explore noise-driven densities:

- **noise_clouds.py** samples a density derived from several scales of smooth
  gradient noise. Increase **Density contrast** for stronger clumps and emptier
  voids; at zero contrast the distribution is uniform.
- **noise_filaments.py** concentrates stars where two independent noise fields
  are both near zero, forming winding strands. **Strand thickness** widens their
  density profile; **Clump contrast** varies density along them.
  **Strand continuity** (default 0.5) adds a floor to the clump modulation along
  the existing strands. At 0, the original clump modulation is unchanged; at 1,
  it is uniform. At 0.5, clump modulation alone can vary density by at most 2:1.
  This reduces faint stretches without introducing more strands or changing
  their widths or wavelengths. It cannot join genuinely separate loops.

**Noise filaments** also has three **Density curve** slope controls in the
generator settings. This is density postprocessing before sampling, separate
from the shared star Postprocessing panel. Let `x = density / max(density)`:

```text
f(x) = low * min(x, 1/3)
     + middle * clamp(x - 1/3, 0, 1/3)
     + high * max(x - 2/3, 0)
```

The new density is `max(density) * f(x)`. Low, middle and high refer to thirds
of the input density range, not thirds of the stars or spatial regions. Each
slope is dimensionless, range 0.05-3, default 1. All ones bypass exactly.
Below 1 compresses the corresponding segment; above 1 steepens it. Segments
connect continuously, so changing a lower slope also shifts the starting
height of later segments. Positive slopes preserve density ordering and zeros.
For a first peak-flattening trial, keep low/middle at 1 and set high to 0.25:
the lower two thirds stay unchanged and input 1 maps to 0.75. A slope of 0.05
is almost flat. These controls add no randomness and preserve the requested
sample count, redistributing its sampling probability. They work even with
Strand continuity at 1. Uniformly scaling all three slopes has no distribution
effect because sampling normalizes density. Colors follow the processed density;
per-star sizes keep their independent draws. This remaps values, not spatial
noise frequencies, and does not spatially smooth the field.

Order: original density, density curve, native edge fade, star sampling, shared
star merging/alignment/warp. Later merging can still reduce the displayed count.
The shared `build_density` function stays raw for existing comparison experiments.

**noise_filaments_branches.py** always combines A/B, A/C and B/C with equal
weight. Its base density is the symmetric sum
`exp(-(A*A+B*B)/(2*w*w)) + exp(-(A*A+C*C)/(2*w*w)) + exp(-(B*B+C*C)/(2*w*w))`.
The families meet at triple-zero junctions but can produce a much busier pattern.
Connectivity and Layer continuity have been removed from this generator; old
saved values are ignored and disappear when the viewer next saves a successful
generation. Thin Y samples a literal slice without relaxing any field constraint.
The original two-field generator remains available for comparison.
The branches generator supports the same density curve and Strand continuity
controls. Strand continuity defaults to 0 here to retain its older clump
modulation. **layer_filaments.py** remains the separate cellular experiment.

The branch sampler and Density-guided local strands share an additional broad
density layer. After the three-regime value curve, multiply the fine density by
`exp(strength * (B(x)-max(B)))`, where B is one independently seeded Perlin octave
at `frequency / broad_scale`. Subtracting its maximum is a common normalization
that cancels during sampling. This changes the large-scale allocation of material
without changing A/B/C, their detail octaves, strand thickness, or clump noise.
It does not add another zero-surface constraint or new fine filaments. Curves are
regenerated in the reweighted field, so individual paths need not stay fixed.

- **Broad density strength (0 off)**: dimensionless, default 4, range 0-12.
  Higher values favor broad high-density regions and empty out others. Zero
  bypasses the new noise evaluation and restores the previous density exactly.
  This remains effective at Strand continuity 1.
- **Broad density scale (base wavelengths)**: dimensionless multiplier, default
  2, range 2-8. Two adds variation one octave coarser than the base geometry noise;
  larger values make broader regions. World-space scale is approximately
  `extent * broad_scale / frequency`, following the existing noise convention.

The broad field uses a separate seed stream (505); existing random streams stay
unchanged. Direct sampling retains the requested star count and size draws.
For curves, the number of attempted starts and length budgets stay unchanged,
but termination/joining can change total length and sampled star count. Local
overlap can increase in favored regions; this experiment does not cap it.
The initial strength-4/scale-2 trial is enabled through schema defaults without
editing live settings files. Before this experiment, code and saved settings
were committed as `b9f9455`. A comparison from that preset is saved in
`build/broad-density-comparison.png`: 1,408 versus 1,413 sampled stars, about
1.46 versus 1.61 seconds through the pipeline excluding startup in that run.
These are scene-dependent measurements, not a visual-quality guarantee.

`noise_filaments.py` and `noise_filaments_branches.py` now have independent
**XZ half-extent (units)** and **Y half-extent (units)**. They define bounds
`[-XZ, XZ]` in X/Z and `[-Y, Y]` vertically. Defaults are 6 units each; XZ ranges
1-30 and Y ranges 0-30. Y=0 makes a flat layer. Changing XZ no longer multiplies
the Y half-extent. Changing Y selects a different noise slice rather than merely
stretching existing points. Noise frequency still specifies detail across the
horizontal span, so changing XZ extent also changes the world-space noise
wavelength. These dimensions add no randomness or stars; count stays fixed
before merging. Earlier comparison generators retain their old extent/fraction
controls.

The **XZ edge fade** and **Y edge fade** sections each have an independent
on/off toggle, width and clump suppression. Width is a fraction of that group's
half-extent (default .8, range .05-1); larger means a broader taper. Suppression
has the same dense-only shoulder in each group (default 1, range 0-4). Neither
adds randomness. The XZ envelope uses `max(abs(x/XZ), abs(z/XZ))`; Y uses
`abs(y/Y)`. Disabled groups contribute no attenuation, and Y fade is bypassed
for a zero-height layer. Where both apply, the stronger attenuation wins rather
than multiplying two fades; equal settings reproduce the old box envelope.
These density stages redistribute a fixed requested star count before merging.

Old saved presets migrate inside the worker: `y_extent = extent*y_scale`, and
the old fade toggle/width/suppression populate both axis groups. Explicit new
values take precedence. The viewer receives migrated values on source reload
and saves them normally, avoiding external writes to live settings. To taper
the horizontal outline without thinning the layer vertically, turn off Y fade.

In the original two-field **noise_filaments.py**, **Layer continuity** defaults to 1 to reduce isolated
patches caused by slicing across 3D strands. The base strand family uses
`exp(-(a*a + beta*b*b)/(2*width*width))`, multiplied by the clump modulation, where
`beta = (1-continuity) + continuity*y_thickness**2`.
As the layer narrows, relaxing the second field constraint favors curves across
the layer's horizontal sections, but actually broadens the 3D density into sheets
around A=0. The name does not imply a guarantee of connected strands. The noise
wavelengths remain unchanged. Set continuity to 0 for a
literal slice of the 3D density. Full thickness is unchanged either way.
This is an artistic heuristic: natural voids remain, and connected strands are
not guaranteed for every seed.

In both, **Noise frequency** changes how many structures fit inside the volume;
**Detail octaves** and **Detail strength** add finer features. **Extent** scales
the volume without changing the underlying normalized pattern. FastNoiseLite's
compiled Perlin/fBm implementation fills a 96Â³ density grid in native code;
NumPy handles continuous trilinear density sampling, so stars
do not sit on a lattice. The grid limits the finest resolvable detail. Counts,
colors, and per-star sizes use the same protocol as the original scripts.
Adding these scripts requires no viewer rebuild or restart: the file watcher
refreshes the Script dropdown. If watching is disabled, click **Generate / reload**.
Switching from the earlier NumPy noise backend changes the patterns for a given
seed; seeds remain reproducible within this backend. The two-field intersection
is an artistic implicit-curve construction, not a model of gravitational cosmic
structure formation.

Run `python -B scripts/benchmark_noise.py` to compare the compiled 3D algorithms
and full in-process filament generation without opening the viewer. On this
machine, one octave over 96Â³ points measured about 16 ms for compiled Perlin,
22 ms for OpenSimplex2, and 25 ms for OpenSimplex2S, versus 299 ms for the earlier
NumPy Perlin. Perlin is the current backend because it was fastest in this test.

**layer_filaments.py** remains available as a separate cellular experiment.
It uses a full 3D web of noise-warped Voronoi edges: density peaks where the
three nearest jittered sites are nearly equidistant. Cells change through Y.
**XZ scale (units)** and **Y scale (units)** set the axis half-extents and scale
the cell wavelengths with them; equal values give a roughly isotropic web.
**Cells across each axis**, **Strand width / cell**, **3D warp / cell**, and
**Clump contrast** control the structure. **Fade edges** tapers the rectangular
boundary with adjustable **Fade width**. It uses a 96Â³ density grid and SciPy's compiled spatial index;
SciPy 1.10.1 is already present in the configured Python environment.

The panel reports generation/packing time, total worker/transfer time, CPU time
spent uploading to OpenGL, and FPS. Timing varies with the algorithm; rendering
is not necessarily the slowest operation. Python startup and file transfer are
paid only on regeneration, not on every rendered frame.

### Soft alignment postprocessing

**noise_filaments_aligned.py** samples `noise_filaments.py` unchanged, then nudges
the resulting stars toward smooth guide curves from the same A/B noise fields.
It preserves the random cloud, star count, point order, clumps, sizes and default
colors. It neither replaces the cloud with paths nor distributes stars evenly
along a guide. It increases local concentration around guides but does not
guarantee a population per curve or fill gaps along their length.

- **Alignment strength** (default 0.6) controls the pull. At zero, positions,
  colors and sizes exactly match the base generator. Its maximum is 0.95 so
  influenced stars retain scatter instead of snapping completely onto a curve.
- **Alignment reach (units)** (default 0.35) defines a local influence radius.
  The pull tapers smoothly to zero at its edge. Stars beyond reach stay fixed.
- **Guide smoothing** removes grid-scale corners from the attracting paths.
- **Guides across Y layer** adds multiple internal paths when Layer continuity
  relaxes the density in a thin region. The guide constraint blends B with a
  horizontal plane: `sqrt(beta)*B + sqrt(1-beta)*frequency*(Y-anchor) = 0`,
  intersected with A=0. These are heuristic paths through the broadened density,
  not exact density ridges. Full-depth mode retains the original A=B=0 guides.
- **Color alignment (0 off, 1 on)** blends affected stars toward per-guide colors
  in proportion to the pull, without changing their positions.

Short guides below twice Alignment reach are excluded, and open endpoints do not
attract stars beyond their ends, avoiding compact endpoint piles. A region with
no useful guides is returned unchanged. Regions far from guides remain diffuse.
Base edge fade is applied during sampling;
the subsequent small nudges can slightly change that profile. The nearest of
eight nearby polyline segments is used for the projection, in bounded batches.
All earlier generators remain available. This requires no viewer changes.

### Explicit curve sampling experiment

**noise_filament_curves.py** uses this pipeline, entirely in live Python scripts:

1. Evaluate the same two strand noise fields as `noise_filaments.py`.
2. Extract their shared zero contours as explicit paths on a tetrahedral grid.
   Shared faces stitch segments into open curves and closed loops.
3. Optionally smooth those paths and form bundles of nearby curves.
4. Allocate a minimum star count per retained curve, then distribute the remaining
   stars in proportion to curve length. Place stars at regular arc-length
   intervals, preserving endpoints and avoiding duplicate loop seams.

This samples the curve geometry itself instead of randomly sampling a density.
Faint clump modulation cannot erase a stretch of an extracted path. It does not
connect separate paths, and the 96Â³ field grid can still miss unresolved features.
The prototype uses a literal Y slice; it does not apply the older layer-continuity
relaxation or an edge fade. Bundles may extend beyond the sampling box by their
radius. Star count alone does not guarantee touching rendered cubes: a long curve
with too few stars can still have visible spaces between regularly placed stars.

- **Minimum stars per curve** reserves a floor for each retained path, including
  bundle curves. If the total budget is insufficient, longest centerlines take
  priority, then their satellite curves. Fewer paths are retained; the total star
  count remains exact. A total count below the minimum places all stars on one path.
- **Curves per filament** and **Bundle radius** make thick filaments from multiple
  coherent offset curves, with no independent random scatter per star. A zero
  radius uses just the centerline rather than creating coincident duplicates.
- **Curve smoothing** reduces grid-scale corners; **Ignore curves shorter than**
  removes tiny fragments. Both affect extracted geometry explicitly.
- **Color by curve (0 off, 1 on)** assigns each path a stable color for a fixed
  seed and configuration, useful for inspecting the bundles. Color and star-size
  edits do not rearrange positions.

Shared extraction, bundling and allocation helpers live in `generators/_curves.py`;
noise construction remains separate. Other generators stay available, and no
renderer or worker-protocol change is required.

## Zel'dovich displacement (`zeldovich.py`)

This separate generator starts with nearly uniform, jittered particles and a
Gaussian random density field. FFTs turn that density into a displacement field
with `divergence(s) = -density`. Each particle moves directly from its initial
position `q` to `x = q + D * s(q)` in a periodic box. Increasing **Evolution
strength** creates concentrations and voids; the default is 1.8. The spectrum is
chosen for appearance, not calibrated cosmology. NumPy and SciPy handle the math;
no viewer rebuild or additional dependency is required.

- **Structure scale** sets the smoothing scale of the initial density, and
  **Small-scale detail** adds finer structure. The field uses a fixed 96Â³ grid;
  scales below one eighth of the box width are capped to limit aliasing.
- **Evolution strength** is a one-shot displacement multiplier. Smaller steps
  through the same values only animate the same trajectories; there is no
  iterative solver to converge. After trajectories cross, stars pass through
  concentrations rather than binding into stable structures.
- **Void threshold (mean density)** replaces the former density-power control.
  It multiplies density by `rhoÂ² / (rhoÂ² + thresholdÂ²)`, where `rho` is relative
  to the volume-mean density. The default threshold is 1 (range 0â€“4). The
  multiplier is half at the threshold, tiny in voids, and approaches 1 in
  peaks, avoiding the peak amplification of a power law. Threshold 0 returns
  the original particles exactly. Otherwise a periodic 64Â³ smoothed density
  estimate is filtered and sampled continuously, retaining the requested count
  without duplicate particles. Renormalization still reallocates removed void
  mass across surviving regions; it does not cap existing peaks. At least
  262,144 pilot particles reduce density-estimation noise at small star counts.
  The density helper lives in `_postprocess.py` for reuse by other methods.
- **Y scale fraction** compresses the complete result vertically, including
  its features. It does not slice a thin region out of the field. At 1 the
  construction is statistically isotropic.
- Colors run from blue to warm as the final local particle concentration rises.
  Coloring does not change positions. Star size and size variation remain
  independent per-star attributes.

## Minecraft block population trial

The visual target is the reference collection in `scar/`: a shallow, patchy
star canopy, many tiny pale objects, fewer bright rods/cubes, and large dark
gaps. Planets are a future milestone; physical size relationships are not a
constraint. Block mode now includes candle, end-rod and full-block cuboid proxies.

For the active stable curve generator, **Star population -> Block population**
selects cell sampling; turning it off selects continuous stars in the same block
coordinates. Older comparison generators retain **Blocks per unit
(0 = continuous stars)** and their legacy parameter conventions.
Choose **Shaded cubes** with **Star size scale = 1** for
block geometry. The display multiplier and Points mode remain available
but are not a literal block preview. Later palette/control edits reload from
Python without a rebuild. The cuboid renderer itself requires a rebuild
and viewer restart. Saved settings are not modified externally.

**Minecraft material proxies** defaults on when block sampling is used. Turning
it off restores the plain unit-cube comparison; continuous sampling is unaffected.
Each source path receives one material and one candle color from a muted cream,
lavender and gray palette. These are artistic approximations, not block textures.
**Use curve colors** overrides the palette for diagnostics without changing types.
At a shared cell, one contributing curve wins with probability proportional to
its integrated mass, so materials and colors are not blended at crossings.
Path identities can change when the generator changes its paths.

| Control | Meaning and count effect |
| --- | --- |
| Candle / Rod / Full-block curve weight | Three dimensionless weights, each 0-100, defaults 82/15/3. Normalize by their sum to obtain the probability of assigning an entire curve to each material. For example 6/3/1 means 60%/30%/10% of curves in expectation. Zero excludes a material; at least one weight must be positive. Changing the mix can change counts through the density multipliers. These are not exact final object ratios: curve lengths, intensity, taper and occupancy also matter. |
| Rod density multiplier | Dimensionless, default .4, range 0-1. Multiplies a rod curve's population intensity before cell integration; 0 removes its population, 1 matches candle density. Changes counts, without changing transverse scatter. Occupancy saturation means final counts need not be exactly 40%. |
| Full-block density multiplier | Dimensionless, default .05, range 0-1. Makes full-block curves extremely sparsely populated, giving sporadic blocks while retaining the same curve-based pipeline. Zero removes their population; 1 matches candle density. Changes count, not scatter or source geometry. |
| Maximum candles per cell | Integer 1-4, default 4. Per-cell group weights are .50/.27/.15/.08, truncated and renormalized at this maximum. Higher values permit wider groups; no positions, colors, rod shapes, or occupied-cell counts change. |

**Stars per block of curve** is the common intensity before these multipliers.
At .25 per block, candles use .25, rods default to .1, and full blocks to .0125
(one object per 80 blocks of curve before taper/occupancy). Candle palette colors
are still chosen equally per candle curve. Previous `pop_rod_fraction` presets
migrate to three weights preserving their prior material probabilities and seeded
assignments; full-block sparsity is the intentional appearance change. New controls
and migration reload from Python without restarting the rebuilt cuboid viewer.

Candle proxies are upright cuboids with height 6/16 block and XZ width
2/16, 4/16, 5/16 or 6/16 block for groups of one through four. No individual
candles or flames are drawn. Rods are 1 block long and 2/16 thick, independently
and equally oriented along X, Y or Z per occupied cell. Opposite facings are
visually identical until a directional end cap is added. Full blocks are 1 cubed.
All proxies remain centered within their selected block cell and fit inside it;
these are visual stand-ins, not support/attachment-aware Minecraft placements.
Fading preserves each surviving cell's base color, dimensions and orientation.
With lighting enabled, removing a source can darken nearby surviving candles.

### Block lighting

**Postprocessing -> Block lighting** applies to Minecraft material proxies.
End rods emit level 14, full blocks emit level 15, and candles are unlit.
At each surviving cell center, light is the maximum of zero and
`emission - (abs(dx) + abs(dy) + abs(dz))` over surviving sources, in blocks.
Block sources combine by maximum, and candles do not relay light. A separate
uniform cool sky contribution illuminates the exposed canopy even where block
light is zero. This first pass has no shadows, occlusion, sky-light propagation,
per-source colored light or bloom.

- **Block lighting** (`pop_lighting`): on by default. Off returns the previous
  base colors exactly. Continuous stars and the unit-cube comparison bypass it.
- **Ambient brightness** (`pop_light_ambient`): dimensionless fraction, 0-1,
  default .03. Adds neutral illumination above the lightmap's baseline, before brightness adjustment.
  Higher values brighten dark regions; 1 restores base colors everywhere.
- **Night sky illumination** (`pop_light_sky`): dimensionless strength, 0-1,
  default .35. Adds a uniform cool tint (.8, .82, 1) times this strength, independent
  of nearby sources. Higher values brighten exposed candles; 0 disables sky light.
  This does not draw a sky or moon. The lightmap retains a dim neutral baseline
  even with ambient, sky and block light all zero, as Minecraft's shader does.
- **Shadow brightness lift** (`pop_light_brightness`): dimensionless blend, 0-1,
  default 1. Higher values lift dark/middle illumination values after combining
  sky, ambient and block light. Zero uses the unlifted result. This approximates
  the effect of Minecraft's brightness setting; it adds no light sources.

None of these controls changes random draws, geometry, material assignment,
occupied-cell counts, sizes or orientations. The earlier untouched trial preset
(ambient .03 or .08, sky .2, brightness .5) migrates once to .03/.35/1 through
the normal worker response and viewer autosave. Custom combinations stay literal.

The preview uses the normal path of the
[Java 1.21.8 lightmap shader](https://mcasset.cloud/1.21.8/assets/minecraft/shaders/core/lightmap.fsh);
the rational light ramp feeds Minecraft's warm block RGB ramp, then sky light,
the first 4% neutral mix, extra ambient, clamping, the quartic brightness lift,
and the final 4% neutral mix. With extra ambient zero this matches the original
shader's GPU output to about 1e-7 for all 16 block levels at the chosen sky inputs.
The canopy assumes exposed sky level 15; its tint and strength were visually
tuned against the night screenshots in `scar/`, not recovered game settings.
The material palette now has brighter cream candles alongside dim gray/lavender,
near-white rods and pale cream luminous blocks. Three sky-strength trials were
rendered with the native renderer; .35 keeps the candles visible and dark gaps
intact. Before/after and below-canopy renders are in `build/scar-lighting-*.png`.
Minecraft separately maps sky and block light to screen color, as described in
[Mojang's lightmap notes](https://feedback.minecraft.net/hc/en-us/articles/42011663817357-Minecraft-Java-Edition-26-1-Snapshot-1).
The preview omits time of day, weather, exposure occlusion and status effects.
Emitting rods and blocks use the same mapping at their own light level, without
a full-bright override. Existing renderer face
shading applies to all proxies. One illumination color is baked into each object's
RGB, equally in cube and point modes; this is not a complete Minecraft lightmap.
Lighting runs after warp, occupancy and all survival fades, before any legacy
display conversion. Per-material nearest-neighbor trees query exact Manhattan
distance without a dense light volume or all-pairs source/receiver allocation.
The material IDs remain private worker metadata; FSTAR003 is unchanged.
Python reload only: no viewer rebuild/restart or external settings edits.

Material **edge fading** shares one seeded survival threshold across the occupied
cells owned by each source curve, equally for candles, rods and full blocks.
A curve with a low threshold reaches farther into the fading region; one with
a high threshold stops nearer the center. This correlates fading along the curve
instead of independently removing its objects. The existing positional envelope
and clump suppression still determine the local survival weight, and ordinary
sampling/tip taper can still leave gaps. Marginal survival probability is unchanged,
but a fixed scene's surviving count can change. Continuous stars and the unit-cube
comparison retain independent star fade draws. A crossing uses its selected source
owner. No source curves move or shorten, and no new coherence control is added.

The active generator now receives block-valued parameters directly. Its curves,
sampler, fade bounds, renderer and camera share those coordinates. A full cube
has side one, and a half-extent of 262.496 means a width of 524.992 blocks.
The one-time preset migration scales lengths and inversely scales density,
preserving the intended population and existing cell choices. The legacy
comparison path retains its conversion adapter; the active path has no ongoing
sampler/display scale conversion.

Block mode uses a separate sampler in `generators/_block_population.py`,
dispatched by `_population.py`. It integrates the existing curve intensity into
cells using scrambled Sobol probes: the shared along-curve density CDF,
per-curve density multiplier, Gaussian transverse scatter, and tip taper all
contribute. Probes are integration samples, not generated stars. Contributions
from all paths sum before selection. A cell with integrated expected population
`lambda` is occupied with probability `1-exp(-lambda)`, using a stable seeded
hash of its integer XYZ. This is Poisson occupancy, not fixed-count sampling,
rounding a finished star cloud, or refilling collisions elsewhere. At low mass
the probability is approximately lambda; crowded cells saturate at one object.
With proxies off, overlapping sources retain the earlier mass-weighted colors.

Cell `(x,y,z)` spans `[x,x+1)` etc., with center `(x+.5,y+.5,z+.5)` and side
one. Proxy dimensions are fractions of that cell. Floor handles negative coordinates consistently. A zero-thickness layer
on a cell boundary chooses the positive-side cell. The sampler introduces its
own reproducible randomness. **Spacing randomness (continuous)** and continuous
star size/variation do not affect block mode. Along-curve density variation is
still supported, but individual spacing follows cell occupancy rather than
the continuous sampler's stratified quantiles.

Swirl/wave warp acts on integration positions before cell
assignment, using the same transform for the curve preview. Wave
anisotropy uses a fixed spread measured from source path vertices. Shared
point-stage edge fading follows selection in block coordinates with matching
bounds; it only removes cells. The current star-based **Merge dense stars** and
**Align sparse stars** must be off in block mode; incompatible settings report
an error instead of moving blocks off-grid. Direct-star generators and plain
line previews do not expose this sampler.

Cell integration is approximate. It requests at least 128 probes per expected
star and 8 per block of arc, rounded to powers of two per path, with a total
2,097,152-probe budget. The response warns if this budget is reached. Very fine
grids or large transverse spreads can under-resolve individual cell masses even
below the cap. The existing one-million-object output limit still applies.
Exact voxel integration, occluded lighting and export are later work. Proxies use the
extended FSTAR003 format described below; unit-cube/continuous data stays FSTAR002.

Initial saved-scene check (seed 934903968): continuous 1,668 stars; scales
8/16/32 produced 1,587/1,693/1,614 occupied cells, each unique and grid aligned.
Scale 16 used 467,072 integration probes; the pipeline took about .94 seconds
excluding startup (continuous .28 seconds). Counts fluctuate because these are
different discrete samples. Appearance still needs visual judgment.

## Shared postprocessing

The collapsible **Postprocessing** panel offers three independent appearance
experiments for every generator, all off by default. Controls and algorithms live
in `generators/_appearance.py`; changes to those Python files reload live. The
C++ panel reads section names, checkbox hints, ranges, and dependent controls
from the worker schema. Adding a new section using these widget types does not
require another rebuild. A new widget type or C++ layout change does.

- **Density alignment** is used by `noise_filaments.py` and
  `noise_filaments_branches.py`. **Align sparse stars to density** uses the
  original continuous density rather than fitting directions to sparse stars.
  The generator shares its density after remapping but before edge fade;
  Gaussian smoothing and log-density derivatives are computed once per job.
  Each star takes bounded steps in the negative-curvature directions transverse
  to the local filament, approaching a density ridge without intentionally
  migrating along it toward a brighter blob. Movement fades where there is no
  clear filament direction. Steps backtrack if density decreases and stay inside
  the source box. There is no generated curve network or extra star population.
  The method remains limited by grid resolution and local ridge ambiguity.

  Merging runs first. Only unmerged originals can move, using the existing sparse
  fraction and feathered spacing cutoff; merged centers/colors stay fixed.
  **Field smoothing (units)** is Gaussian standard deviation in world units,
  default 0.25, range 0.02-3. Higher values ignore finer density detail but can
  blend nearby structures. **Maximum alignment travel (units)** reuses the old
  reach value and caps each star's total projection travel (default 0.5).
  **Alignment strength** mixes the original position with the projected position
  (0 unchanged, 1 full alignment); sparse-selection feathering also multiplies it.
  These controls add no randomness or stars and do not change colors/sizes.
  They tighten transverse scatter; they do not refill gaps or impose uniform
  along-filament spacing. Guide length and Color by guide are removed from these
  generators' panels because field alignment does not use those controls.
  Extremely thin Y (half-height below smoothing/20) uses Y-averaged XZ guidance
  while retaining each star's sampled height. Work is capped at 32 projection
  iterations, so a large travel limit does not guarantee ridge convergence.
  A saved-scene comparison is in `build/density-alignment-comparison.png`:
  15,963 stars, 9,862 moved, about 0.42 seconds for merging and alignment together
  in the initial measurement, excluding worker startup. Appearance is experimental.

- **Sparse curves** remains the sample-based method for other generators.
  It selects low-density stars using eighth-neighbor distance.
  When merging is enabled, it runs afterward on the remaining unmerged stars.
  Spacing is recomputed without combined stars; the sparse cutoff remains the
  input cloud's quantile, so newly sparse remnants can qualify too. Combined
  stars keep their centers and colors and do not seed or steer these guides.
  Random anchors are spaced across the cloud; each short sinusoidal guide follows
  its anchor neighborhood's principal direction and bends in its local plane.
  Nearby sparse stars are gently attracted to the guides, with smooth distance
  and density falloff. Dense knots remain untouched. **Attraction reach**,
  **Guide length**, **Alignment strength** and **Sparse fraction** control the
  effect. **Color by guide** is an optional visual diagnostic; it doesn't change
  positions. This is a local heuristic, not a connected filament skeleton or
  a minimum-population guarantee for every guide.
- **Merge dense stars** groups stars from the chosen dense fraction in randomly
  oriented spatial bins. Each bin's diameter is at most **Merge distance**;
  close stars across bin boundaries may remain separate. Merged positions and
  colors use volume-weighted averages, and size is `cbrt(sum(sizeÂ³))`. The result
  has fewer, larger stars without chaining a whole filament into one object.
  **Merged size boost** then multiplies only combined stars' diameters/cube sides:
  default 2, range 1-8, dimensionless. It adds no randomness and does not change
  grouping, centers, colors, or count. At 1 the merge preserves total cube
  volume; larger values deliberately increase visual weight (eight equal stars
  become four times as wide at boost 2). Unmerged stars retain their sizes.
  Groups whose base size exceeds 1000 units stay unmerged; boosted sizes
  saturate at that limit. Bounded bins can still leave multiple merged stars
  inside a broad blob.
- **Coherent warp** offers **Flow (0 swirl, 1 waves)**. Swirl, the default,
  applies a large-scale differential rotation around the world Y axis:
  `theta = angle / (1 + (horizontal_radius / swirl_radius)^2)`.
  **Swirl angle** sets rotation near the center (negative reverses direction),
  and **Swirl radius** is where that angle halves. All stars participate, keeping
  their Y coordinate and horizontal distance from the axis. This bends existing
  structures into a swirl; it does not attract stars to a spiral-shaped ridge.
  The original four-sine-wave displacement remains under mode 1, with separate
  **Wave amount** and **Wave wavelength** controls. Its short-axis displacements
  are reduced for thin clouds. Either warp preserves colors, sizes, and count.

The order is merging, residual sparse alignment, warp, then point-stage edge fade.
Merging classifies the original cloud before any alignment. **Sparse fraction**
sets the original spacing cutoff; after merging it is not a quota on the
remaining stars. Removing neighbors can make more remnants eligible. Alignment
still feathers its effect above that cutoff and within guide reach. Each experiment has a separate random
stream; toggles are deterministic for a fixed seed and configuration. Warp runs
after guide assignment and merging so changing its strength deforms the same
stars instead of rebuilding a different set of guides. Point-stage fade can
still remove different stars as they cross the boundary. All values
autosave per generator. Merging and point-stage fading reduce the displayed count.

Every generator in the viewer has **Fade edges (0 off, 1 on)**. The common
envelope in `generators/_postprocess.py` follows the rectangular bounds using
`max(abs(normalized_position))`, preserving the square outline rather than cutting
off its corners with a sphere. **Fade width** ranges from 0.05 to 1 and measures
the taper as a fraction of each half-extent. The default 0.8 starts fading at
20% of the half-extent and smoothly reaches zero at the face. Smaller widths
make a narrower edge transition; 1 fades across the entire half-extent.
**Edge clump suppression** (default 1, range 0â€“4) additionally suppresses dense
edge regions. It now acts only above a fixed knee `T = 0.25 * peak_density`,
using the pre-fade density after any density remapping. Empty space cannot lower
this threshold. With `r = density/T`, `q = max(r-1, 0)`, positional envelope `e`,
and suppression strength `s`, the output density is
`T * e * (min(r,1) + q/(1+s*(1-e)*q))`.
Below the knee the ordinary edge fade is exactly unchanged at every suppression
strength. Above it only the excess is compressed, with continuous value and
slope at the knee and no reversed density ordering. The full-strength interior
(`e=1`) is unchanged. Strength 0 restores position-only fading. No extra slider
was added; the quarter-peak knee is an experimental choice and a dominant
outlier can raise it. Suppression is distinct from the ordinary positional
fade, which still attenuates sparse regions toward the box faces.
The previous formula penalized every nonzero density against a volume mean,
so empty space caused faint filaments to be classified as dense too.
This thins existing structures; it does not extend them or create new branches.

Existing density generators
apply it before sampling and keep their requested star count. Other generators
use the worker's shared postprocessing stage: each sampled star survives with
the density-aware probability. Their density estimate uses a smoothed 48-cell
grid per active axis, compensating smoothing at the boundaries and ignoring
collapsed axes; opposite edges never wrap into each other. The point-stage knee
is one quarter of the maximum estimated density at stars.
For native density sampling, normalization redistributes the
fixed count after suppression, so unchanged low-density weights do not mean
identical sampled star positions. For sampled-star thinning, sub-threshold
stars retain exactly the same survivors when only suppression strength changes.
For point-stage thinning, surviving positions, colors and sizes are unchanged;
the displayed count decreases. Disabling fade restores the original output.

The fallback uses the cloud's bounding box unless the generator supplies
`postprocess_bounds(**params)`, returning `(center, half_extents)` in world
coordinates. Zel'dovich and explicit noise curves supply their known box bounds,
including Y thickness. A degenerate axis is ignored. If fading removes every
star, generation reports an error because the viewer requires a nonempty cloud.

The worker appends shared controls to each script's catalog, so they use the
existing GUI and autosave system without a renderer rebuild. A script that
already declares `fade` handles it natively; it is never applied twice. Further
point processors belong in `apply_to_stars`, with their schema added by the
worker. Density-aware operations can reuse the same helpers before sampling.

## Seed-grown curve preview (`grown_filaments.py`)

Select **grown_filaments.py** and use **Fit cloud** to inspect the skeleton.
This experiment draws continuous colored lines with small gold wire-sphere seed
markers; it does not populate stars yet. The initial line-display integration
requires a C++ rebuild. Subsequent Python growth/schema edits reload live.

Seeds are spaced within a ball. Each launches several separated directions;
tips advance with persistent headings, bent by a shared smooth 3D vector noise
field. **Noise turning** controls curvature (zero makes straight rays), while
**Noise scale** controls how quickly steering varies through space. **Filament
length** and **Length variation** control path budgets before Y compression.
**Y scale fraction** compresses the whole skeleton; seed markers remain spherical.

**Branch spacing** defaults to zero/off. Positive values add branches with a
one-unit minimum gap plus an exponentially distributed distance of that mean.
Children start on a parent vertex at **Branch angle**, inherit 65% of its remaining
length, and can branch through two generations, with a total limit of 256 paths.
Existing trunks remain unchanged when branching is enabled. Paths do not yet
seek other seeds, join, avoid collisions, or model a scalar density ridge. Crossings
are simply crossings. Growth has no clipping box or edge fade.

Colors identify the seed of origin. Color and marker controls do not change the
grown curves. Curve resolution is independent of the saved star count; the star
count and postprocessing controls are hidden for line previews. The renderer uses
one-pixel OpenGL lines in either saved star display mode. Star size controls are
disabled during the preview. Star population, width and density come later.

## Branching at noise-zero junctions (`noise_branch_curves.py`)

This separate line preview follows pairwise zero intersections of two to four
scalar noise fields. Select **noise_branch_curves.py**, then **Fit cloud**. Python
changes reload live; it uses the line renderer already built for grown_filaments.
**Noise** selects Perlin (0, default) or OpenSimplex2S (1).

For three fields, blue curves follow A=B=0, orange follows A=C=0, and green
follows B=C=0. When an AB curve encounters C=0, all three families meet at the
same triple-zero point. **Branch probability** decides separately whether to
launch a branch into each alternative family, choosing one outgoing direction
that favors continuation of the arriving heading. At starting junctions the
alternative direction is selected deterministically. Probability zero follows
only AB; adding fields supplies more possible junctions, not guaranteed global
connectivity. Four fields have six pair families and four possible triple types.

The implementation samples the fields on a fixed 48-cubed grid and uses linear
interpolation within a consistent tetrahedral mesh. It solves pairwise zeros on
tetrahedron faces and triple zeros inside tetrahedra, splitting the pair segments
at those shared points. Thus junctions come from the noise itself, without
nearest-seed links, proximity joins, or bridges across empty regions. This is
tracing the zero centerlines of a field approximation, not an attraction model
for offset trajectories. Small features below the grid resolution may be lost.

**Starting junctions** chooses spatially separated AB triple zeros, falling back
to ordinary AB vertices when no triple zeros exist. Yellow rings mark these
roots; white crosses mark reached triple zeros. Curves initially grow along both
AB directions. **Growth length** limits each root's travel before Y compression;
children inherit the parent's remaining travel budget. Branches start exactly on
the parent. Already traversed segments are not redrawn, and **Maximum curves**
bounds the number of paths. Length/curve budgets, closed loops, previously visited
edges, and the finite field boundary can stop growth. This preview does not add
scattered stars, smooth away junctions, or promise that every component connects.

**Y scale fraction** compresses the completed geometry, preserving its topology.
Star count has no effect on the skeleton. Star placement and filament widths are
still deferred. The earlier free vector-steered growth remains in grown_filaments.

## Historical guide-based density curves (legacy non-DAG path)

The current viewer uses direct field growth, described above. This section records
the preceding arc-root and block-seed/guide experiments; their projection and
interval-joining rules no longer run in the active viewer path.

**XZ/Y half-extent** now selects the sampled region of a world-space noise
field. **Noise scale (units)** independently sets its base spatial scale:
larger values make broader features, smaller values make finer features.
The old normalized **Noise frequency** control is replaced only in this active
stable-curves experiment. Existing presets migrate once with
`noise_scale = extent / frequency`, preserving their current field and fit.
Subsequent extent edits leave that scale fixed; the worker returns/saves the
new parameter through normal viewer settings, with no external config edits.
The default is 9.458/2.505 (about 3.776 units), range .1-60. This is a noise
coordinate scale, not an exact periodic wavelength. Clump/detail/broad fields
retain their existing relative scales. No new random stream is introduced;
larger bounds or changes to feature size can change total curve length/star count.

This removes whole-pattern stretching; it does not yet make extent edits append
an immutable set of stars. The fixed sample count per grid axis changes physical
interpolation spacing when bounds change. Increase grid resolution for larger
domains if needed. Re-extraction can change guide paths and seed projections;
density normalization and fractional seed/fade regions also depend on the box.
Consequently individual intervals, colors and star samples can still change.
Shared world-coordinate A/B/C values are invariant (within floating-point
precision); exact interior mesh/star identity is not promised. Older comparison
generators retain their existing frequency/extent conventions. Explicit legacy
Python calls with `frequency` and no `noise_scale` retain their old meaning.

Select **Density filament curves (stable seeds)**. The previous growth experiment
is preserved as `density_filament_growth.py` below. Curves use the same A/B/C
fields and symmetric branch density as `noise_filaments_branches.py`. Extract
each pair's entire zero intersection on a fixed tetrahedral grid using the
existing `_curves.intersect_fields`. These are exact zeros of the piecewise-linear
grid approximation, not exact zeros of continuous Perlin noise. Each family keeps
its own path through triple intersections; there is no family switching, wandering,
proximity joining, or density-gradient steering.

Test block centers `(x+.5, y+.5, z+.5)` inside the XZ/Y seed-region fractions
(both 0.65 initially), before extracting guides. Hash the integer coordinates and
scene seed to a fixed uniform value `u`; accept when
`u < seed_rate * 1e-6 * w / mean(w)`, with
`w = (density / field_peak)**seed_density_power` and the mean taken over eligible
block centers (updated normalization shared with the active field-growth path).
Power 0 bypasses density entirely, including zero-density cells. Changing the
power reuses the same hashes; higher powers redistribute seeds toward dense parts.
A larger region tests additional coordinates without reshuffling existing hashes,
but changes the weight mean. Extent edits can also change density interpolation.
There is no seed-region taper or curve-count quota. Empty samples report an error
and keep the previous viewer cloud. Work guards reject regions above 100 million
block centers or more than 8192 accepted seeds, without silently truncating them.

Only accepted block centers project to the nearest segment of an extracted guide.
These projected roots grow both ways simultaneously. Each block identity has a
fixed Beta(2,2) draw and total budget
`strand_length * (1 + length_variation * (2*Beta - 1))`.
Density controls births, not this budget. The central region restricts sampled
blocks; projection and subsequent growth can extend outside it.

On contact along the same guide, merge only if the combined length fits the
**maximum** of the two budgets, never their sum. The joined curve inherits only
still-active outer tips. Exhausted tips never restart. Failed joins stop the
contacting tips and leave separate curves. Closed guides wrap at their indexing
seam. No cross-guide joins, coverage targets, post-growth deletion or budget
redistribution are added. Colors follow the block identity of the largest budget
in each joined curve. Legacy worker requests without the shared density graph
retain the earlier arc-root experiment.

The separate XZ/+Y/-Y edge fades act **only on stars**, after shared appearance
processing (including merging/warp), using their final positions and the generator's
fixed half-extents. They never change curve geometry, colors, roots or travel
budgets. Each enabled axis supplies a smoothstep survival envelope, with its
existing dense-star suppression; the stronger attenuation wins. Fixed random
draws make stronger fading retain a subset of the same stars, preserving surviving
positions, sizes and colors. A width of 1 tapers from the center to zero at the
boundary; stars beyond that enabled axis's bound are also removed. It reduces
star count rather than dimming stars.

In this stable-curve generator, **+Y (above)** and **-Y (below)** each have their
own toggle, fade width and edge clump suppression. They refer to world Y, not the
camera. Width is a fraction of the Y half-extent on that side (default .8, range
.05–1); increasing it starts fading closer to the center and usually removes more
stars. Clump suppression is dimensionless (default 1, range 0–4); increasing it
further reduces dense populations within that side's fade. Neither adds randomness
or changes the opposite side's settings. Toggles default off. Previous symmetric
Y presets copy to both sides; explicit new side values take precedence. Earlier
direct-density/growth experiments retain their symmetric Y controls.

Central seeding limits root locations; it does not add an outer length falloff.
Very long curves can still reach and be clipped by the outer box, especially
along a thin Y axis; the curve preview deliberately retains those paths while
the stars fade away. `POPULATION_AXIS_FADE` opts this generator into shared
`_postprocess.apply_to_stars` axis fading with `postprocess_bounds`.

| Control | Meaning and effect |
| --- | --- |
| Noise scale (blocks) | Base spatial noise scale, independent of extent. Larger means broader features; no extra randomness. Can change path length and star count. Existing frequency presets migrate as described above. |
| Noise grid resolution | Shared upstream control: 48 samples per axis, range 24–96. Higher values refine the zero geometry and cost more. Changes geometry, projected roots and potentially star count. |
| Mean seeds per million blocks | Default 500, range 0–10000. Expected starts per million eligible blocks, with density weights normalized to mean one; probabilities cap at one. Higher rates retain a superset of starts and usually increase stars. |
| Seed density power (0 = uniform) | Dimensionless, default 1, range 0–4. Zero samples uniformly; 1 follows density linearly; higher values concentrate starts while preserving expected count before probability saturation. Actual curves and star counts change. Separate from Original density influence in star population. |
| Mean curve length (blocks) | Default 32, range 0.2–3840, across both directions; saved key `strand_length`. A budget before box exits/contacts. Longer budgets generally add curve length/stars; joins cannot add budgets together. |
| Curve length variation | Dimensionless, default 0.5, range 0–1. Fixed Beta draws span mean*(1-v) to mean*(1+v); 0 gives equal budgets. Increasing variation shortens some budgets and lengthens others, potentially changing joins/counts. |
| XZ / Y seed region | Fraction of the respective half-extent, 0.65 by default. Smaller values exclude more roots; retained roots keep the same travel. Neither changes the underlying noise curves. No additional randomness. |
| Density support width | Saved `width`, in noise-value units. Controls sampled branch-density support and therefore seed acceptance and density-weighted star population; it does not thicken the exact centerlines. Use shared transverse star scatter for displayed thickness. |

Geometry noise, bounds, resolution or scene-seed edits can rearrange the
source paths/roots. Density remapping, clumping and broad modulation change
seed acceptance and covered intervals on those paths. Edge fade affects only stars. Stars use the shared sampler and
appearance pipeline: less curve length generally means fewer stars. Individual
star positions/colors can resample when paths split/merge or change length; the
stability guarantee for density edits concerns curve shape, not persistent individual
star IDs. Fade-only edits do preserve the individual surviving stars.
Exact pair-zero lines require positive Y extent (minimum 0.01 blocks in this
generator); the previous growth experiment retains its flat-slice heuristic.

Saved-scene check: the former arc-root method produced 40 curves; default rate
500/power 1 accepted 69 blocks and produced 40 curves (about 1.7 seeds per curve).
Power 0 accepted 6557 blocks and produced 131 curves at the same rate. Seed
selection plus projection/growth took about 2.7 seconds in each case, excluding
field extraction, stars and worker startup. No length exceeded its budget.
These are measurements, not an adaptive count target or visual acceptance.

Earlier central-seeding verification on saved seed 1650304426, travel 30 units: reducing both seed
regions from 1 to 0.65 reduced curve length in the outer 20% of the box from
334.9 to 25.8 units and outer stars from 630 to 39. Inner-40% curve length remained
44.89 units. The previous root-budget fade in that comparison is superseded by
star-only fading. Generation plus shared sampling took
about 0.23 seconds for central seeds, excluding worker startup. These are one-scene
measurements, not aesthetic acceptance or an all-settings guarantee. Comparison:
`build/stable-fade-comparison.png`; reproduction: `build/verify_stable_fade.py`.
That older script compares curve generation and raw population only, excluding
the current worker's star-fade stage. Current worker verification on saved seed
714462872: Y fade off / width 0.4 / width 1 produced 1895 / 1589 / 944 stars,
including 265 / 51 / 5 in the outer 20% of Y. All three curve buffers were byte
identical; survivors retained their attributes. Full generation and postprocessing
took about 0.34 seconds, excluding process startup. Visual quality still needs
user judgment.

## Previous density-guided local strands (`density_filament_growth.py`)

Select **Density-guided strands (previous growth)**. This shares
`noise_filaments_branches.build_density` with the direct branch sampler: equal
AB, AC and BC contributions, clump modulation and the three-regime density curve.
There is no Layer continuity or Connectivity control. It traces short curves within
that density, retaining an assigned original pair (AB, AC or BC). Curve and star
visibility remain independent; stars and appearance use the shared pipeline.
Each complete two-way curve has its own bright color, deterministic for the seed
and output path index. Joined curves retain their separate colors so junctions
are easier to inspect. Enable **Use curve colors** in Star population to apply
these colors to stars too. Coloring does not change geometry, sizes or counts.
The XZ and Y half-extents are independent world-unit bounds. Old presets migrate
Y to `extent*y_scale`; initial bounds are XZ 9.458 and Y 2.213172. Frequency 2.505,
width .025, roughness .107, clumping 6.875 and Strand continuity 1 retain the
experiment's earlier defaults. Separate XZ/Y fades use the shared density-fade
helper before seeding and guidance, rather than thinning sampled stars afterward.
Old shared fade settings migrate to both axes. Fade can change roots, curve
lengths and star counts; equal settings reproduce the shared box density taper.
Bounds/remapping/fade introduce no extra random draws. Physical noise wavelength
still follows XZ extent through Frequency. No live settings files are overwritten.

Roots are sampled from the remapped, broadly modulated, edge-faded density.
At each root choose one pair with probability proportional to that pair's local
`exp(-(A*A+B*B)/(2*width*width))` contribution (and its two permutations).
The choice uses independent seed stream 82517. Both halves keep that pair for
their entire lives; filling-mode roots choose their pair when they are born.
The original A/B/C grids are returned from the same density-building call,
without regenerating noise. Their physical gradients are cached once.

In 3D the tangent is `unit(cross(gradient(A), gradient(B)))` for the assigned
pair, oriented toward the previous heading. Normal correction reuses the
regularized pair guidance from `_stochastic_curves.py`:
`correction = J.T * inverse(J*J.T + lambda*I) * [A,B]`, where J contains the two
field gradients. Pull is `-correction/r`, projected transverse to the heading
and capped to unit length. The desired heading combines the pair tangent,
weighted pull, Perlin wandering and same-family neighbor steering. Degenerate
pair gradients retain the heading; they never select another family.
This follows the cached-grid approximation to the original filament with finite
attraction, not a hard projection of every point onto the zero-intersection line.

Perlin steering is 80% shared / 20% per-curve offset, two octaves, roughness .35,
wavelength 4r. Heading response uses `1-exp(-step/r)`. Both halves share a random
total budget `mean_length*(0.5+Beta(2,2))` and begin in opposite directions.
Growth stops at the box, its finite budget, a tenfold decline in smoothed total
density, or a tenfold decline in its assigned pair density from the root.
Another family's density cannot sustain a tip after it leaves its own filament;
an explicit final contact is the only exception to that pair-support check.
There is no spontaneous family switching or child spawning. Junctions arise
when an arriving curve attaches to an existing curve and stops.

For Y half-thickness below r/20, a literal slice may not contain 3D intersection
lines. Each pair then has its own smoothed, Y-averaged XZ density guidance,
using the earlier Hessian method separately for each pair. It never averages
directions across the three families. Heights remain fixed except at a final
contact. The old combined-density tracer remains available to direct helper
callers without `pair_fields`, and `DensityShape` still supports star alignment.

| New curve control | Meaning and effect on stars |
| --- | --- |
| Local strands | 512 density-weighted random starts. More starts generally produce more stars; these are separate short paths, not branches of one graph. |
| Mean total strand length | 2 world units by default, range 0.2-30, total across both directions; random budget is 0.5-1.5 times this value. Longer curves generally produce more stars. Early termination can shorten them. |
| Filament response length | Saved `direction_scale`, 0.3 world units. Heading response length and normalization scale for pair attraction; Perlin wavelength is 4 times this value. Also smooths the density survival envelope and tiny-Y per-pair guidance. Larger slows turns; 3D tangents still come from the original scalar fields. Can change lengths/counts. |
| Pull toward assigned filament | Saved `density_pull`, 0.35, dimensionless. Bounded transverse correction toward the assigned pair's zeros; zero disables correction. Does not switch pairs. Can change paths, survival lengths and counts; independent of star scatter. |
| Curve Perlin steering | 0.15, dimensionless smooth random steering during growth. Zero disables ongoing noise; starts, initial directions and lengths remain stochastic. It can affect final curve lengths/counts. |
| Strand joining reach | 0.6 world units. Only deposited parallel strands of the same pair within this distance steer a growing tip. Zero disables joining entirely. Larger reach can cause earlier joins and fewer stars through shorter paths. |
| Strand joining strength | 1, dimensionless. Amount of neighbor-directed turning. Zero restores independent growth including no contact termination. No new random draws; it changes paths and can shorten them, reducing stars. |
| Strand contact radius | 0.08 world units, capped by joining reach. A tip reaching an existing segment within this 3D distance can attach at any angle or pair and stop. Zero disables contact termination while retaining steering. Larger values usually shorten paths and reduce stars, but can make joins less smooth. |
| Density coverage | 0 retains the original joining method; 1 (default) uses density-proportional capacity; 2 additionally steers and launches later curves into remaining deficits. Modes 1/2 can either increase or reduce total length/stars compared with unconditional joining. |
| Coverage radius | 0.5 world units, Gaussian standard deviation used to compare target density and deposited curve length. Larger compares broader neighborhoods and may blur a narrow bottleneck together with an adjacent blob. It can change curve lengths and star count. |
| Curve capacity multiplier | 1, dimensionless. Total target length is this multiplier times Local strands times Mean strand length. The original density sets relative allocation across space, not an absolute length. Lower values fill sooner and generally shorten curves/reduce stars; higher values allow more material. |

Density capacity/filling uses `_curve_coverage.py`. On a 48-cell grid per active
axis, normalize the original density into target curve-length mass T whose sum
is `capacity_multiplier * strand_count * strand_length`. Boundary vertices have
trapezoidal half weights. Every accepted growth segment deposits its physical
arc length into a trilinear grid; long segments are subdivided so contact snaps
are accounted for along their length too. Gaussian-smooth deposited mass C and
target T with the same physical coverage radius. The local load is `C/T` with a
small numerical floor. This measures material already represented, not the
number of tips arriving or just the number of neighboring curves. Density
normalization means multiplying all source densities by a constant has no effect.

In mode 1, joining strength ramps from zero at load 0.5 to its normal value at
load 1; general junction contact is allowed from load 0.75. Close parallel
duplicates of the same pair can contact at any load: an underfilled density
target must not permit repeated tracing almost on top of an existing strand.
For these contacts, the larger source index yields to the smaller one, retaining
one continuation instead of both tips stopping against each other. Both halves
of a source share its priority. This uses the existing contact radius and 25-degree
parallel criterion; zero contact radius or disabled joining still bypasses it.
Separated strands and crossings in projection are not considered duplicates.
When a proposed
step has load >=1, the tip stops there unless it can actually complete a nearby
contact. It does not inherit or transfer unused length/star budgets. Two
initial steps are allowed so each seed has geometry. Capacity is measured at
finite spatial resolution and refreshed every four growth steps: simultaneous
growth, initial steps and final contact snaps can overshoot, so this is a local
growth limit, not an exact mathematical density constraint. It cannot guarantee
that a low-density bridge stays continuously connected.

Mode 2 uses the same capacity rule, but launches strands in four waves. The first
uses the original density; later waves sample remaining material proportional
to `T*max(1-C/T, .001)` (a tiny fallback prevents an empty sampler). They use a
separate seeded random stream. Ongoing headings also receive a bounded transverse
steering term `coverage_radius * gradient(log(max(1-C/T,.05)))`, clipped to unit
magnitude. This favors underrepresented directions relative to the target,
rather than adding another pull toward its densest peak. Pair-specific
tangents, smooth Perlin steering, heading persistence and finite lifetimes still
operate. Blobs can fill with curved paths where direction is ambiguous; no
explicit vortex/spiral or inter-blob route is imposed. Later waves see earlier
geometry, intentionally making placement depend on what remains to be filled.
It is an approximate filling method, not an optimizer that runs until all
remaining mass is represented. More attempts/longer lengths also raise the target
budget; use the capacity multiplier to adjust that budget independently.

Tests of a weak bridge, a round blob and the saved noise scene showed lower
normalized, smoothed curve-density mismatch with filling, but also more deposited
length than unconditional joining, which had stopped many paths early. This
does not establish visual superiority or equal star counts. Shared density
variation, taper, scatter and later appearance processing can further change
how closely stars reproduce the curve-length density.

Joining acts **during growth** (general junctions remain capacity-gated in modes 1/2); the rejected post-growth overlap-deletion pass
and its controls are no longer used. A global deposited-segment tree refreshes
every four growth steps. Query up to 48 nearest midpoints within joining distance
plus the longest segment's half-length, then choose the closest
eligible segment by exact 3D distance. Eligibility requires a different source
strand (both halves of one's own strand are excluded). Steering additionally
requires the same pair and absolute tangent dot >= cos(25 degrees); final
contact accepts any pair/angle. This bounded search can
miss eligible segments hidden behind many ineligible neighbors.

Checks use local density-grid interpolation. Neighbor steering searches are
skipped at load <=0.5. Contact searches start after two steps; below load 0.75,
only parallel same-pair duplicates with lower source index are eligible.
Coverage gradients are only built for filling mode, and proposed-step capacity
checks interpolate only the scalar load. Field gradients are built once;
coverage still refreshes its small grid every four steps. No new controls.
Before pair guidance, on one fixed saved branch field with 512 starts, median growth times over three
runs changed from 0.62 to 0.56 seconds (coverage off), 0.65 to 0.50 (capacity), and
1.04 to 0.85 (filling), excluding noise construction, stars and process startup.
All three optimized outputs matched the previous path bytes exactly in this
comparison. Timings vary with bounds, strand count, length and early termination.
The initial saved-scene pair-guidance run used 175 paths (62 AB, 56 AC, 57 BC)
and took about 1.18 seconds through the full star pipeline, excluding startup.
The later close-parallel contact correction reduced overlapping arc length
from about 545 to 285 units on a fixed 175-root scene, with total length 966
to 769 units. Measurement uses same-pair segments within the 0.08-unit contact
radius and 25 degrees, including short contact approaches. Growth plus density
took about 1.87 versus 1.83 seconds. All roots remain; fewer duplicate segments
means fewer sampled stars. No completed paths are deleted. A 3D separation
greater than the radius remains even if it looks overlapped in projection.

For nearest projection q, oriented neighbor tangent g, current heading h,
distance d and reach R, define transverse offset `v=(q-x)-h*dot(q-x,h)` and
`j=w*(g-h+2*v/R)`, with `w=(1-d/R)^2*min(1,travelled/R)` inside reach, zero
outside. The ramp avoids abrupt launch steering. Noise and density guidance
still act, and heading response remains smooth. Contact is tested at the proposed
new position against deposited geometry; after at least two growth steps, a
close arrival ends that half on the actual receiving segment. There is
no assigned destination and no deletion of complete curves afterward. All tips
advance together, deposited vertices remain fixed, and unconnected tips retain
their normal random length/density/domain limits. Joining edits can affect other
curves through their changed deposited geometry. Star budgets on shortened paths
are not redistributed; the shared star sampler is unchanged.

Shared Stars per unit length controls along-path count; Spacing randomness
controls longitudinal jitter; Transverse spread is independent star scatter.
Shared tip taper and postprocessing still operate on stars. Native axis density
fade also changes source curves. The tracer has a 200k segment-budget scale, increasing
step size at extreme settings. It does not preserve the density's exact sampling
distribution: finite paths can redistribute material and leave gaps. No claim
of a connected skeleton is made.

## Guided random walks (`guided_walk_filaments.py`)

Select **Guided random-walk filaments** and **Fit cloud**. This is the simpler
one-pass experiment, using the shared Star population/Postprocessing panels and
independent Show curves / Show stars controls. Earlier experiments remain.

Blobs are random best-candidate positions inside a ball, not noise intersections.
Walks leave them in random directions. Additional free filaments start anywhere
in the same ball and grow in two opposite initial directions; the two halves
become one continuous output curve. Blobs can exist solely as attractors with
Walks per blob set to zero, or be absent entirely with Blobs set to zero.

At each .08-unit step the rule is
`h_new = normalize(h + (step/persistence)*(wandering*N(x) + guide_strength*G(x)))`.
The previous heading supplies persistence. N is a vector of three independent
Perlin/Simplex octave fields, sampled directly without gradients or zeros.
Each component mixes 80% shared spatial noise with 20% of a per-curve offset
sample, multiplied by 2 for useful steering amplitude. Nearby walks bend through
a shared landscape while retaining some independent variation.

G is **one** nearby guide, never a sum. Blobs have candidate weight
`(1-distance/blob_radius)^2`. Filaments have weight
`(1-distance/filament_radius)^2 * alignment^2`, and require absolute tangent
alignment above 0.5. One weighted random choice is held briefly, unless it
leaves range or becomes ineligible. The source blob and curves from the same
source group cannot guide a walk. A free-walk draw instead holds no guide for
that interval. A blob guide points toward its center. A filament guide is its
tangent oriented into the current heading's hemisphere, plus transverse offset
divided by influence radius, then normalized. The selected guide's amplitude
is multiplied by the square root of its candidate weight, fading at the cutoff.

Reaching another blob's capture radius snaps the last point locally to its
center and ends that direction of growth. Following a filament neither snaps
nor ends growth; noise can peel it away again. All tips advance in batches.
There are no assigned destinations, repeated growth passes, reinforcement, or
pruning during growth. Output selection happens afterward: by default, keep
the shortest discovered route per unordered blob pair, reject routes whose
arc length exceeds twice their endpoint distance, and keep up to four open
paths (preferring free starts, then smaller detours). No links are invented.
Selected paths receive Gaussian smoothing over 0.2 units of arc length with
exact endpoint preservation, before Y compression. Output mode 0 retains all
raw walks. Selection improves readability but does not guarantee connectivity.

| Curve generation control | Meaning and default |
| --- | --- |
| Starting region radius | 6 pre-compression units, enclosing blob and free-start positions. Growth can leave it. |
| Blobs | 10 attractor positions. Zero allows entirely source-free scenes. |
| Walks per blob | 5 independent random-heading walks per blob. Zero leaves blobs as attractors only. |
| Free filaments (two-way) | 15 free starts, each growing in two directions and returned as one curve. |
| Mean filament length | 16 units before compression/capture. A free filament splits its mean budget equally between its two halves. |
| Length variation | 0.6; each budget is mean times `1-v+2v*Beta(2,2)`. Zero gives equal budgets; larger values spread endpoints. Free halves draw independently. |
| Noise type | 0 Perlin, 1 OpenSimplex2S, for all vector components. |
| Noise scale | 3 units; larger produces more gradual spatial changes. |
| Noise octaves | 2; each successive layer doubles frequency. |
| Noise roughness | 0.35; amplitude multiplier for successive octave layers. |
| Noise steering strength | 0.7; amount of noise-induced turning. Zero removes it. |
| Heading persistence | 0.8 units; larger means slower response to noise and guides. |
| Local guide strength | 2.5; amount of steering from the single selected guide. Zero gives free walks, though accidental blob capture can still happen. |
| Blob influence radius | 3 units; blobs outside this radius exert no steering. Zero disables blob guidance. |
| Filament influence radius | 1 unit; cutoff for local filament following. Zero disables it. |
| Blob capture radius | 0.18 units; reaching another blob this closely terminates that half/walk. Zero disables capture. |
| Guide hold distance | 1.5 travelled units before reconsidering a valid guide. This is not time; a vanished/ineligible guide is reconsidered immediately. |
| Free-walk probability | 0.2 at each new selection. Holds no guide for the hold distance, preserving exploration. One means all motion is unguided. |
| Output | 1 selects centerlines after growth; 0 displays every exploratory walk. Selection changes total curve length and therefore star count. |
| Maximum length / endpoint distance | 2, dimensionless, measured before Y compression. Rejects winding routes above this ratio; smaller values keep fewer curves/stars. Used only in output mode 1. |
| Open centerlines to keep | Cap of 4 nonconnecting paths in output mode 1. Increasing it permits more curves/stars; it adds no randomness to growth. |
| Y scale fraction | 0.35; compresses finished curves and blob positions vertically. |
| Blob markers | On; preview rings only, excluded from star population. |

Length/count controls directly affect total star candidates; other geometry
controls can change arc length and early captures, affecting star counts
indirectly. Marker visibility leaves stars unchanged. Star density along paths
and transverse scatter remain in the shared population panel. At least one
blob-launched walk or free filament is required.

A single segment tree is rebuilt every eight steps. Queries examine 24 nearby
midpoints, then measure exact segment distances, filter candidates, and retain
one candidate per curve. This is a bounded approximate search; eligible guides
may be missed among many excluded segments. A total 160,000 candidate-step cap
can shorten extreme settings. Typical default growth was about 0.6 seconds for
65 exploratory filaments on two tested seeds, excluding selection, worker startup/star sampling.

Show curves / Show stars apply to generators with both curve and population
layers. Single-layer point or curve scripts always display their primary output,
so hiding stars while inspecting curves cannot hide an older point-only script.

## Emergent local network (`emergent_filaments.py`)

Select **Emergent filament network** (`emergent_filaments.py`) and **Fit cloud**.
This is a separate iterative experiment with the shared Star population and
Postprocessing panels, plus independent Show curves / Show stars controls.
There is no chosen blob adjacency, spanning tree, or fixed destination endpoint.
The abandoned preconnected relaxation experiment was removed.

Initial curves grow freely from verified triple-noise seeds, with one or two
random initial pair families per blob. They retain the existing finite soft
pair-zero attraction and gradient-cross tangent guidance; they do not trace an
extracted graph. In this script, wandering is a three-component spatial fBm
field with independent per-curve offsets, using the selected Perlin/Simplex type.
Lengths use bounded Beta(2,2) variation from 40% to 160% of the selected mean.

For a nearby segment from a different blob, orient its unit tangent t into the
growing heading h's hemisphere. It contributes only when `abs(dot(t,h)) > 0.5`
and distance d is below interaction radius R. With transverse offset delta,
the steering contribution is
`(1-d/R)^2 * dot(t,h)^2 * (delta/R + 0.5*(t-h))`.
One nearest aligned candidate per other source blob contributes; the summed
force is capped to unit magnitude before applying corridor strength. Own-source
curves are excluded so merely launching a dense bundle does not reinforce itself.
This is a local heuristic, not physical gravity or a global connectivity solver.

After a minimum travel of 2R, a tip inside the join radius of another blob or
aligned deposited segment attaches locally and stops. Segment indices refresh
every eight growth steps; four midpoint candidates per other blob are checked
with exact point-to-segment distances. Detection is therefore approximate.
Later passes regrow from the same starts and random draws. Prior curves that
participated in contacts have memory weight 1; unsuccessful exploration has
weight 0.1. Memory affects steering only: actual attachments always use current
geometry. Receiving curves with no onward connection are trimmed after their
last incoming attachment. Unconnected curves are then probabilistically thinned,
while contact targets are always preserved. At least one curve remains if no
connection or survivor was found. No explicit mid-curve branch spawning yet.

| Curve generation control | Meaning and default |
| --- | --- |
| Seed region extent | Half-extent of seed search box before Y compression, 6 units. Changes root positions and geometry. |
| Seed blobs | Up to 10 verified triple-noise roots. More roots provide more potential local encounters; no connections are guaranteed. |
| Max curves / direction | 4 candidate copies per selected direction, with stochastic uneven counts. More exploration and potential stars. |
| Noise fields | 3 scalar geometry fields, selectable up to 4. Defines possible initial pair families. |
| Noise type | 0 Perlin, 1 OpenSimplex2S; applies to guidance and wandering. |
| Noise frequency | 1.5; base landscape scale is extent/frequency. Larger gives smaller structures. |
| Detail octaves | 1; each added octave doubles frequency. |
| Detail strength | 0.2; amplitude multiplier for each successive geometry octave. |
| Mean exploration length | 18 pre-compression units. Random finite travel budget, ending sooner on contact. |
| Noise attraction | 1.2; coefficient of normal correction toward the active pair's zero intersection. Zero removes this pull, but retains tangent guidance. |
| Noise wandering strength | 0.3; transverse random steering amplitude. Zero disables it. |
| Wandering scale | 2 units; larger makes independent wandering vary more slowly through space. Two octaves with gain 0.35. |
| Turn response length | 0.35 units; distance over which heading adjusts, not finished-curve smoothing. |
| Local interaction radius | R=0.8 units; strict cutoff for filament attraction/alignment. Larger enables interaction across wider gaps. |
| Local corridor attraction | 2; multiplier on local steering from other source blobs. Zero disables corridor forces, while local joins can still occur. |
| Local join radius | 0.12 units; proximity needed to attach a tip locally. Zero disables all joins. There is no distant target steering. |
| Growth passes | 3; repeated growth with local memory. More passes cost time and do not guarantee improvement. |
| Previous-pass reinforcement | 0.8; multiplier on the memory's local force. Zero omits memory and evaluates only one pass, since subsequent passes would repeat. |
| Unconnected curve survival | 0.2; independent probability of retaining a curve with no contact. Zero keeps only contacted curves, subject to the nonempty fallback. |
| Y scale fraction | 0.35; compresses the completed geometry vertically. Distances above are measured beforehand. |
| Seed markers | On; preview rings only, never populated with stars. |

Geometry controls can change total path length, contacts and thus star counts.
Only seed markers leave populated stars exactly unchanged. None of these
controls sets transverse star scatter or along-curve star density: use the
shared Star population panel. A total 160,000 candidate-step budget across all
passes bounds runtime; extreme combinations can truncate exploration early.
The initial spatially separated seed selection remains, so isolated components
are expected. This experiment does not guarantee a connected galactic web.

## Smooth stochastic bundles (`stochastic_filaments.py`)

Select **stochastic_filaments.py** and **Fit cloud**. **Curve generation** controls
the trajectories, and **Star population** places stars along them. The
exact-intersection and original free-growth experiments remain available.
Under **Display**, **Show curves** and **Show stars** independently toggle the
two layers immediately, without regeneration. These choices are saved.

Population density is stars per unit of displayed curve length, after Y
compression. Samples follow a normalized 1D density along arc length, with
independent Gaussian scatter in the local normal plane. Each curve receives
stars independently, so overlapping bundles naturally have more stars.
**Tip taper fraction** sets the final fraction of each curve where survival falls
smoothly to zero: `t*t*(3-2*t)`, with `t` the remaining distance divided by taper
length. This removes stars without shortening the curves or moving survivors.
**Curve density variation** gives each curve its own mean density:
`D_i = D * (1 + v*(2*U_i-1))`, with a separate seeded uniform draw per curve.
At v=0 all curves use the base D. The default v=0.5 gives densities from 0.5D to
1.5D. This changes candidate counts; the mean is D across random draws, but the
total for a particular collection of curves is not fixed.

**Along-curve density variation** replaces the previous Clump strength thinning.
Local density is `D_i * exp(A*f(s)) / mean(exp(A*f(s)))`, where `s` is arc length
and `f` is 1D gradient octave noise. Each curve has independent noise;
world position does not affect it. Inverse cumulative-density sampling places a
fixed number of candidates, so density variation redistributes rather than
removes stars. Numerical integration uses 32 cells per finest scale, capped at
262,144 per curve for unusually long paths. Taper runs afterward: moving density
into the tip can still reduce the final surviving count.

| Star population parameter | Meaning |
| --- | --- |
| Stars per unit length | Base candidate density; range 0â€“10, default 4, before curve multipliers and taper/postprocessing. |
| Curve density variation | Spread of mean densities between curves, 0â€“0.95, default 0.5. Each gets a multiplier uniformly between 1-v and 1+v. Changes candidate counts. |
| Along-curve density variation | Exponential noise contrast A, 0â€“6, default 0. Zero is uniform along a curve. Does not change that curve's candidate count. |
| Density noise scale | Base noise lattice spacing in arc-length units, default 1. Larger values give broader density variations. |
| Density noise octaves | Number of frequency layers, 1â€“6, default 3. Each additional layer has twice the frequency. |
| Density noise roughness | Amplitude multiplier between layers, 0â€“1, default 0.5. Zero keeps only the first layer; 1 gives equal amplitudes. The sum is amplitude-normalized. |
| Spacing randomness | Jitter within equal-probability intervals, 0â€“1, default 0.8. Zero gives regular spacing at uniform density, or regularly spaced density quantiles with variation enabled. One randomizes within each interval. |
| Transverse spread XZ / Y | Independent horizontal/vertical Gaussian spread scales, each default 0.035 generator units, range 0–0.5. Larger values widen scatter in the respective directions. Offsets stay perpendicular to the curve: on sloping curves the actual component deviations depend on tangent direction. Zero Y adds no vertical scatter; both zero stay on the curve. Equal values reproduce the former isotropic spread exactly. Continuous candidate count is unchanged; block occupancy and subsequent fading can change final counts. |
| Tip taper fraction | Final fraction of each path subject to smooth survival falloff, default 0.3. Zero disables thinning; curves remain full length. |
| Star size | Base cube side length or point diameter, default 0.04 world units, before the Display multiplier. |
| Size variation | Uniform relative size variation, default 0.4 gives 60%â€“140% of base size. Independent of positions/count. |
| Use curve colors | Inherit source curve colors when enabled; otherwise pale blue. Postprocessing can override colors. |

Both spread controls apply to continuous and block sampling, before warp, and
do not change source geometry, along-curve sampling or material assignment.
Old `pop_spread` presets migrate to the same value on both axes; explicitly set
new axis values take precedence. The Gaussian has unbounded tails as before.

The old saved clump-strength/scale keys retain their values under the new density
labels. Outlier frequency/width controls have not been added; such controls belong
in the population stage while local curve directions are available.
Candidate counts are capped at one million, reducing density with a panel notice
when needed. Zero density leaves a valid curve-only view.

The existing **Postprocessing** panel operates on populated stars only. Warp and
sparse alignment can move them away from the displayed source curves. Population
edits currently rerun the deterministic generator, reproducing the same curves;
visibility edits only affect rendering.

Each seed blob is centered on a verified triple-zero junction. **Noise fields**
is configurable from 3 to 4 (default 3) in this generator. Three fields allow ABC
junctions; four allow ABC, ABD, ACD and BCD junctions. All triple families are
eligible, including ones that do not contain AB. Four independent scalar zero
surfaces do not generally meet at one point in 3D, so four-field junctions are
not required. The separate exact-intersection preview still supports two fields.

**Seed pairing bias** (0â€“1, default 1, dimensionless) favors dense arms along
existing noise-zero routes between selected blobs. The initialization graph is
walked separately for each field pair until another selected seed, a boundary,
or a loop. Merely sharing the AB label or being spatially close is insufficient:
the seeds must lie on the same connected AB strand in the sampled box. Each
route records the outgoing direction at both ends and its arc length L.

Shorter routes receive higher randomized priority, with at most two busy pair
families per blob. At full bias, both ends share a seeded launch probability
`0.65 + 0.3/(1+L/noise_scale)` and the same per-copy draws, guaranteeing at least
one launch at each end before the global curve cap. Opposite unpaired arms accept
only 10% of copies. A blob with no selected route keeps one sparse exploratory
pair and at least one launch; a lone seed retains the original launch behavior.
Counts remain unequal between different routes and directions. This control can
change initial curve counts, subsequent branches, and total stars; it does not
change star density per length or transverse scatter.

Zero restores the earlier independent plans exactly: a random primary pair
accepts each direction with probability 0.5â€“1, and an optional secondary pair
uses 0â€“0.5. Intermediate bias mixes independent and paired launch decisions,
still limiting each blob to two initial pair families. Later branching may
introduce other pairs. Graph routes only influence launch allocation: no edges,
target forces, prescribed connections, or extra travel budgets are added.
Finite, wandering trajectories may still fail to reach the neighboring seed.
Spatially separated seed selection can produce no shared routes at all; routes
outside the sampled box are not detected. This is not a connectivity guarantee.

**Max curves / direction** (same `curves_per_seed` saved key, default 6, range
1â€“16) caps the initial trajectories in each direction; it no longer fills every
arm to that number. Actual counts vary between blobs, pairs and directions, so
this setting affects geometry and total stars indirectly. Increasing the cap
extends each blob's existing seeded launch plan. With
repulsion disabled, earlier trajectories stay unchanged until the curve limit
applies; with repulsion enabled, extra curves can steer existing neighbors.
Curves are retained even when they overlap. **Starting spread** offsets their
birth positions in the normal plane around the seed. Roots are initialized from
noise-zero junctions from the tetrahedral graph and refined against their three
continuous scalar fields. Invalid candidates are rejected before choosing
spatially separated seeds. If none can be found, generation reports an error
rather than substituting ordinary pair intersections. The extracted graph is
used to locate roots and allocate paired launch density, never to prescribe
the growing trajectories. Starting spread still
gives individual trajectories offsets around the junction-centered blob.

**Mean curve length** and **Length variation** give every trajectory its own finite
travel budget. The default variation is 0.6: root lengths range from 40% to 160%
of the mean, with more lengths near the middle. A bounded Beta(2,2) distribution
gives the bundle a smoothstep-shaped expected falloff in surviving root curves,
rather than a shared cutoff. Zero variation restores equal-length roots.
Length randomness uses a separate stream, so changing these controls preserves
the shared earlier portions of each trajectory when repulsion is disabled.
With repulsion enabled, neighbors stopping at different times can change later
motion. Branches get their own randomized
fraction of the parent's remaining budget, never exceeding it. Branches can add
local density along a bundle, so the complete branched network need not thin
monotonically. This is a taper in curve population; the star population's tip
taper can additionally soften each individual tip.

At each step, direct Perlin or OpenSimplex2S samples give scalar values and
central-difference gradients. The cross product of the active pair's gradients
gives the local tangent. A regularized normal correction pulls toward its zero
intersection: `J.T @ inverse(J @ J.T + lambda*I) @ (A, B)`, where J contains the
two gradient rows. This scales the attraction to approximately world-space
distance rather than making it depend strongly on noise-gradient magnitude.
It is a finite steering influence, not a projection or exact zero constraint.

**Attraction strength** is the base coefficient A. **Attraction variation**
(0â€“1, default 0.9) assigns each curve a fixed coefficient
`A_i = A * (1-v*U_i^3)` from a separate seeded uniform draw. This keeps most curves
near the base, with a smaller tail of weakly attracted curves. At v=0 all use A;
at v=0.9 strengths span 0.1A to A; at v=1 they can approach zero. Children get
their own draw rather than inheriting the parent's strength. This changes
geometry and may indirectly change branch encounters/star counts; it does not
change transverse star scatter or directly thin stars.

Two optional multipliers vary attraction as a curve grows:
`A_effective(x) = A_i * (1-b*dÂ²/(dÂ²+RÂ²)) * (1+c*tanh(3*N(x)))`.
Here d is straight-line distance from the original source blob, before Y
compression; descendants retain that source rather than resetting at a branch.
N is a separately seeded spatial fBm field using the selected Perlin/Simplex
algorithm. It is shared by nearby curves, independent of the geometry fields,
and does not introduce additional zero-surface junctions.

| Control | Meaning |
| --- | --- |
| Seed-distance attraction effect | b, default 0, range -1 to 1. Positive weakens attraction outward; negative strengthens it. Far away the multiplier approaches 1-b. |
| Attraction distance scale (units) | R, default 4. Distance at which half of the distance effect is reached. |
| Attraction noise strength | c, default 0, range 0 to 1. Multiplier lies between 1-c and 1+c; zero disables this field. The tanh mapping increases contrast while keeping attraction nonnegative. |
| Attraction noise scale (units) | Default 3. Larger values produce broader regions of strong/weak attraction. |
| Attraction noise octaves | Default 3, range 1 to 5. Each extra octave adds variation at twice the frequency. |
| Attraction noise roughness | Default 0.5, range 0 to 1. Each octave's amplitude relative to the previous one. Zero leaves only the first octave. |

Both effect amounts default to zero, preserving prior behavior exactly. They can
be compared separately or multiplied together. The same modulation is included
in branch route predictions. These controls alter steering, not path budgets or
star scatter; changed branch encounters can indirectly change total star count.
Distance is spatial, not distance travelled: a curve returning toward its seed
regains its original attraction multiplier.

The desired heading combines that tangent, negative per-curve attraction times
the correction, and each curve's smooth random steering. Random steering is a
sum of three sine modes with independent random amplitudes/phases per curve.
**Wandering strength** widens/deforms bundles; **Wandering length** makes those
deviations persist over longer distances. **Turn response length** (previously
Turn smoothing; same saved `smoothness` key, default 0.25 units) sets the travel
distance over which a growing curve's heading responds. Each step uses
`blend = 1-exp(-step/response_length)` before normalizing the blended direction.
It does not smooth an already generated polyline. Larger values soften turns but can make paths
lag tight bends and drift farther from a strand. Default one-octave fields,
continuous sampling, and gradual turning remove the old tetrahedral guide
corners without smoothing away branch attachments afterward.

**Curve repulsion** adds gentle sideways steering away from nearby segments of
other curves, including already completed portions. Default strength is 0.15
(range 0â€“1); it is dimensionless relative to the unit tangent. Zero disables it.
**Repulsion reach** is the cutoff distance, default 0.2 units (range 0.03â€“0.6),
measured before Y compression. Larger reach spreads influence over a wider area;
neither control directly changes star density or transverse star scatter.

For distance `d < reach`, each neighboring curve contributes an away vector with
weight `(1-d/reach)^2`. Only its nearest encountered segment contributes, so extra
vertices on a curve do not multiply its influence. The summed force is projected
perpendicular to the current noise tangent and capped at unit magnitude before
the strength multiplier. Near zero distance, a soft denominator avoids a singular
force; exact overlaps use a separate seeded direction. Repulsion ramps in over
the first `2*reach` of each path and passes through turn response. Existing
vertices and branch attachments never move. This is soft separation, not a hard
collision constraint or guaranteed gap. Y compression can reduce displayed gaps.

For interactive speed, a spatial index examines up to 64 nearby segment candidates
from each of its older/recent batches per tip. This is a local approximation in
very dense bundles. Repulsion changes trajectories and potentially branch
encounters, so final curve/star counts can change indirectly. Travel budgets and
the shared population/postprocessing pipeline are unchanged.

**Branch encounter width** defines a neighborhood around a third zero surface,
using `abs(C)/length(gradient(C))` as a local distance estimate. When a trajectory
enters that band while near its current pair, **Branch probability / encounter**
can create a child following one alternative pair. Hysteresis and a minimum
travel cooldown prevent retriggering at every integration step. Children start
at the parent's exact position, but their initial heading follows their selected
pair's tangent, oriented into the parent's forward hemisphere. Branch departure
is chosen independently of turn response: a fork can have an immediate angle,
while subsequent turns along each path remain smooth. Weak/degenerate gradients
can fall back to the parent heading. Their lengths are bounded by the parent's remaining travel;
depth is limited to three
branch generations. There is no forced snapping or guarantee of global joins.

**Branch divergence preference** (0â€“1, default 0.8) changes which alternative
pair is selected. At zero, both alternatives have equal chance. At larger values,
short predicted routes favor separation from the parent's continuation. Twelve
probe steps use the same attraction and turn response, but omit wandering and
repulsion. The horizon is `min(child_remaining, max(1, min(3*response_length,
base_noise_scale)))`, in world units before Y compression. Scores are mean
distance from the parent probe divided by the horizon. Selection probabilities
mix uniform choice with `softmax(8*score)`, using the preference as the mixing
weight. Even at 1 the choice is stochastic. Similar underlying noise routes can
still stay close or rejoin; no artificial connecting or separating geometry is
added. This control can indirectly affect later branching and star counts.

**Maximum curves** includes the initial trajectories and branches. Initial launches
are allocated round-robin, giving every selected blob one trajectory before
adding more. If the budget cannot fit one curve per requested blob, fewer blobs
are selected; remaining slots are available for later branches.
A separate
440,000-segment safety budget stops growth before the transfer limit; extreme
settings can therefore stop short of the sampled length. **Mean curve length**,
widths and smoothing are measured before the complete result is compressed by
**Y scale fraction**. The seed-region box does not clip growing paths: the noise
continues outside it. Field-pair coloring and seed-marker toggles leave the paths
unchanged. The star count has no effect on this curve preview.

## Other experiments

An earlier direction retains the noise-sampled cloud and gently aligns nearby stars
with guide curves in `noise_filaments_aligned.py`. The explicit-curve population
and bundling experiment remains in `noise_filament_curves.py` for comparison.
Further density cleanup or curve editing can be added as separate stages.
Artistic appearance takes priority over physical realism.

Compare the Zel'dovich experiment with those noise-based approaches. Possible
follow-ups are particle-mesh gravity, which recomputes forces as particles move,
or adhesion-style evolution to retain converging structures. These require a
different evolution model; subdividing the fixed Zel'dovich displacement will
not provide that behavior. Neither follow-up is implemented yet.

## Writing a generator

The baseline for new patterns is **curve generation -> shared star population ->
shared postprocessing**. Most new experiments should replace only curve generation,
keeping the same star sampler and appearance controls. The current reference is
`generators/stochastic_filaments.py`; its noise guidance is one choice of curve
algorithm, not a requirement of the pipeline.

Add a `.py` generator with `PRIMITIVE = "lines"` and
`generate_population_source(count, seed, **params)`. Return
`(line_attributes, paths, path_colors)`: preview endpoint attributes, ordered
polylines, and one RGB color per path. Exclude seed markers and other preview
decorations from `paths`. Retain a `generate` wrapper returning `line_attributes`.
The worker supplies the Star population panel through `_population.py`, followed
by the shared Postprocessing panel. Curves and stars remain independently visible.
Keep reusable changes to star placement in that shared stage so every new curve
pattern benefits from them.

Earlier direct-star generators remain supported for comparison. Their interface
is illustrated below:

```python
import numpy as np

NAME = "Gaussian cloud"
PARAMETERS = [
    dict(key="scale", label="Scale", type="float", default=3.0, min=0.1, max=20.0),
]

def generate(count, seed, scale=3.0):
    rng = np.random.default_rng(seed)
    positions = rng.normal(0, scale, (count, 3))
    colors = np.full((count, 3), [0.7, 0.8, 1.0])
    sizes = rng.uniform(0.02, 0.06, count)
    return positions, colors, sizes
```

Return XYZ positions and RGB colors in `[0, 1]`, both shaped `(count, 3)`, plus
an array of world-space sizes shaped `(count,)` (or one scalar for all stars).
Size is the cube's side length or point's diameter, before the display multiplier;
it must be finite and in `(0, 1000]`. Existing scripts returning only positions
and colors still work, receiving a default size of `0.04` per star.
The bridge validates finiteness, shapes, colors, sizes and coordinates, then converts to
contiguous float32 data. `PARAMETERS` supports `float` and `int`, with unique keys,
labels, defaults and bounds; values are clamped to the current schema on reload.
Use NumPy operations over whole arrays rather than a Python loop per star. A seed
should reproduce the same cloud. Keep imports free of expensive generation work.
Put shared helpers in files beginning with `_` so they are not listed as patterns.

These are ordinary local Python scripts with your user's permissions, not a
sandbox. The separate process isolates failures and allows cancellation; it does
not restrict filesystem or network access. A job is stopped after 60 seconds.
The math modules have no renderer dependency and can also be imported from a
notebook, tests, or a future Minecraft exporter.

## Controls

Choose **Drag / orbit** or **First person** in the Camera dropdown, or press **F**.
Switching modes preserves your position and viewing direction. First-person mode
captures the mouse: moving it looks around without holding a button. **Tab**
releases/recaptures it and **Esc** releases it for GUI interaction. Click the scene
to recapture. Switching away from the app releases the mouse; returning does not
automatically recapture it. Movement pauses while the first-person cursor is free.
Adjust **Sensitivity** and **Move speed** in the GUI. Movement speed is independent
of orbit distance. The wheel only zooms in drag mode. Default sensitivity is 0.10
(previously 0.15).

Hold the **right mouse button** over the scene (or in captured first-person mode)
to zoom in by narrowing the field of view. Release it to restore normal FOV.
**Right-click zoom** sets magnification from 1â€“10Ã—, default 3Ã—. Camera position
stays fixed, and look/pan sensitivity scales down while zoomed. Right-drag look
in orbit mode is replaced by this zoom control; use first-person mode to look around.

Sensitivity, movement speed, zoom factor, and camera mode save automatically to
`config/controls.ini` and are restored on the next run. Restored
first-person mode starts with the mouse free; click the scene or press Tab to
capture it. Plot/display settings and camera position are saved in `config/plot.json`.

| Input | Action |
| --- | --- |
| F | Switch camera mode |
| G | Regenerate current script with a new random seed |
| Mouse movement (first person) | Look around while captured |
| Tab / Esc (first person) | Toggle capture / release mouse |
| Left drag (drag mode) | Orbit around target |
| Middle drag (drag mode) | Pan |
| Hold right mouse | Narrow FOV to zoom; release to restore |
| Wheel (drag mode) | Zoom toward/away from target |
| WASD | Move forward/back/left/right |
| Space / E | Move up |
| Shift / Q | Move down (either Shift key) |
| R | Reset camera |
| Esc (drag mode) | Quit |

ImGui captures its own mouse and keyboard interactions. **Display â†’ Draw as**
switches between **Shaded cubes** (default) and **Points (fast)**. Cubes have
fixed block-style face shading and depth testing to distinguish
overlaps. Top faces retain full color; north/south faces use 92% brightness,
east/west 82%, and bottom faces 85%. Opposite horizontal faces match, with no
directional light or edge outlines. They are world-aligned; material proxies
can supply different X/Y/Z dimensions. A small center crosshair stays visible in both camera modes.
Points can be
round or square. **Star size scale** multiplies each star's own size without
regeneration; axes, background color, and VSync are also adjustable.

Both modes have perspective: a star at twice the camera depth has approximately
half the pixel diameter. In point mode, sizes are clamped to the GPU's supported
point size range (typically at least one pixel), so extremely distant stars stop
shrinking at the minimum. Cubes use real geometry and have no point-size clamp.
The GUI supports
1,000â€“1,000,000 stars. The generator protocol also accepts smaller clouds for tests.

## Data and rendering

`src/point.h` defines `Point { position, color, size, shape }`.
`src/point_renderer.h` owns GPU buffers/shaders and accepts any `std::vector<Point>`.
`src/generation.cpp` handles background jobs, cancellation and validated binary
transfer; `src/generator_panel.h` handles discovery, sliders and file watching.
`python/worker.py` loads the independent modules in `generators/`.
Each star occupies 40 bytes on the GPU (three vec3s and one float). Shape defaults
to (1,1,1); cuboid dimensions are size times shape. Points use the largest dimension.
Generators may declare `PRIMITIVE = "lines"` to return independent endpoint pairs
in the same buffer format. Their output has a geometry-controlled even vertex
count (2 to 1,000,000); `count` remains the requested star budget and can be ignored.
The worker validates each vertex, omits shared star postprocessing on curves, and returns
`primitive: "lines"` in the catalog and successful response metadata. The viewer
uses `GL_LINES` for that uploaded buffer, preserving separate curve boundaries.
Omitting `PRIMITIVE` retains the existing point/count contract and legacy returns.
Line generators can additionally expose `generate_population_source(count, seed,
**params)`, returning `(line_attributes, paths, path_colors)`. Paths are ordered
polylines without preview decorations; colors have shape `(len(paths), 3)`.
The worker appends shared `pop_` controls and a Star population section, samples
the paths, then applies shared appearance processors to the star layer. Both
`pp_` and `pop_` parameter prefixes are reserved. `population: true` in the
catalog and response enables the second layer in the viewer.
Data uploads happen only when replaced. The entire cloud uses one instanced cube
draw call or one GL_POINTS draw call per frame, with depth testing and no per-star
CPU work during drawing. Both modes share the same star buffer, so switching
does not regenerate or re-upload it. Cubes reuse one 12-triangle mesh; they cost
more GPU work than points, especially at high counts.

`src/camera.h` contains the orbit/fly camera and projection. The current demo uses
single-precision coordinates and a fixed 0.01â€“10,000 clipping range. Very large
world coordinates, file loading, picking, streaming, and level of detail are
future work. The sample count range is not a performance guarantee; GPU speed,
point size, and overlapping points all affect frame time.

The transfer file is a 16-byte header (`FSTAR002`, then a little-endian uint64
count), followed by `count` interleaved XYZ/RGB/size float32 records. JSON is used only
for small parameter/schema messages. Populated curve jobs use `points.bin` for
lines and `points.stars.bin` for stars, with the same binary layout. Only the star
sidecar may have zero records; response `star_count` must match it. Both buffers
must validate before the viewer replaces either layer.
Block material proxies use `FSTAR003` with the same header and ten floats per
record: XYZ/RGB/size followed by three positive dimension multipliers in (0,1].
The viewer reads both formats and supplies shape (1,1,1) for FSTAR002. An older
viewer cannot read the proxy format and retains its prior cloud on that error.
Each job uses its own temporary directory,
cleaned after completion. The viewer reuses one Python subprocess across completed
requests, keeping imports warm. It waits on stdin while idle. A source-file change
(including helpers), cancellation, timeout or process failure discards the worker;
the next request starts a fresh process. The native job object kills descendants
when the worker closes. Requests remain serialized and latest-request-wins, with
no embedded interpreter/GIL integration or per-frame Python calls. Standalone
`runGeneration` and the one-shot worker CLI retain fresh-process operation.

Cell population now groups occupied XYZ cells through lexicographically packed
integer keys, retaining the previous cell ordering, mass sums and random draws.
Very wide integer domains fall back to the previous axis-wise union. Probe counts,
seed rates and field resolution are not reduced for speed. Warm native generation
on the 85-root scene is approximately .9s including request transfer and buffer
loading, with occasional runs around 1.02s under background viewer load. Cold
startup still costs roughly two seconds; this is not a universal subsecond bound.
Worker reuse needs the rebuilt viewer; Python geometry changes alone reload live.

## Validation

CPU-only tests (no viewer window):

```powershell
.\.tools\cmake-3.31.6-windows-x86_64\bin\ctest.exe --test-dir build/Release -E 'renderer_smoke|point_perspective' --output-on-failure
.\build\Release\generation_test.exe --benchmark
```

These cover deterministic generation, per-star sizes, array validation, binary parsing, settings,
windowless generator-panel startup with default and restored settings,
script discovery/reload/repair, missing interpreters, stale-job cancellation, and
timeouts. `scripts/build.ps1 -Test` also runs a hidden GPU test comparing the
pixel footprints of stars at different depths/sizes, cube face shading, instancing,
and overlap depth, and the GPU smoke test below.

The smoke test creates a hidden native OpenGL context, compiles the GLSL 330
shaders, checks the loading frames before a star buffer exists, draws 100,000 stars,
exercises camera movements and window resize,
checks mouse capture/release, focus loss, and jump-free mouse recapture, checks
scene pixels before drawing the GUI, and checks for OpenGL errors.
It writes `smoke.ppm` in the test working directory for visual inspection.
It needs a graphical Windows session and a working GPU driver.

## Pinned dependencies

| Component | Version |
| --- | --- |
| Application graphics API | OpenGL 3.3 core / GLSL 330 |
| GLFW | 3.4 |
| GLM | 1.0.1 |
| Dear ImGui | 1.91.9b |
| GLAD | 0.1.35-generated OpenGL 3.3 core loader from Ising |
| LLVM-MinGW (Clang/UCRT x64) | 20250305 |
| CMake | 3.31.6 |
| Ninja | 1.12.1 |
| nlohmann/json | 3.11.3 |
| Python | 3.10+ (configured interpreter) |
| NumPy | 1.24â€“2.x |

Graphics-library revisions are pinned by commit in CMakeLists.txt; the JSON
library uses a versioned release archive. The GLAD generated
source is vendored with its license; other licenses accompany fetched sources.
The local `.reference/ising` checkout is ignored and is not a build dependency.

The GPU driver may report OpenGL 4.x when asked for a 3.3 context. That is normal:
this application only loads and uses the OpenGL 3.3 API and GLSL 330 shaders.

For another C++ toolchain, use ordinary CMake commands instead of the Windows
bootstrap script. The CMake project also supports MSVC if its C++ workload is
installed. The subprocess bridge currently uses Windows APIs; porting it is
required before building the viewer on Linux/macOS. The Python math is portable.
