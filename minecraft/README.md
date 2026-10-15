# Minecraft mod: design handoff

Status: **design only, no mod code yet.** This records a research session from
2026-10-14/15 that compared filaments with mobwalk
([colinsmao/mobwalk](https://github.com/colinsmao/mobwalk), v1.1.1 at `7381562`),
Litematica and Axiom. Everything below is a recommendation unless it says
**decided**. Rules for agents working here live in [`AGENTS.md`](AGENTS.md).

## Goal

A Fabric **client** mod for Minecraft `26.3` that generates filaments canopies
in-game:

- change settings in-game and see the result immediately;
- optional debug renders (the curves, bounds); skipping them is acceptable if the
  mod relies purely on Litematica;
- hand the result off for building or pasting.

The mod ships **without** the C++ viewer. Whether it ships the Python scripts is
**open** (see [Generator backend](#generator-backend-python-worker-or-java-port-open)).

What the mod places is what the block sampler already outputs, in native block
coordinates: candles (groups of 1–4, one of the five tints in
`_block_population.CANDLE_COLORS`), end rods along X/Y/Z, and occasional full
blocks. The visual target is `scar/` (Hermitcraft 11, a survival server). The game
lights real blocks itself, so `_block_lighting.py` only matters for approximate
previews.

## Recommended architecture

```
filaments-mod (Fabric client, 26.3)
├─ generator/   Generator interface; PythonWorkerGenerator now, JavaGenerator later;
│               per-stage caches; coalescing runner on a background thread
├─ preview/     retained block mesh, curve lines, bounds box, progress ring, HUD stats
├─ config/      MaLiLib options built from the parameter table, side-panel screen,
│               pinned parameter adjusted with sneak + scroll
├─ input/       wand sets the anchor, hotkeys
└─ litematica/  optional: send to placement, paste/undo in a creative test world
```

`Generator` returns `{curves, blocks, stats}`. Build the mod against the Python
backend first; port to Java once the experiment stops changing daily, using the
Python worker as the per-stage test oracle.

### Preview: own renderer for tuning, Litematica for committing

Three ways to see a result in-world:

| Option | Real block models | Real lighting | Latency per change | Code |
| --- | --- | --- | --- | --- |
| Own preview (mobwalk's renderer) | No (boxes) | Python approximation, optional | One frame after generation | Moderate |
| Litematica ghost from a schematic | Yes | No (uniform fake light) | Generation + Litematica re-mesh | Small |
| Real blocks pasted in a creative world | Yes | Yes | Seconds (see [Fake vs real blocks](#fake-vs-real-blocks)) | Small via Litematica |

Use the **own preview** for the tuning loop, **Litematica** as a "send to
Litematica" button (material list, layer mode, paste, survival building), and a
**"place for real"** key in a creative test world to judge the actual night
lighting. Do not fork Litematica's renderer (see [Litematica](#litematica)).

Own preview contents:

- blocks as the boxes the viewer already draws (candle groups, rod axes), optionally
  colored by a Java port of `_block_lighting.py` (~100 lines) for a night look that
  Litematica ghosts cannot show;
- curves colored like the viewer's `lines` output: candidates grey, selected candle
  curves one hue each, rods gold;
- seed-region and fade bounds, anchor marker, HUD counts and timings (already in
  the generator's `stats`).

Renderer changes relative to mobwalk's `WorldOverlayManager`: upload the mesh once
per result and redraw it every frame (mobwalk rebuilds and quad-sorts every frame),
and add a line layer for curves (or thin quads through the existing pipeline).

### Making changes feel immediate

Measured in-process with `worker.generate_request` on the saved preset of
2026-10-14 (`config/plot.json`, `density_population_selection`, seed 1213151058,
about 9,600 objects):

| Edit | Total | Pool + sketch | Selection | Block population |
| --- | --- | --- | --- | --- |
| Cold | 1.81 s | 254 + 243 ms | ~35 ms | 836 ms |
| Selection setting (rod attraction, isolation) | 0.90–0.97 s | cached | ~35 ms | 861–928 ms |
| Growth setting (short wandering) | 1.71 s | 209 + 215 ms | ~35 ms | 920 ms |

Selection time is the total minus the measured stages; lighting took 3 ms.
Block population is over 90% of a selection-only edit, so the preview updates in
stages:

1. curves redraw as soon as selection finishes;
2. blocks follow when block population finishes, with the previous blocks drawn
   until then (mobwalk's publish-on-completion snapshot);
3. a progress ring shows a run in flight (mobwalk's `FloodProgressOverlay`).

Stage caches already exist as `lru_cache`s keyed on each stage's own parameters:
`_curve_selection.build_pool`, `_population_selection.build_sketch`, `rasterize`
and `population_proximity`. A slider reruns from the first stage whose inputs
changed; tag each parameter with that stage so the UI can show the cost.

Runner rules:

- **Coalesce, don't cancel.** The viewer's service discards the worker on
  cancellation, and the next run starts cold (~2 s per the root README) with empty
  caches. Let a run finish, then run once more with the latest values if they
  changed.
- Generation never reads the world, so it runs on a background thread. Mobwalk's
  latest-wins immutable snapshot handoff applies; its per-frame time budget does not.

### In-game settings UI

MaLiLib screens keep the world live: `GuiBase.isPauseScreen()` returns false and
`extractBackground` skips vanilla's blur. `GuiBase.drawScreenBackground` dims the
whole screen with `0xB0000000`; override it to darken only a side panel so the
canopy stays visible while dragging sliders.

- Build options from a parameter table, not hand-written static fields.
  `density_population_selection` defines 48 parameters; the viewer shows 86 with
  the shared population, postprocessing and lighting controls. Python's schema
  already carries key, label, range, default, group, description and `enabled_if`,
  and MaLiLib's config screen lists whatever `getConfigs()` returns
  (`ConfigOptionWrapper.createFor(collection)`), so options built at runtime work.
- A pinned parameter adjusted with sneak + scroll and a HUD readout, generalizing
  mobwalk's radius scroll and `RadiusIndicatorOverlay`, tunes one value while
  flying around with no screen open.

### Generator backend: Python worker or Java port (open)

**Python worker.** `python/worker.py --serve` reads JSON lines
(`{request, response, points}`) on stdin and keeps imports and caches warm.

- No porting; results match what was tuned in the viewer.
- Every player needs Python 3 with numpy, scipy and pyfastnoiselite. Bundling a
  Python runtime with numpy/scipy is far too large for a mod jar.
- Dependency drift: `python/requirements.txt` allows any `numpy<3`, but NumPy 2.5
  (what pip installs today) has no `np.trapz`, so `_population_field.py:44` raises
  `AttributeError` on a fresh install.

**Java port.** Self-contained, and block population parallelizes across threads.
The import closure of `density_population_selection` plus `_population`,
`_block_population`, `_postprocess` and `_density_field` is about 3,900 non-blank
lines in 29 modules, part of which serves other experiments. Replacements:

- FastNoiseLite has an official Java port;
- `cKDTree` → spatial hash grid (every query has a bounded radius);
- `scipy.sparse` Gram products → hash maps;
- `ndtri` → a standard inverse-normal approximation;
- scrambled Sobol (`scipy.stats.qmc`) and NumPy `SeedSequence`/PCG64 need exact
  ports only if a saved preset must reproduce the same canopy in both; otherwise the
  two match statistically.

**Worker output gap (needed by either backend).** `FSTAR003` stores
XYZ/RGB/size plus three box multipliers, and the RGB is pre-lit. Block kinds
(`_block_kinds`) are popped from the stats in `worker.py`, used for lighting and
dropped; candle count is only implied by box width (`[2, 4, 5, 6]/16`) and rod axis
by which multiplier is 1. Add an explicit block output (kind, candle count, tint
index, rod axis) as a new, additive output so the C++ viewer keeps working.

### Litematica

- Maintained 26.3 fork: [sakura-ryoko/litematica](https://github.com/sakura-ryoko/litematica),
  branch `26.3`, **LGPL-3.0**. Artifact `fi.dy.masa.litematica:litematica-fabric-26.3`
  0.29.1 on `https://masa.dy.fi/maven/sakura-ryoko`, the repository mobwalk already
  uses for MaLiLib.
- No formal API; addons call its public classes or use mixins (e.g.
  [litematica-printer](https://github.com/aleksilassila/litematica-printer), AGPL-3.0).
  Internal classes change between versions.
- Build and place a schematic in memory:
  `LitematicaSchematic.createEmptySchematic(area, author)` →
  `getSubRegionContainer(region).set(x, y, z, state)` →
  `SchematicHolder.getInstance().addSchematic(schematic, allowDuplicates)` →
  `SchematicPlacement.createFor(schematic, origin, name, enabled, enableRender)` →
  `DataManager.getSchematicPlacementManager().addSchematicPlacement(placement, printMessages)`.
  Swap with `removeSchematicPlacement` and `SchematicHolder.removeSchematic`.
- No-mod loop: write a schematic file into `.minecraft/schematics` and press
  **Reload** in Loaded Schematics. Reload calls `readFromFile()` (Sponge `.schem`,
  vanilla `.nbt`, `.litematic`) and rebuilds every placement of that schematic in
  place. Litematica picks the format from the file extension.
- Ghost lighting: `FakeLightingProvider` returns one uniform level
  (`renderFakeLightingLevel`, default 15) and ghosts draw at `ghostBlockAlpha` 0.5,
  so ghosts show position and scale, not night lighting.
- Paste (creative only): `TaskPasteSchematicPerChunkDirect` in singleplayer writes
  straight into the world with `setBlock` flags `0x12` (no neighbor or shape
  updates, so floating candles survive); `TaskPasteSchematicPerChunkCommand` uses
  commands on servers. Schedule with
  `TaskScheduler.getServerInstanceIfExistsOrClient().scheduleTask(task, interval)`.
- Undo a previous paste precisely with
  `ToolUtils.deleteBlocksByPlacement(placement, PlacementDeletionMode.MATCHING_BLOCK, listener)`,
  which removes only world blocks that still match the schematic.
- Forking is legal under LGPL (the fork stays LGPL with source published) and
  impractical: 316 Java files, ~73k lines; the renderer alone is 51 files and ~12k
  lines plus a 2k-line fake world and 53 mixins, and it is the most
  version-sensitive part.

### Axiom

- Client is proprietary; its [EULA](https://axiom.moulberry.com/eula) forbids
  reverse engineering, decompiling, modifying and derivative works. **Do not fork.**
- Official [AxiomClientAPI](https://github.com/Moulberry/AxiomClientAPI) (MIT):
  `CustomTool` (ImGui options, use/confirm/delete callbacks), `BlockRegion`
  (ghost render with real block models), `ToolService.pushBlockRegionChange`
  (undoable edit). API 2.0.0 builds against 26.1-rc-3 with Java 25; the
  [example](https://github.com/Moulberry/AxiomClientAPIExample) still targets
  1.20.1. Axiom 6.1.3 ships for 26.3; the API on 26.3 is untested.
- Imports `.schem` and `.schematic` (File → Import Schematic).
- Multiplayer needs the MIT [AxiomPaperPlugin](https://github.com/Moulberry/AxiomPaperPlugin),
  op or `axiom.default`, and a whitelist (non-commercial) or commercial license.
- Best fit: creative/singleplayer art with preview, paste and undo. Litematica fits
  survival building, which matches `scar/`.

## Fake vs real blocks

Fake (measured): a plain Java loop writing position + RGBA quads (16 bytes per
vertex, 24 vertices per box):

| Boxes | Vertices | Mesh | Build |
| --- | --- | --- | --- |
| 9,643 (saved preset) | 231k | 3.7 MB | 0.7 ms |
| 17,555 (tuned scene in the root notes) | 421k | 6.7 MB | 1.5 ms |

Minecraft's vertex builder and the GPU upload add a few milliseconds; the result
shows on the next frame.

Real (estimated; measure in-game before relying on these):

1. Litematica's paste and delete each walk the whole bounding box (~257×120×257,
   ~7.9M cells for ~10k blocks) at up to ~60 ms of tick time per server tick.
2. End rods emit light 14; adding or removing hundreds relights the air around each.
3. The client re-meshes every 16³ section whose blocks or light changed, most of
   the ~2,300 sections in the box.
4. Changes reach the client at the end of a server tick (50 ms).

A custom paster that touches only occupied cells removes cost 1. Real placement fits
an occasional "place for real" key, not every slider change.

## Reuse from mobwalk

Paths are under `src/client/java/dev/kelianmao/mobwalk/client/` in
[colinsmao/mobwalk](https://github.com/colinsmao/mobwalk) (MIT, same author).

| Part | Size | Reuse |
| --- | --- | --- |
| Gradle/Loom setup, `fabric.mod.json`, `splitEnvironmentSourceSets()`, MaLiLib/ModMenu repositories, `fabric-loader-junit` test wiring | build files | As-is |
| `overlay/` (HUD + world frameworks, `FloodProgressOverlay`, `RadiusIndicatorOverlay`), `config/WandItem`, `InitHandler`, `MobWalkClient` | ~840 lines | Rename package; add retained mesh + line layer |
| `config/Configs` + `config/GuiConfigs` (MaLiLib stack, live apply, JSON save) | ~1,600 lines | Pattern |
| `surface/` geometry, profile roster, their tests | ~9,000 lines | None |

Versions mobwalk builds with: Minecraft 26.3, Fabric Loader 0.19.5, Loom
1.18-SNAPSHOT, Fabric API 0.161.0+26.3, MaLiLib 0.30.2, ModMenu 21.0.0, JDK 25.
Re-check <https://fabricmc.net/develop> before building.

## Game rules that shape placement

- A client-only mod places blocks only in singleplayer (integrated server), through
  op commands, or through Litematica/Axiom.
- Candles need a sturdy block below to be placed (`CandleBlock.canSurvive`);
  floating candles come from removing that support afterwards
  ([MC-226686](https://mojira.dev/MC-226686)). For survival building, offer a second,
  toggleable placement with a temporary block under every candle. End rods need no
  support. Verify both on 26.3.

## Open questions

- Audience: personal tool (Python worker is fine) or public release (Java port)?
- Must a saved preset reproduce the identical canopy in Python and Java?
- Litematica as optional or required dependency?
- Block palette: which candle colors the five tints map to, and which full block.
- Anchor convention (canopy center vs corner) and vertical placement.
- License: filaments has none yet. It decides which libraries can be bundled
  (e.g. `litemapy` is GPL-3.0; `nbtlib` is MIT).

## Sources

- Litematica 26.3: <https://github.com/sakura-ryoko/litematica/tree/26.3>
- MaLiLib 26.3: <https://github.com/sakura-ryoko/malilib/tree/26.3>
- Axiom docs: <https://axiomdocs.moulberry.com/> · EULA: <https://axiom.moulberry.com/eula>
- AxiomClientAPI: <https://github.com/Moulberry/AxiomClientAPI>
- Candle support behavior: <https://mojira.dev/MC-226686>
- Fabric versions: <https://fabricmc.net/develop>
