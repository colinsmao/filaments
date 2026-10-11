# Filaments

A native C++17 / OpenGL 3.3 star-distribution viewer with live Python/NumPy generators.
Windows runs directly against the installed graphics driver; WSL is not required.

For development context and workflow preferences, read [AGENTS.md](AGENTS.md).

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

## Density-guided local strands (`density_filament_curves.py`)

Select **Density-guided local strands**. This shares
`noise_filaments_branches.build_density` with the direct branch sampler: equal
AB, AC and BC contributions, clump modulation and the three-regime density curve.
There is no Layer continuity or Connectivity control. It traces short curves within
that density. It does not construct a new blob network or trace A=B=0. Curve and star
visibility remain independent; stars and appearance use the shared pipeline.
The XZ and Y half-extents are independent world-unit bounds. Old presets migrate
Y to `extent*y_scale`; initial bounds are XZ 9.458 and Y 2.213172. Frequency 2.505,
width .025, roughness .107, clumping 6.875 and Strand continuity 1 retain the
experiment's earlier defaults. Separate XZ/Y fades use the shared density-fade
helper before seeding and guidance, rather than thinning sampled stars afterward.
Old shared fade settings migrate to both axes. Fade can change roots, curve
lengths and star counts; equal settings reproduce the shared box density taper.
Bounds/remapping/fade introduce no extra random draws. Physical noise wavelength
still follows XZ extent through Frequency. No live settings files are overwritten.

Math: smooth the density with a Gaussian of physical standard deviation r, then
compute `L=log(smoothed_density)` and its symmetric Hessian `H=second_derivatives(L)`.
Physical XYZ grid spacing is used, including the thin Y domain. At query points,
interpolate H before diagonalizing it; interpolating signed eigenvectors would
allow opposite signs to cancel. Sorted eigenvalues `l0 <= l1 <= l2` describe
local curvature. The l2 eigenvector is the least sharply curved direction.
Confidence is `clip((l2-l1)/max(abs(l)),0,1)`, zero when l1 is nonnegative.
Thus tube-like regions guide strongly, while sheets and round peaks guide weakly.

Roots are sampled from the remapped, edge-faded density. Initial directions are shared
spatial Perlin vectors softly projected into the low-curvature directions:
each eigenvector component is weighted by `exp(-(l2-li)/(0.2*max(abs(l))))`.
That permits a plane of directions in sheets instead of arbitrary out-of-plane
launches. Both halves share the initial axis and a random total budget
`mean_length*(0.5+Beta(2,2))`; they begin in opposite directions.

At each step, orient the least-curvature tangent t toward the previous heading h.
The target heading is `unit(h + confidence*(t-h) + pull*u + wander*N(x) + join_strength*j)`.
Here u is `r*(gradient(L)-h*dot(gradient(L),h))`, capped to magnitude 1: density
attraction is transverse, not deliberate motion along the strand toward a peak.
N uses existing vector Perlin steering, 80% shared / 20% per-curve offset, two
octaves, roughness .35, wavelength 4r. Heading approaches its target with response
`1-exp(-step/r)`. Growth stops at the box, its finite budget, or a tenfold decline
in smoothed density from its starting value. There are no assigned connections.
If the Y half-thickness is below r/20, directional analysis uses Y-averaged XZ
density and paths retain their sampled heights except for the final local snap
to a joined strand. Exactly zero Y is supported.

| New curve control | Meaning and effect on stars |
| --- | --- |
| Local strands | 512 density-weighted random starts. More starts generally produce more stars; these are separate short paths, not branches of one graph. |
| Mean strand length | 2 world units total across both directions; random budget is 0.5â€“1.5 times this value. Longer curves generally produce more stars. Early termination can shorten them. |
| Density direction radius | 0.3 world units, Gaussian standard deviation for shape estimation and heading response length. Larger suppresses small features and slows turns; Perlin wavelength is 4 times this value. Count can change through early termination. |
| Transverse density pull | 0.35, dimensionless. Steers sideways toward higher density; zero disables this correction. It can change paths and survival lengths, hence counts. It is not star scatter. |
| Curve Perlin steering | 0.15, dimensionless smooth random steering during growth. Zero disables ongoing noise; starts, initial directions and lengths remain stochastic. It can affect final curve lengths/counts. |
| Strand joining reach | 0.6 world units. Only deposited parallel strands within this distance steer a growing tip. Zero disables joining entirely. Larger reach can cause earlier joins and fewer stars through shorter paths. |
| Strand joining strength | 1, dimensionless. Amount of neighbor-directed turning. Zero restores independent growth including no contact termination. No new random draws; it changes paths and can shorten them, reducing stars. |
| Strand contact radius | 0.08 world units, capped by joining reach. Within this distance, an aligned tip snaps locally onto the existing segment and stops. Zero disables contact termination while retaining steering. Larger values usually shorten paths and reduce stars, but can make joins less smooth. |
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
load 1; physical contact termination is allowed from load 0.75. When a proposed
step has load >=1, the tip stops there unless it can actually complete a nearby
aligned join. It does not inherit or transfer unused length/star budgets. Two
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
rather than adding another pull toward its densest peak. Density-derived
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

Joining acts **during growth** (capacity-gated in coverage modes 1/2); the rejected post-growth overlap-deletion pass
and its controls are no longer used. A global deposited-segment tree refreshes
every four growth steps. Query up to 48 nearest midpoints within joining distance
plus the longest segment's half-length, then choose the closest
eligible segment by exact 3D distance. Eligibility requires a different source
strand (both halves of one's own strand are excluded) and absolute tangent dot
>= cos(25 degrees). Transverse crossings do not join. This bounded search can
miss eligible segments hidden behind many ineligible neighbors.

Checks use local density-grid interpolation. Neighbor steering searches are
skipped at load <=0.5, and contact searches are skipped below load 0.75 or before
the initial two steps. These are the same existing eligibility thresholds.
Coverage gradients are only built for filling mode, and proposed-step capacity
checks interpolate only the scalar load. Density derivatives are built once;
coverage still refreshes its small grid every four steps. No new controls.
On one fixed saved branch field with 512 starts, median growth times over three
runs changed from 0.62 to 0.56 seconds (coverage off), 0.65 to 0.50 (capacity), and
1.04 to 0.85 (filling), excluding noise construction, stars and process startup.
All three optimized outputs matched the previous path bytes exactly in this
comparison. Timings vary with bounds, strand count, length and early termination.

For nearest projection q, oriented neighbor tangent g, current heading h,
distance d and reach R, define transverse offset `v=(q-x)-h*dot(q-x,h)` and
`j=w*(g-h+2*v/R)`, with `w=(1-d/R)^2*min(1,travelled/R)` inside reach, zero
outside. The ramp avoids abrupt launch steering. Noise and density guidance
still act, and heading response remains smooth. Contact is tested at the proposed
new position against deposited geometry; after at least two growth steps, a
close aligned arrival ends that half on the actual receiving segment. There is
no assigned destination and no deletion of complete curves afterward. All tips
advance together, deposited vertices remain fixed, and unconnected tips retain
their normal random length/density/domain limits. Joining edits can affect other
curves through their changed deposited geometry. Star budgets on shortened paths
are not redistributed; the shared star sampler is unchanged.

Shared Stars per unit length controls along-path count; Spacing randomness
controls longitudinal jitter; Transverse spread is independent star scatter.
Shared tip taper and postprocessing still operate on stars. Edge fade does not
change source curves. The tracer has a 200k segment-budget scale, increasing
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
| Transverse spread | Gaussian standard deviation in each of the two local perpendicular directions, default 0.035 world units. Zero stays on the curve. Unbounded tails allow rare outliers, with no separate tail control. |
| Tip taper fraction | Final fraction of each path subject to smooth survival falloff, default 0.3. Zero disables thinning; curves remain full length. |
| Star size | Base cube side length or point diameter, default 0.04 world units, before the Display multiplier. |
| Size variation | Uniform relative size variation, default 0.4 gives 60%â€“140% of base size. Independent of positions/count. |
| Use curve colors | Inherit source curve colors when enabled; otherwise pale blue. Postprocessing can override colors. |

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
directional light or edge outlines. They are world-aligned, with equal side
lengths for now. A small center crosshair stays visible in both camera modes.
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

`src/point.h` defines `Point { position, color, size }`.
`src/point_renderer.h` owns GPU buffers/shaders and accepts any `std::vector<Point>`.
`src/generation.cpp` handles background jobs, cancellation and validated binary
transfer; `src/generator_panel.h` handles discovery, sliders and file watching.
`python/worker.py` loads the independent modules in `generators/`.
Each star occupies 28 bytes on the GPU (two vec3s and one float).
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
Each job uses its own temporary directory,
cleaned after completion. A fresh Python process loads the saved source on each
run, with no interpreter/GIL integration or per-frame Python calls.

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
