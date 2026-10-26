# Direct-connect initialization patch

New build: **946DE6E9DDE8C806**. Full fingerprint: `946de6e9dde8c806a6cf9927046282c455d7c96772b849563be5070df43072d7`.

Status: local Lua/controller tests passed; the real Internet two-player test is pending. The previously tested build was `270CF146D1588153`. Networking, Panorama, towers, debug commands, and balance were not changed.

## Confirmed source failure path

Only `game/gemtd_debug/scripts/vscripts/addon_game_mode.lua` changed relative to the previously tested runtime. The old `OnPlayerStartTeamSelect` requested the initial roster once behind `_G.is_heros_get_sended`. `OnPlayerConnectFull` updated player counts without fetching information for later arrivals. The Riki placeholder path in `OnPlayerPickHero` called `SetGameWinner(DOTA_TEAM_BADGUYS)` if `player_info_<steamid>` was absent. This confirms a failure path consistent with the reported symptoms; the next live logs will establish whether any additional runtime problem remains. Riki itself is GemTD's expected placeholder before the backend-selected hero is created.

## Changes

- `InitVaribles` resets controller state each game. Debug-only connect/reconnect and team-select hooks start one real-time watcher during setup.
- The watcher scans connected player slots (including sparse IDs), excludes zero Steam IDs and disconnected players, and checks original `player_info_table` entries. It logs newly seen players and the complete ready roster.
- Missing records trigger the **original HTTP endpoint and original publication/quest handling** for the current connected roster. No synthetic backend records are created. Existing valid records/quests are retained during a refresh. The response must contain requested records with the structures directly needed by the original hero initialization (`hero_sea`, `quest`, `onduty_hero.hero_id`).
- At most one request is outstanding. If a new player arrives during it, the next watcher pass requests the updated roster. Failure retries back off by 5 seconds per failure up to 30 seconds, using real time; the HTTP timeout remains 20 seconds. Invalid JSON and incomplete results are logged and retried. Old-game callbacks and stale hero handles are discarded. A reconnect with valid information does not refetch it.
- A Riki pick without information is queued **before** stripping abilities, adding particles, inserting into `_G.hero`, or invoking the old loss branch. It resumes automatically once the record arrives and initializes only once. The original missing-record loss branch remains for non-debug execution.
- An early custom hero-choice event is safely ignored with a log; select again after READY. It does not dereference a missing table or fabricate a choice.
- The original delayed `StartGame()` path is scheduled once in debug mode and waits for pending picks and asynchronous hero replacement (`_G.playerid2hero`) to finish. Engine game state may advance during a slow response, but GemTD initialization waits rather than awarding the missing-record loss. Backend errors can leave it waiting; recovery is automatic when a valid response arrives. Explicit backend `blocked`/blacklist decisions are retained.
- After setup, no new refresh is started unless a hero initialization remains pending. All compatibility control flow is gated by `_G.myself == true`. Original non-debug request/hero behavior remains intact.

## Next two-player test

1. Both players close Dota. Friends extract the new `dist/GemTD-Debug-Friend-Kit.zip`, run `Install-GemTD-Debug.cmd`, and enter `REBUILD` for the old build. Then run `Verify-GemTD-Debug.cmd` and confirm **946DE6E9DDE8C806**.
2. The host's workspace is already patched. Verify it with `dist\GemTD-Debug-Friend-Kit\Verify-GemTD-Debug.cmd -Target "F:\CodexProjects\GemTD-Debug\game\gemtd_debug"`. Do not install over the host's junction.
3. Host launches normal Dota, runs `sv_cheats 0`, then `dota_launch_custom_game gemtd_debug gemtd_coop`.
4. Wait for the host-only READY message. This deliberately exercises joining after the initial fetch. Friend runs `connect <host-public-ip>:27015`.
5. Both run `jointeam good` as in the proven network test. Before pressing Start Game, wait until the **host console** reports READY with **both actual Steam IDs**, then select heroes where the existing UI permits it.
6. Press Start Game. Expect `hero init READY` for both players, normal hero replacement, no immediate missing-info Dire victory, and working building/waves.
7. In a separate fresh session, optionally start immediately after the friend joins to exercise the request race. A `hero init WAIT` must be followed by `hero init READY` once the response arrives; it must not cause an immediate missing-record loss. Do not interpret a backend outage as successful initialization.

Expected host console sequence (replace placeholders with actual IDs; success/READY messages may be separated by about one second):

```text
[GemTD Debug] player connected id=0 steamid=<host-id>
[GemTD Debug] player-info refresh started steamids=<host-id>
[GemTD Debug] player-info refresh succeeded steamids=<host-id>
[GemTD Debug] player-info READY steamids=<host-id> (all connected players; safe to Start Game)
[GemTD Debug] player connected id=1 steamid=<friend-id>
[GemTD Debug] player-info refresh started steamids=<host-id>,<friend-id>
[GemTD Debug] player-info refresh succeeded steamids=<host-id>,<friend-id>
[GemTD Debug] player-info READY steamids=<host-id>,<friend-id> (all connected players; safe to Start Game)
```

After Start:

```text
[GemTD Debug] hero init READY id=0 steamid=<host-id> player_info=true
[GemTD Debug] hero init READY id=1 steamid=<friend-id> player_info=true
```

If started too early:

```text
[GemTD Debug] hero init WAIT id=1 steamid=<friend-id> player_info=false; waiting for backend
```

Failures report `player-info refresh failed HTTP=<status>`, `invalid response or backend error`, or `missing/incomplete requested records`, followed by `retry scheduled`. Do not press Start on these messages; wait for the two-ID READY line. Return these logs and any first Lua error. If the friend's UI still cannot select a hero after READY, report that separately; Panorama was deliberately not changed.

## Local verification

- `tools/test_multiplayer_init.py`: compiles the full Lua file and exercises the actual Lua request/controller/hero handlers with stubbed engine APIs and HTTP callbacks. Covers overlapping joins, sparse IDs, single-flight requests, retries, incomplete data, reconnects, hero waiting/deduplication, asynchronous replacement gating, stale responses/entities, non-debug behavior, and retained backend blocking.
- `tools/check_debug_mode.py`: prior developer activation/chat regression checks and unchanged tower/anti-cheat code comparisons.
- `tools/test_friend_kit.py`: actual Windows PowerShell 5.1 installation from the original VPK, all 2,508 files compared byte-for-byte with current host runtime, verification/rebuild/uninstall/version rejection tests. Four Tools caches remain excluded; the tested whitelist is included and unchanged from the prior kit.
- Review `tools/multiplayer-init.patch` for this task's runtime diff and `tools/debug-mode.patch` for the cumulative diff from the subscribed baseline. `tools/friend-kit-validation.json` records the installer test results.
