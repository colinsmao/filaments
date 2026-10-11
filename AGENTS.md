# Continuing this project

Read this file and `README.md` before changing the project. This is a handoff of
the current implementation, not a commitment to continue any particular experiment.

## Purpose and user preferences

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

- `density_filament_curves.py` / `_density_curves.py`: current local-alignment
  experiment, reusing the actual `noise_filaments.build_density` (including
  layer/clump modulation). Density-sampled roots grow short two-way strands.
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
  buffer. Both use FSTAR002; only the sidecar allows zero records. The viewer
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
- `noise_filaments_branches.py`: unions several pairwise intersections; preserved
  but visually busy. `layer_filaments.py`: anisotropic 3D Voronoi-edge experiment.
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

`generators/_appearance.py` owns the shared schemas and operations. All three
experiments default off. Settings may enable them in the user's saved preset.

1. Sparse curves: identify sparse stars by eighth-neighbor distance, choose random
   spatially separated anchors, use local PCA directions to build sinusoidal
   guides, and attract nearby sparse stars with smooth falloff. Optional guide
   colors do not change positions. No guarantee of connectivity or uniform filling.
2. Merge dense stars: randomly oriented bounded bins combine nearby dense stars.
   Use volume-weighted centroids/colors and cube-root summed size-cubed. This
   preserves star volume and avoids transitive merging of whole filaments.
3. Warp: mode 0 is a global swirl about world Y, theta = angle/(1+(r/radius)Â²),
   preserving height and horizontal radius. Mode 1 retains the earlier sum of
   transverse sine waves. Swirl bends structures; it does not attract stars onto
   spiral ridges. All stars participate, with no motion on the rotation axis.

Order: sparse alignment, merge, warp, point-stage fade. Warp intentionally runs
after guide assignment/merging: the previous order regenerated guides and colors
when warp changed, making even small changes look like an entirely new pattern.

`generators/_postprocess.py` contains common density functions and edge fading:

- Rectangular fade uses max(abs(normalized position)), not a radial sphere.
  Fade width defaults to 0.8 of each half-extent; bigger means a broader taper.
- **Edge clump suppression** defaults to 1 (0 restores positional fading).
  Survival = e / (1 + strength*(1-e)*rho), with rho relative to volume mean.
  The full-strength interior is unchanged. Dense edge regions have a decreasing
  soft density ceiling. This is the latest experiment, not visually accepted yet.
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
