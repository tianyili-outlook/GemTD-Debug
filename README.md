# GemTD private development baseline

当前主机为 **2026-09-26 结算诊断版**，仅增加只读日志；Friend Kit 仍为稳定版 `946DE6E9DDE8C806`。主机与该包的 Lua 差异是预期的。单人 coop 测试说明见 [SETTLEMENT_DIAGNOSTICS.md](SETTLEMENT_DIAGNOSTICS.md)。

## Friend installer (updated 2026-09-24)

The user has now confirmed the debug commands work in normal Dota runtime, including both requested `-crab` towers, `-choose`, and `-spawn`. Distribute **`dist/GemTD-Debug-Friend-Kit.zip`** (139,210 bytes; 8 files; 382,465 bytes unpacked). Friends extract it and run `Install-GemTD-Debug.cmd`. Windows PowerShell 5.1/.NET are the only dependencies; no Python or Workshop Tools are needed on their machines.

Expected build: **946DE6E9DDE8C806**. Full fingerprint: `946de6e9dde8c806a6cf9927046282c455d7c96772b849563be5070df43072d7`. It hashes sorted UTF-8 `path + NUL + lowercase SHA256(file) + LF` entries for all 2,508 runtime files. Verification rejects changed/missing/extra runtime files, ignoring only the four root Tools cache files listed in the kit manifest. The current tested `resource/custom_game_whitelist.txt` is included byte-for-byte (it differs from the subscribed archive); it is not silently excluded from the fingerprint.

Kit files: `Install-GemTD-Debug.cmd`, `Verify-GemTD-Debug.cmd`, `Uninstall-GemTD-Debug.cmd`, `GemTD-Debug.ps1`, `Vpk.cs`, `build.json`, `patches.json`, `README.txt`. The ZIP contains no original VPK, full addon, or development/test dependency. The cumulative Lua byte edits are derived from the reviewed working file, plus one unchanged whitelist patch. Every patch has input/output SHA-256 checks, followed by full runtime verification before installation. The pinned source VPK SHA-256 is the original baseline hash documented below; a mismatch stops installation.

Discovery uses a running Steam process path, Steam registry install locations, and standard installation paths, then parses `steamapps/libraryfolders.vdf` for modern `path` entries and older numbered library paths. It finds Dota and Workshop item 474619917 across libraries and prefers the selected Dota library's Workshop copy. Ambiguous/missing paths prompt the friend with instructions, or can be supplied using `-DotaPath` and `-VpkPath`.

`Verify-GemTD-Debug.cmd` verifies a friend's installation. For this junction-based host workspace, run `dist\GemTD-Debug-Friend-Kit\Verify-GemTD-Debug.cmd -Target "F:\CodexProjects\GemTD-Debug\game\gemtd_debug"`. Install/uninstall refuse junction targets. `Uninstall-GemTD-Debug.cmd` prompts for YES and moves the addon outside `dota_addons` to a printed backup path. Rebuilds likewise preserve the old directory and swap in verified staged content; no recursive deletion is performed. The original Workshop directory and authoring content tree are untouched. Close Dota before normal install/uninstall; `-Target` is an explicit advanced/test override for isolated directories.

Validation: `tools/test_friend_kit.py` tested the actual unpacked ZIP with Windows PowerShell 5.1: wrong-version rejection, clean extraction, direct byte comparison of all 2,508 files to the host, no-op reinstall, cache handling, unexpected/changed file rejection, backup-preserving rebuilds, uninstall/repeated uninstall, junction refusal, actual Steam discovery, and the CMD wrapper. All passed; see `tools/friend-kit-validation.json`. `tools/build_friend_kit.py` reproduces the package from the frozen baseline and current runtime. Test folders and Python dependencies under `tools` are not distributed. No gameplay files were changed in this installer task. The user has confirmed direct-IP Internet connectivity. The new player-initialization compatibility patch still needs a real two-player test; see [MULTIPLAYER_INIT.md](MULTIPLAYER_INIT.md).

## Earlier setup notes (historical)

Current status: the user confirmed normal Dota runtime successfully loads `gemtd_coop`, its UI, normal builds, waves, kills, and round progression. Workshop Tools has a separate Panorama recompilation issue and is outside the current task. The historical baseline instructions below describe the original extraction.

The private developer patch now sets `_G.myself = true` at the start of `Activate()`, before `InitGameMode()`. `OnPlayerSay` uses a local Steam-ID-only record if a player's backend record is absent in developer mode; it does not insert a partial record into the shared player table. The shared `_G.crab`, normal build function, and anti-cheat functions are unchanged. Only `scripts/vscripts/addon_game_mode.lua` was changed in the runtime tree by this patch. Existing whitelist changes and Tools caches were preserved.

Review `tools/debug-mode.patch`. `tools/check_debug_mode.py` passes full-file Lua 5.1 syntax compilation and stubbed activation/chat tests using Lupa 2.8 under `tools/.test-deps`, including two players without backend records, shared crab assignment, gold, debug toggles, level selection, spawn dispatch, and preservation of existing player records. It compares runtime hashes to `tools/pre_debug_file_hashes.json` and verifies that the original build and anti-cheat code are unchanged. These tests do not simulate Dota tower creation.

For the next manual test, restart normal Dota, run `sv_cheats 0` then `dota_launch_custom_game gemtd_debug gemtd_coop`. After selecting a builder, use chat `-debug`, `-money`, `-crab heiyaoshi`; build once normally and check for Black Obsidian. Use `-crab jingangshikulinan`; build once normally and check for Cullinan. A further unforced build should use normal random selection. The pending override is shared and consumed by the next successful normal build by any player. Once no wave is active, use `-choose 20`, then `-spawn` once; verify level 20 enemies spawn. Report the first Lua error if any. Hidden commands still require a valid initialized hero, and their existing argument requirements are unchanged. Do not use generic Dota unit/cheat commands.

Prepared 2026-09-24 from installed Workshop item **474619917**, without changing any packaged file. Ready for the first unmodified Workshop Tools launch; an actual in-engine smoke test remains to be performed.

## Provenance and verification

- Upstream: `F:\Steam\steamapps\workshop\content\570\474619917\474619917.vpk` (233,630,570 bytes).
- Publish metadata: title `GemTD`, source folder `gemtd`, publish time `1789652562`, original readable value `09/17/2026 09:42:42 下午`.
- SHA-256: `47714373031d769c8cb12efd6e3f69633cfc3f1418578e5c1b804c4180e1bb2c`.
- Extracted **2,508 files**, **233,527,825 bytes**. All entry CRC32 checks passed, and every written file was read back and compared by SHA-256. VPK tree, hash-section, and whole-file MD5 checks passed. Modern Blake3 chunk hashes and publisher signatures were not independently verified; these are not needed for the byte-for-byte extraction comparison.
- `baseline/manifest.json` pins the archive, metadata, and every extracted file. `baseline/474619917.vpk` and `baseline/publish_data.txt` preserve the upstream snapshot against future Workshop updates.
- `baseline/maps.json` records inspection of the three playable-map packages without unpacking them into the runtime tree. Their inner entry CRCs and available MD5s passed. The older race package omits two section hashes, but its whole-file MD5 passes.
- Steam app manifest reports Dota build `25493322`, with Workshop Tools DLC `313250` installed. This is the engine build, not a GemTD version number.
- No files were taken from the public source reference repository. The installed VPK is the sole baseline authority. The original Workshop directory was only read.

## Layout

```text
GemTD-Debug/
  game/gemtd_debug/       Exact extracted runtime addon
    addoninfo.txt        Playable addon metadata (original KV3)
    scripts/             Lua, NPC KeyValues, shops, network/event declarations
    maps/                Compiled map VPKs, including original backups
    panorama/            Compiled UI plus the few shipped source files
    resource/            Localization, UI images, whitelist/filter files
    models/, materials/, particles/, soundevents/, sounds/
    effect/, effects/, content/, gem/, gemtd/, gemtd2/, mod/, sm/, sm2/, ...
                         Other original resource paths, preserved exactly
  content/gemtd_debug/    Empty source-authoring directory
  baseline/              Frozen archive, metadata, per-file manifest, map report
  tools/vpk_baseline.py   Reproducible extractor/verifier
```

The junctions are on the Dota side, targeting the workspace:

```text
F:\Steam\steamapps\common\dota 2 beta\game\dota_addons\gemtd_debug
  -> F:\CodexProjects\GemTD-Debug\game\gemtd_debug
F:\Steam\steamapps\common\dota 2 beta\content\dota_addons\gemtd_debug
  -> F:\CodexProjects\GemTD-Debug\content\gemtd_debug
```

The archive supplies compiled resources, not a complete authoring project. There are no uncompiled `.vmap`, `.vmdl`, `.vmat`, `.vtex`, or `.vpcf` source assets. Lua/KV stay under `game`; compiled maps remain packaged. Nothing must be copied to `content/gemtd_debug` for this launch. The archive's own `content/` subfolder contains 54 compiled particle resources and remains at its original runtime path. It is not the Workshop Tools source tree.

Do not rebuild the maps or bulk-decompile/recompile assets for this baseline. Some packaged Panorama XML/CSS sources coexist with compiled versions and may not represent equivalent UI; keeping both exactly as shipped avoids replacing the working compiled UI. Future original source assets or deliberate reconstruction would belong under the matching `content/gemtd_debug` paths.

## Code and resources inspected

- `scripts/vscripts/addon_game_mode.lua`: `Precache` at line 72, `Activate` at 633 prints `GemTD START!`, creates `GemTD`, and calls `InitGameMode` at 2546. It loads pathfinding, timers, AMHC, physics, JSON/MD5 and Drodo helpers. `bit` is an engine-provided module.
- `scripts/npc/npc_abilities_custom.txt`: data-driven abilities, including `gemtd_build_stone`, call the existing Lua code. Other principal KV files are `npc_units_custom.txt`, `npc_items_custom.txt`, `npc_heroes_custom.txt`, `herolist.txt`, `activelist.txt`, and `portraits.txt`.
- `scripts/custom_events.txt`, `scripts/custom_net_tables.txt`: client/server communication. The net tables include `game_state`, `game_maze`, `gemtd_ranking`, and `player_info_table`.
- `panorama/layout/custom_game/`: loading screen, UI manifest, boards, scoreboard and team selection. Most actual UI logic/styles are compiled `.vjs_c`, `.vxml_c`, and `.vcss_c` resources.
- `resource/addon_english.txt`, `addon_schinese.txt`, `addon_tchinese.txt`: localization. Resources also include compiled models/materials/textures/particles/audio and original nonstandard directory names.
- Existing developer behavior is unchanged: `_G.myself` is set for existing developer Steam IDs in `OnPlayerConnectFull` (around 13589); chat commands begin around 7528; `_G.crab` substitution/clear occurs at 5130–5132. None has been enabled for additional players.
- Existing anti-cheat remains: `DetectCheatsThinker` at 2532 checks game cheat mode and `sv_cheats`; `StartGame` installs it when `_G.myself` is not true. Original HTTP/backend requests also remain, so successful offline operation and backend behavior must be assessed in the smoke test.

## First unmodified launch

1. In Steam, launch **Dota 2 → Launch Dota 2 - Tools** (Workshop Tools). Alternatively open `F:\Steam\steamapps\common\dota 2 beta\game\bin\win64\dota2cfg.exe`.
2. Select the existing **gemtd_debug** addon and choose **Launch Dota 2**. If the launcher was already open before extraction, close and reopen it to refresh. Do not create a new addon or use a template over this directory.
3. In the attached Workshop Tools VConsole2 (open `game\bin\win64\vconsole2.exe` if needed), enter:

   ```text
   sv_cheats 0
   dota_launch_custom_game gemtd_debug gemtd_1p
   ```

4. Once the map loads, query `sv_cheats`; if it reports `1`, immediately enter `sv_cheats 0` before starting the round. Leave lobby cheats disabled. The unmodified addon can declare a loss if either cheat flag is active. If Tools still creates a cheat-mode game despite this, report it; it is a baseline compatibility finding, not permission to change the addon.
5. Look for `GemTD START!`, working custom UI, normal builder/hero selection, and a normal tower build followed by wave start. Do not use the hidden developer commands for this baseline check.

Please return whether the addon appeared in the launcher, whether the map/UI loaded, and whether you could build normally and start a wave. On failure, return the first Lua error and surrounding console output, or the exact loading/cheat-detected message and the queried `sv_cheats` value.

Map inventory from original `addoninfo.txt`:

| Map | Role | Players | State |
| --- | --- | --- | --- |
| `gemtd_1p` | First smoke test; default map | 1 | Listed and packaged |
| `gemtd_coop` | Future cooperative testing | Up to 4 | Listed and packaged |
| `gemtd_race` | Legacy race variant | Original commented option says 4 | Packaged, commented out of playable list |

Future cooperative command: `dota_launch_custom_game gemtd_debug gemtd_coop`. This identifies the local test map; friend connectivity/distribution is not yet tested or configured.

The command format is documented in [Valve's Playing Addons guide](https://developer.valvesoftware.com/wiki/Dota_2_Workshop_Tools/Addon_Overview/Playing_Addons?uselang=ru), and this installed Dota's `gameinfo.gi` sets `AddonMapCommand` to `dota_launch_custom_game`. Local addon metadata has `IsPlayable = 1`, `HideInTools = false`, `IsTemplate = false`, and `DefaultMap = "gemtd_1p"` already; no registration edit was necessary.

## Reproduce or verify

Tools used: PowerShell, ripgrep, and the Codex-bundled Python runtime with a standard-library VPK reader. No extractor was found in Dota/Steam common, on PATH, or in checked standard tool locations. Dota supplies `resourcecompiler.exe`, `resourceinfo.exe`, `resourcecopy.exe`, `dota2cfg.exe`, and `vconsole2.exe`; none was needed to rewrite or rebuild assets.

Run from `F:\CodexProjects\GemTD-Debug` in PowerShell:

```powershell
$gemtdPython = 'C:\Users\Illidan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
# Compare against the installed Workshop copy AND the pinned manifest:
& $gemtdPython tools\vpk_baseline.py verify
# Verify against the preserved snapshot after Steam updates upstream:
& $gemtdPython tools\vpk_baseline.py verify --source baseline\474619917.vpk
# Reconstruct in a separate EMPTY directory, without overwriting ongoing work:
& $gemtdPython tools\vpk_baseline.py extract --source baseline\474619917.vpk --target baseline\reconstructed
```

The extractor rejects nonempty targets and unsafe archive paths. Verification reports added/missing/changed files, including files the engine may generate later. A changed Workshop version is rejected against the pinned manifest; use a separate target and manifest for a future upgrade. Runtime folder naming is independent of the upstream metadata's `source_folder = gemtd`, so the private addon can be mounted as `gemtd_debug` without altering packaged files.
