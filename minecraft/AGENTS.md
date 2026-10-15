# AGENTS.md (minecraft/)

Rules for agents working on the filaments Minecraft mod. The design, evidence and
open questions live in [`README.md`](README.md); read it first. The root
[`../AGENTS.md`](../AGENTS.md) and [`../README.md`](../README.md) cover the
generator itself.

## Scope

- `minecraft/` holds the mod. Generator math stays in `../generators/` (Python)
  until the Java port is decided; the open questions in `README.md` are the user's
  decisions, not the agent's.
- Changes to `../python/worker.py` stay additive (a new block output, new request
  fields) so the C++ viewer keeps reading `FSTAR002`/`FSTAR003` unchanged.
- Implement one agreed step at a time. Surface extra work you discover as a
  proposal instead of folding it in.

## Minecraft and Fabric

- Target Minecraft `26.3`, a real release on the year-based scheme; do not
  "correct" it to `1.21.x`. Class and package names differ from training data
  (e.g. `Identifier`, `GuiGraphicsExtractor`, `com.mojang.renderpearl`); verify
  against the resolved jars and <https://docs.fabricmc.net/develop>.
- `26.3` ships unobfuscated: `build.gradle` has no `mappings` line (Loom rejects
  one). Start from mobwalk's Gradle setup, which already builds on 26.3.
- Client-only: `"environment": "client"`, a `client` entrypoint, client code in the
  Loom `client` source set (`splitEnvironmentSourceSets()`).
- Use the Gradle wrapper. `./gradlew build` and `./gradlew test` prove compilation
  and pure logic only.
- **Never launch `./gradlew runClient`**; it takes over the user's session. Hand the
  user a short numbered in-game checklist (`action → expected on-screen result`) and
  wait for their results. Rendering, lighting and timing are judged in-game.

## Code and licensing

- Mobwalk ([colinsmao/mobwalk](https://github.com/colinsmao/mobwalk), MIT, same
  author) is the code source for the framework; copy and adapt freely.
- Litematica and MaLiLib are LGPL-3.0: depend on their jars and call public classes;
  keep their source out of this repo.
- Axiom's client EULA forbids decompiling and derivative works: use only the MIT
  `AxiomClientAPI`, and never inspect or copy Axiom client code.
- Filaments has no license yet; ask before adding GPL dependencies (e.g. `litemapy`).
- Prefer a thin in-house renderer (mobwalk's approach) over rendering libraries; the
  26.3 rendering API changes every release.

## Runtime design rules

- Generation never touches `Level`. It runs on a background thread and publishes an
  immutable result through one `volatile` reference; the render thread reads only
  that snapshot.
- Coalesce generation requests (finish the current run, then run once with the
  latest values); killing the Python worker discards its warm caches.
- Upload preview meshes once per result and redraw them each frame.

## Measurements

State the preset with every timing (see the tables in `README.md`), and mark
estimates as estimates.
