# Filaments

A small native C++17 / OpenGL 3.3 point viewer with GLFW, GLM, and Dear ImGui.
Windows runs directly against the installed graphics driver; WSL is not required.

## Build and run on Windows

From this directory in PowerShell:

**To run an existing build, no compilation is needed:**

```powershell
.\build\Release\filaments.exe
```

You can also double-click that executable in File Explorer. Rebuild only after
changing source code; the build script recompiles only changed files:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Run
```

The first build downloads a portable x64 Clang/MinGW compiler, CMake, Ninja,
and pinned library sources. Git and curl must be available. Tools are kept in
`.tools/`, dependencies and generated files in `build/`; no administrator install,
global PATH change, Python environment, or Visual Studio workload is needed.
ExecutionPolicy Bypass applies only to that PowerShell process.

Subsequent builds reuse these downloads. Release is the default:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Test
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Configuration Debug -Test
.\build\Release\filaments.exe
```

The executable uses a static C++ runtime and can be launched directly, from any
working directory. It requires a Windows graphics driver supporting OpenGL 3.3.
No shader files or other assets need to accompany it.

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

ImGui captures its own mouse and keyboard interactions. The GUI controls point
count (apply with Generate sample), pixel size, round/square points, axes,
background color, and VSync. Point count ranges from 1,000 to 1,000,000.

## Data and rendering

`src/main.cpp` defines `Point { position, color }` and
`PointRenderer::setPoints(const std::vector<Point>&)`. Replace `makeCloud()` with
your data source. Each point currently occupies 24 bytes on the GPU (two vec3s).
Data uploads happen only when replaced; the entire cloud uses one GL_POINTS draw
call per frame, with depth testing and no per-point CPU work during drawing.

`src/camera.h` contains the orbit/fly camera and projection. The current demo uses
single-precision coordinates and a fixed 0.01–10,000 clipping range. Very large
world coordinates, file loading, picking, streaming, and level of detail are
future work. The sample count range is not a performance guarantee; GPU speed,
point size, and overlapping points all affect frame time.

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

Library revisions are pinned by commit in CMakeLists.txt. The GLAD generated
source is vendored with its license; other licenses accompany fetched sources.
The local `.reference/ising` checkout is ignored and is not a build dependency.

The GPU driver may report OpenGL 4.x when asked for a 3.3 context. That is normal:
this application only loads and uses the OpenGL 3.3 API and GLSL 330 shaders.

For another C++ toolchain, use ordinary CMake commands instead of the Windows
bootstrap script. The CMake project also supports MSVC if its C++ workload is
installed. Linux/macOS portability has not been tested here.
