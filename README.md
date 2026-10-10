# Filaments

A native C++17 / OpenGL 3.3 star-distribution viewer with live Python/NumPy generators.
Windows runs directly against the installed graphics driver; WSL is not required.

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

**noise_filaments_branches.py** preserves the three-field experiment. Its
**Connectivity** slider adds the A/C and B/C strand families to A/B; these
meet at triple-zero junctions but can produce a much busier pattern. At 0 it
reproduces the original two-field method. **layer_filaments.py** also remains
available as the separate cellular experiment.

Both noise scripts have **Y thickness fraction**: 1 uses the full volume, 0.1
samples Y between `-0.1 * extent` and `+0.1 * extent`, and 0 makes a flat layer.
Noise is evaluated at those actual coordinates, so its wavelengths stay unchanged;
this selects a thinner region rather than compressing the noise features.
**Fade edges (0 off, 1 on)** optionally tapers density over the outer 30% of an
ellipsoid fitted to the region. The total star count stays fixed; stars are
redistributed toward the interior rather than made transparent or smaller.
The toggle uses an integer 0/1 control supported by the running viewer.

In **noise_filaments.py**, **Layer continuity** defaults to 1 to reduce isolated
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
compiled Perlin/fBm implementation fills a 96³ density grid in native code;
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
machine, one octave over 96³ points measured about 16 ms for compiled Perlin,
22 ms for OpenSimplex2, and 25 ms for OpenSimplex2S, versus 299 ms for the earlier
NumPy Perlin. Perlin is the current backend because it was fastest in this test.

**layer_filaments.py** remains available as a separate cellular experiment.
It uses a full 3D web of noise-warped Voronoi edges: density peaks where the
three nearest jittered sites are nearly equidistant. Cells change through Y.
**XZ scale (units)** and **Y scale (units)** set the axis half-extents and scale
the cell wavelengths with them; equal values give a roughly isotropic web.
**Cells across each axis**, **Strand width / cell**, **3D warp / cell**, and
**Clump contrast** control the structure. **Fade edges** tapers an ellipsoidal
boundary. It uses a 96³ density grid and SciPy's compiled spatial index;
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
connect separate paths, and the 96³ field grid can still miss unresolved features.
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
  **Small-scale detail** adds finer structure. The field uses a fixed 96³ grid;
  scales below one eighth of the box width are capped to limit aliasing.
- **Evolution strength** is a one-shot displacement multiplier. Smaller steps
  through the same values only animate the same trajectories; there is no
  iterative solver to converge. After trajectories cross, stars pass through
  concentrations rather than binding into stable structures.
- **Density power** suppresses void stars by resampling the final density in
  proportion to `density^power` (default 2, range 1–6). At 1 it bypasses this
  stage and returns the original particles exactly. Above 1, a periodic 64³
  smoothed density estimate is powered and sampled continuously, retaining the
  requested star count without duplicate particles. This changes positions;
  it is not an opacity control or further evolution. At least 262,144 pilot
  particles estimate density to reduce sampling noise for small star counts.
  Higher values increasingly favor knots and can thin out weaker connections.
- **Y scale fraction** compresses the complete result vertically, including
  its features. It does not slice a thin region out of the field. At 1 the
  construction is statistically isotropic.
- Colors run from blue to warm as the final local particle concentration rises.
  Coloring does not change positions. Star size and size variation remain
  independent per-star attributes.

## Next experiments

Current direction: retain the noise-sampled cloud and gently align nearby stars
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

Edit `generators/galaxy.py` or `generators/filaments.py`, or add a new `.py` file:

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
**Right-click zoom** sets magnification from 1–10×, default 3×. Camera position
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

ImGui captures its own mouse and keyboard interactions. **Display → Draw as**
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
1,000–1,000,000 stars. The generator protocol also accepts smaller clouds for tests.

## Data and rendering

`src/point.h` defines `Point { position, color, size }`.
`src/point_renderer.h` owns GPU buffers/shaders and accepts any `std::vector<Point>`.
`src/generation.cpp` handles background jobs, cancellation and validated binary
transfer; `src/generator_panel.h` handles discovery, sliders and file watching.
`python/worker.py` loads the independent modules in `generators/`.
Each star occupies 28 bytes on the GPU (two vec3s and one float).
Data uploads happen only when replaced. The entire cloud uses one instanced cube
draw call or one GL_POINTS draw call per frame, with depth testing and no per-star
CPU work during drawing. Both modes share the same star buffer, so switching
does not regenerate or re-upload it. Cubes reuse one 12-triangle mesh; they cost
more GPU work than points, especially at high counts.

`src/camera.h` contains the orbit/fly camera and projection. The current demo uses
single-precision coordinates and a fixed 0.01–10,000 clipping range. Very large
world coordinates, file loading, picking, streaming, and level of detail are
future work. The sample count range is not a performance guarantee; GPU speed,
point size, and overlapping points all affect frame time.

The transfer file is a 16-byte header (`FSTAR002`, then a little-endian uint64
count), followed by `count` interleaved XYZ/RGB/size float32 records. JSON is used only
for small parameter/schema messages. Each job uses its own temporary directory,
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
| NumPy | 1.24–2.x |

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
