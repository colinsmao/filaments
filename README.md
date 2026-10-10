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

Python 3.10+ and NumPy are now required for generation. The current setup uses the
existing `py310` Conda interpreter with NumPy 1.24.3; no Python packages were
changed. On a new machine, use `python -m pip install -r python/requirements.txt`
in your chosen environment. The build discovers and remembers the interpreter;
to select another one, pass `-PythonExecutable C:\path\to\python.exe` to the build
script. This selects an executable, not a Python DLL linked into the viewer.

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
The first successful cloud is framed automatically; later updates preserve the
camera. Use **Fit cloud** to reframe a different-sized distribution.

The panel reports generation/packing time, total worker/transfer time, CPU time
spent uploading to OpenGL, and FPS. Timing varies with the algorithm; rendering
is not necessarily the slowest operation. Python startup and file transfer are
paid only on regeneration, not on every rendered frame.

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
    return positions, colors
```

Return two arrays of shape `(count, 3)`: XYZ positions and RGB colors in `[0, 1]`.
The bridge validates finiteness, shapes, colors and coordinates, then converts to
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

Sensitivity, movement speed, and camera mode are saved on normal quit to
`%LOCALAPPDATA%\Filaments\controls.ini` and restored on the next run. Restored
first-person mode starts with the mouse free; click the scene or press Tab to
capture it. Display settings and camera position are not saved.

| Input | Action |
| --- | --- |
| F | Switch camera mode |
| G | Regenerate current script with a new random seed |
| Mouse movement (first person) | Look around while captured |
| Tab / Esc (first person) | Toggle capture / release mouse |
| Left drag (drag mode) | Orbit around target |
| Middle drag (drag mode) | Pan |
| Right drag (drag mode) | Look from current camera position |
| Wheel (drag mode) | Zoom toward/away from target |
| WASD | Move forward/back/left/right |
| Space / E | Move up |
| Shift / Q | Move down (either Shift key) |
| R | Reset camera |
| Esc (drag mode) | Quit |

ImGui captures its own mouse and keyboard interactions. **Display** controls star
diameter in world units, round/square points, axes, background color, and VSync. A
star at twice the camera depth has half the pixel diameter, adjusted for field of
view and framebuffer resolution. Sizes are clamped to the GPU's supported point
size range (typically at least one pixel), so extremely distant stars stop shrinking
at the minimum. The GUI supports
1,000–1,000,000 stars. The generator protocol also accepts smaller clouds for tests.

## Data and rendering

`src/point.h` defines `Point { position, color }`.
`src/point_renderer.h` owns GPU buffers/shaders and accepts any `std::vector<Point>`.
`src/generation.cpp` handles background jobs, cancellation and validated binary
transfer; `src/generator_panel.h` handles discovery, sliders and file watching.
`python/worker.py` loads the independent modules in `generators/`.
Each point currently occupies 24 bytes on the GPU (two vec3s).
Data uploads happen only when replaced; the entire cloud uses one GL_POINTS draw
call per frame, with depth testing and no per-point CPU work during drawing.

`src/camera.h` contains the orbit/fly camera and projection. The current demo uses
single-precision coordinates and a fixed 0.01–10,000 clipping range. Very large
world coordinates, file loading, picking, streaming, and level of detail are
future work. The sample count range is not a performance guarantee; GPU speed,
point size, and overlapping points all affect frame time.

The transfer file is a 16-byte header (`FSTAR001`, then a little-endian uint64
count), followed by `count` interleaved XYZ/RGB float32 records. JSON is used only
for small parameter/schema messages. Each job uses its own temporary directory,
cleaned after completion. A fresh Python process loads the saved source on each
run, with no interpreter/GIL integration or per-frame Python calls.

## Validation

CPU-only tests (no viewer window):

```powershell
.\.tools\cmake-3.31.6-windows-x86_64\bin\ctest.exe --test-dir build/Release -E 'renderer_smoke|point_perspective' --output-on-failure
.\build\Release\generation_test.exe --benchmark
```

These cover deterministic generation, array validation, binary parsing, settings,
script discovery/reload/repair, missing interpreters, stale-job cancellation, and
timeouts. `scripts/build.ps1 -Test` also runs a hidden GPU test comparing the
pixel footprints of stars at different depths, and the GPU smoke test below.

The smoke test creates a hidden native OpenGL context, compiles the GLSL 330
shaders, draws 100,000 points, exercises camera movements and window resize,
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
