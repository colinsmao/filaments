# Continuing this project

Read this file and `README.md` before changing the project. This is a handoff of
the current implementation, not a commitment to continue any particular experiment.

## Purpose and user preferences

- Build visually interesting distributions of stars: galaxies, filaments, voids,
  and other patterns. Appearance matters more than physical accuracy. Minecraft
  may be a later destination; currently this is a math playground and viewer.
- The user likes the Zel'dovich generator as a baseline, but is dissatisfied with
  the appearance of some postprocessing and edge fades and wants to explore new
  ideas. Do not assume the existing approaches are the desired final direction.
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

## Architecture

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
  Input count is 1–1,000,000. Actual output may be smaller after merging/fading.
  Zero-point clouds are currently rejected. Job timeout defaults to 60 seconds.
- Generators expose `NAME`, `PARAMETERS`, and `generate(count, seed, **params)`.
  Return positions and colors shaped `(count, 3)`, plus scalar/per-star sizes.
  Existing worker support for legacy two-array returns must remain intact.
  Shared control names beginning `pp_` are reserved by the worker.
- Python files under `generators/` and the worker are watched, including new files.
  Worker/schema errors are shown in the GUI without discarding the last valid cloud.

## Current math experiments

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
- `zeldovich.py`: current baseline. Smoothed Gaussian initial density on a 96³
  periodic grid; FFT displacement with divergence(s) = -density; x = q + D*s(q).
  One-shot approximation, not a gravity simulation or convergence iteration.
  Beyond crossings, stars pass through concentrations rather than binding.
  Y scale compresses the entire result (unlike thin-region sampling in noise
  generators). Colors reflect final concentration; per-star sizes use a separate RNG.
  **Void threshold** applies rho²/(rho²+threshold²) as a bounded multiplier before
  resampling. It replaced a density power that overpopulated peaks. Zero bypasses
  resampling exactly. A 64³ estimate and at least 262,144 pilot particles are used.

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
3. Warp: mode 0 is a global swirl about world Y, theta = angle/(1+(r/radius)²),
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
