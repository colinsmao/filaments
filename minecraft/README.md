# Minecraft: research notes

Research from 2026-10-14/15 comparing filaments with mobwalk
([colinsmao/mobwalk](https://github.com/colinsmao/mobwalk), v1.1.1 at `7381562`),
Litematica and Axiom. Nothing here is a decision or planned work. Rules for agents
working here live in [`AGENTS.md`](AGENTS.md).

## Goal

A Fabric **client** mod for Minecraft `26.3` that generates filaments canopies
in-game:

- change settings in-game and see the result immediately;
- optional debug renders (the curves, bounds); skipping them is acceptable if the
  mod relies purely on Litematica;
- hand the result off for building or pasting.

The mod ships **without** the C++ viewer.

The block sampler outputs, in native block coordinates: candles (groups of 1–4, one
of the five tints in `_block_population.CANDLE_COLORS`), end rods along X/Y/Z, and
occasional full blocks. The visual target is `scar/` (Hermitcraft 11, a survival
server). The game lights real blocks itself, so `_block_lighting.py` only matters
for approximate previews.

## Schematic export

`scripts/export_schematic.py` writes the block population of a saved preset as a
Sponge v2 `.schem` (gzipped NBT, `DataVersion` 5023 = Java 26.3). Litematica's 26.3
source accepts this layout; WorldEdit and Axiom also import `.schem` (untested). No
mod code is involved. **Not yet checked in-game.**

```powershell
& C:/Users/colin/miniconda3/envs/py310/python.exe -B scripts/export_schematic.py --script density_population_selection
```

- Reads `config/plot.json` (or `--settings`) without writing it, and sends the same
  worker request as the viewer (`world_units=blocks`, `density_graph`,
  `density_field`, saved per-script parameters, count, seed). `--script` and
  `--seed` override the saved values; scripts without block population, such as
  `block_scaffold`, are refused.
- Forces `pop_lighting=0` and `pop_colors=0`. Both change only RGB: positions,
  counts and shapes stay byte-identical (checked on both presets below), and
  candle RGB then equals a `CANDLE_COLORS` tint exactly.
- Decodes each `FSTAR003` record from its proxy shape: `(1,1,1)` full block; one
  axis 1 and two `2/16` end rod along that axis; `(w, 6/16, w)` candles with
  `w = 2,4,5,6 /16` giving 1–4 candles.
- Writes `build/minecraft/<script>-<seed>.schem` (or `--out`) plus a `.json` with
  the request, normalized parameters, counts per block state, origin and size.
  The minimum occupied cell is the schematic origin.

Block mapping (first choice, to be judged in-game; the table is at the top of the
script). The references' lavender look is night lighting, which the game now does
itself.

| Generator output | Block state |
| --- | --- |
| Candle tint 0 cream | `candle` |
| Candle tints 1 pale lavender, 3 near-white | `white_candle` |
| Candle tints 2 grey-blue, 4 deep lavender | `light_gray_candle` |
| Candle group of n | `candles=n`, `lit=false` |
| End rod along X / Y / Z | `end_rod[facing=east / up / south]` |
| Full block | `ochre_froglight[axis=y]` (light 15, as in the lighting model) |

First exports, seed 1919363634 from the committed `config/plot.json` (one run each
in a fresh process with cold caches; Generate includes the worker's catalog load):

| Preset | Blocks | Candles / rods / full | Size (X×Y×Z) | Generate | Encode | File |
| --- | --- | --- | --- | --- | --- | --- |
| `density_population_selection`, saved | 5,853 | 5,304 / 549 / 0 | 268×52×252 | 6.5 s | 0.35 s | 18 KB |
| `block_scaffold_stars`, defaults | 8,526 | 7,814 / 673 / 39 | 239×55×214 | 1.9 s | 0.19 s | 20 KB |

`density_population_selection` has no full-block role, so it exports none.

## Generation timings

Measured in-process with `worker.generate_request` on the saved preset of
2026-10-14 (`config/plot.json`, `density_population_selection`, seed 1213151058,
about 9,600 objects):

| Edit | Total | Pool + sketch | Selection | Block population |
| --- | --- | --- | --- | --- |
| Cold | 1.81 s | 254 + 243 ms | ~35 ms | 836 ms |
| Selection setting (rod attraction, isolation) | 0.90–0.97 s | cached | ~35 ms | 861–928 ms |
| Growth setting (short wandering) | 1.71 s | 209 + 215 ms | ~35 ms | 920 ms |

Selection time is the total minus the measured stages; lighting took 3 ms. Block
population is over 90% of a selection-only edit.

Stage caches exist as `lru_cache`s keyed on each stage's own parameters:
`_curve_selection.build_pool`, `_population_selection.build_sketch`, `rasterize`
and `population_proximity`. The viewer's service discards the worker on
cancellation, and the next run starts cold (~2 s per the root README) with empty
caches.

## MaLiLib screens

MaLiLib screens keep the world live: `GuiBase.isPauseScreen()` returns false and
`extractBackground` skips vanilla's blur. `GuiBase.drawScreenBackground` dims the
whole screen with `0xB0000000`.

`density_population_selection` defines 48 parameters; the viewer shows 86 with the
shared population, postprocessing and lighting controls. Python's schema carries
key, label, range, default, group, description and `enabled_if`. MaLiLib's config
screen lists whatever `getConfigs()` returns
(`ConfigOptionWrapper.createFor(collection)`), so options built at runtime can be
listed.

## Generator dependencies

**Python worker.** `python/worker.py --serve` reads JSON lines
(`{request, response, points}`) on stdin and keeps imports and caches warm. Running
it needs Python 3 with numpy, scipy and pyfastnoiselite. `python/requirements.txt`
allows any `numpy<3`, but NumPy 2.5 (what pip installs today) has no `np.trapz`, so
`_population_field.py:44` raises `AttributeError` on a fresh install.

**Java.** FastNoiseLite has an official Java port. The import closure of
`density_population_selection` plus `_population`, `_block_population`,
`_postprocess` and `_density_field` is about 3,900 non-blank lines in 29 modules,
part of which serves other experiments. It uses `cKDTree` (every query has a
bounded radius), `scipy.sparse` Gram products, `ndtri`, scrambled Sobol
(`scipy.stats.qmc`) and NumPy `SeedSequence`/PCG64.

**Worker output.** `FSTAR003` stores XYZ/RGB/size plus three box multipliers, and
the RGB is pre-lit. Block kinds (`_block_kinds`) are popped from the stats in
`worker.py`, used for lighting and dropped; candle count is only implied by box
width (`[2, 4, 5, 6]/16`) and rod axis by which multiplier is 1.

## Litematica

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
- Files: schematics in `.minecraft/schematics` appear under Load Schematics.
  **Reload** in Loaded Schematics calls `readFromFile()` (Sponge `.schem`, vanilla
  `.nbt`, `.litematic`) and rebuilds every placement of that schematic in place.
  Litematica picks the format from the file extension. The 26.3 source validates
  Sponge v2 (`Width`/`Height`/`Length` shorts, `Version`, `Palette`, `BlockData`)
  and v3 (`Schematic` compound with `Blocks` and `DataVersion`).
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
- Forking is legal under LGPL (the fork stays LGPL with source published). Size:
  316 Java files, ~73k lines; the renderer alone is 51 files and ~12k lines plus a
  2k-line fake world and 53 mixins, and it is the most version-sensitive part.

## Axiom

- Client is proprietary; its [EULA](https://axiom.moulberry.com/eula) forbids
  reverse engineering, decompiling, modifying and derivative works, so it cannot
  be forked.
- Official [AxiomClientAPI](https://github.com/Moulberry/AxiomClientAPI) (MIT):
  `CustomTool` (ImGui options, use/confirm/delete callbacks), `BlockRegion`
  (ghost render with real block models), `ToolService.pushBlockRegionChange`
  (undoable edit). API 2.0.0 builds against 26.1-rc-3 with Java 25; the
  [example](https://github.com/Moulberry/AxiomClientAPIExample) still targets
  1.20.1. Axiom 6.1.3 ships for 26.3; the API on 26.3 is untested.
- Imports `.schem` and `.schematic` (File → Import Schematic).
- Multiplayer needs the MIT [AxiomPaperPlugin](https://github.com/Moulberry/AxiomPaperPlugin),
  op or `axiom.default`, and a whitelist (non-commercial) or commercial license.

## Fake vs real blocks

Fake (measured): a plain Java loop writing position + RGBA quads (16 bytes per
vertex, 24 vertices per box):

| Boxes | Vertices | Mesh | Build |
| --- | --- | --- | --- |
| 9,643 (saved preset) | 231k | 3.7 MB | 0.7 ms |
| 17,555 (tuned scene in the root notes) | 421k | 6.7 MB | 1.5 ms |

Minecraft's vertex builder and the GPU upload add a few milliseconds; the result
shows on the next frame.

Real (estimated; not measured in-game):

1. Litematica's paste and delete each walk the whole bounding box (~257×120×257,
   ~7.9M cells for ~10k blocks) at up to ~60 ms of tick time per server tick.
2. End rods emit light 14; adding or removing hundreds relights the air around each.
3. The client re-meshes every 16³ section whose blocks or light changed, most of
   the ~2,300 sections in the box.
4. Changes reach the client at the end of a server tick (50 ms).

## mobwalk

Paths are under `src/client/java/dev/kelianmao/mobwalk/client/` in
[colinsmao/mobwalk](https://github.com/colinsmao/mobwalk) (MIT, same author).

| Part | Size |
| --- | --- |
| Gradle/Loom setup, `fabric.mod.json`, `splitEnvironmentSourceSets()`, MaLiLib/ModMenu repositories, `fabric-loader-junit` test wiring | build files |
| `overlay/` (HUD + world frameworks, `FloodProgressOverlay`, `RadiusIndicatorOverlay`), `config/WandItem`, `InitHandler`, `MobWalkClient` | ~840 lines |
| `config/Configs` + `config/GuiConfigs` (MaLiLib stack, live apply, JSON save) | ~1,600 lines |
| `surface/` geometry, profile roster, their tests | ~9,000 lines |

Versions mobwalk builds with: Minecraft 26.3, Fabric Loader 0.19.5, Loom
1.18-SNAPSHOT, Fabric API 0.161.0+26.3, MaLiLib 0.30.2, ModMenu 21.0.0, JDK 25.
Its Gradle setup builds on 26.3.

## Game rules that shape placement

- A client-only mod places blocks only in singleplayer (integrated server), through
  op commands, or through Litematica/Axiom.
- Candles need a sturdy block below to be placed (`CandleBlock.canSurvive`);
  floating candles come from removing that support afterwards
  ([MC-226686](https://mojira.dev/MC-226686)). End rods need no support. Neither
  behavior has been checked on 26.3.

## Sources

- Litematica 26.3: <https://github.com/sakura-ryoko/litematica/tree/26.3>
- MaLiLib 26.3: <https://github.com/sakura-ryoko/malilib/tree/26.3>
- Axiom docs: <https://axiomdocs.moulberry.com/> · EULA: <https://axiom.moulberry.com/eula>
- AxiomClientAPI: <https://github.com/Moulberry/AxiomClientAPI>
- Candle support behavior: <https://mojira.dev/MC-226686>
- Fabric versions: <https://fabricmc.net/develop>
- Data versions: <https://minecraft.wiki/w/Data_version>
