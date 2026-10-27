# Progress — October 27, 2026

## Current milestone: Phase 2 local network multiplayer

Implemented a working vertical slice extending the existing hot-seat map:

- `run_network.py host`: one authoritative LT engine process, listening only on
  loopback. `app/coop/simulation.py` reuses LT movement, combat/counters, inventory
  durability, RNG, phase/upkeep/event handling and enemy AI. No second solver or
  test-harness dependency is used in production.
- `run_network.py client`: two separate pygame client processes/windows, each
  with independent input and an original geometric map renderer. Blue and Green
  are bound to host-generated credentials and exclusive seats. Commands contain
  tactical intent, not keyboard events or remote desktop frames.
- Version 1 strict, bounded JSON contract; Move/Attack/Wait/EndPhase requests;
  ownership, phase, path/occupancy/range/inventory checks on the host; per-army
  unique IDs; stale, duplicate, malformed and wrong-session rejection.
- Host-only random resolution and ordered authoritative snapshots. Both clients
  see positions, HP, inventories/durability, turn, objectives, all three RNG
  stream states and the same projection digest/revision. Green End includes the
  entire Red AI phase as one atomic command result.
- Live-host disconnect pause, same-army rejoin using the existing credential,
  manual resync and automatic checksum-failure resync. Unexpected engine failure
  publishes a terminal fault revision and freezes further commands.
- The final board remains visible on shared victory/defeat; no campaign/title
  transition or save is attempted by the network session.
- Added isolated `app/coop/` modules, launchers, a three-process smoke utility and
  networking tests. No additional upstream engine source edits or binary assets.

The executable contract and precise limits are in
[NETWORK_PROTOCOL.md](NETWORK_PROTOCOL.md). Launch commands, controls and test
procedures are in [TESTING.md](TESTING.md).

### Verified evidence

- Real three-process graphical smoke passed: one host, distinct Blue and Green
  client PIDs, 10 identical observed snapshots, final revision 9 on Green turn 2.
  Both armies moved and used real LT combat with HP/durability changes; Red AI
  moved/fought on the host. Blue rendering was visually inspected. Reports,
  screenshots, logs and credentials remain ignored local outputs. The final
  Green rendering was also visually inspected.
- Standalone network suite: **22 passed in 23.580 seconds**. Includes actual TCP
  reconnect/resync, fragmented requests with 20ms delays, malformed frames and
  wrong credentials, as well as real-client recovery from an injected bad digest.
- Earlier combined run: **94 passed in 54.016 seconds**, covering 21 network tests
  plus all 73 existing selected hot-seat/AI/movement/canto/save regressions.
  Final combined run including automatic recovery: **95 passed in 52.002 seconds**
  (22 network tests plus 73 existing selected regressions).
- Final CLI smoke rerun passed with host PID 42488, client PIDs 165580/137864,
  10 matching snapshots, revision 9 and matching state digest. Both graphical
  clients completed their scripts; the utility stopped its own child processes.
- Final staged audit passed for 17 Python/Markdown files: Python syntax and
  staged whitespace valid, 31 resolving local document links, no new media or
  matching credential signatures, no tracked local outputs and unchanged
  upstream license/credits. This is a scoped audit, not a full historical scan.
- No full repository suite, manual two-person UI playthrough, internet/separate-PC
  session, load/packet-loss test, full security audit or campaign persistence test
  has been completed. Existing editor smoke was not rerun: no editor code changed.

### Limits, blockers and next steps

This is genuine local client/server gameplay, not the finished product. Clients
use a minimal independent map interface, with immediate committed moves and
authoritative result updates rather than full LT menus/combat animations. Only
move, axe attack, wait and end-phase are supported on the original test scenario.
Green XP/leveling parity, healing/trade/abilities, recruitment, deployment,
multi-chapter progression and campaign saves remain unimplemented.

Transport is plaintext, loopback-only; token possession grants that army's seat.
Do not forward/expose its port. Live-host rejoin needs a manual client relaunch;
host restart loses the session. Snapshot hashes cover the documented projection,
not a complete restorable LT campaign. Host resolution temporarily blocks I/O.
Inherited sample asset rights still need auditing before a distributable game.

Next actionable work: two-human local exploratory playtesting, then design
internet transport/server identity and safe credentials before any public
connectivity. Expand tactical commands/progression using the existing engine,
and define a separate validated campaign-save schema rather than treating the
v1 projection as a save file. See [ROADMAP.md](ROADMAP.md).

### Experiments and fixes

- Direct LT adapter probe resolved movement, Green combat/counters and a Red AI
  round before adding the transport, without modifying the existing engine.
- An initial negative test reused a request ID and reached duplicate rejection
  before wrong-session validation. The test now uses distinct IDs; duplicate
  priority and no-mutation behavior remain intentional.
- Review caught Python's non-ASCII string compare_digest limitation;
  authentication uses UTF-8 bytes, with a raw-socket rejection test.
- An automatic-recovery socket test corrupts one published snapshot and verifies
  a real client discards it, requests the unchanged authoritative revision, and
  converges exactly with the other client without another simulation action.

## Earlier milestones (historical records)

## Repository maintenance milestone

- Canonical project repository: `https://github.com/Eren-Enou/FireEmblem-GBA-Coop`.
  Verified `origin` points there and `upstream` still points to
  `https://gitlab.com/rainlash/lt-maker.git`; no remote reconfiguration was needed.
- Active checkout: `FE-GBA-Coop/`, with an independent `.git`. The enclosing
  workspace Git repository is empty and is not the publication target.
- The completed local prototype was already committed and published as
  `36f6552ddbc7004fdbfa7fb5e99df0907983bba3` on GitHub `main`.
- Moved project status, roadmap, testing and architecture into `docs/`. Updated
  README links and AGENTS.md with goals, architecture constraints, conventions
  and the required test/document/commit/push/remote-verification workflow.
- Preserved the existing local ROM ignore additions and added guards for common
  credential files, private assets and test outputs. No runtime code changed.
- Preserved original MIT license, attribution, third-party notices and upstream
  history. [Asset policy](ASSET_POLICY.md) distinguishes inherited resources from
  newly added files; no asset rights are assumed from the engine code license.
- Re-ran code generation and the targeted suite: **73 passed in 28.443 seconds**
  on October 27, 2026. Prior rendered driver/editor smoke results below remain
  applicable; they were not rerun for these documentation/ignore-only changes.
- Publication checks passed: 8 staged text files (including renamed documents),
  20 resolving local documentation links, no staged media or matching credential
  signatures, no tracked local-output paths, clean staged whitespace check, and
  unchanged original license/credits files. This is a scoped staged-change check,
  not a full historical secret or asset-rights audit. Remote revision verification
  is the final step after committing and pushing this record.

Current blockers: a full inherited-asset rights audit is required before any
standalone distribution. The old test fixture's portrait migration issue remains
as described below. No blocker to the documentation milestone or local tests is
known. Online gameplay is unimplemented, not a verified capability.

Next steps: two-person local exploratory playtest, then design the authoritative
command/result/snapshot contract and implement the Phase 2 local-network proof
of concept. Follow the milestone workflow in [AGENTS.md](../AGENTS.md).

## Earlier Phase 1 delivery

The first assignment's local experiment is implemented. One engine instance
supports two separately owned allied armies on an original map: two Blue units,
two Green units and three Red AI enemies. Turn order is Blue -> Green -> Red;
the round increments once when Blue returns. Both human armies can select,
move, attack and wait through the existing tactical engine. Shared victory and
either-army elimination defeat use ordinary LT events.

Entry point: `run_coop.py`. It loads `default.ltproj`, installs the scenario only
in memory, and starts directly on the map. Original terrain and token graphics
are drawn by code. Neither shipped project is edited.

Ownership policy is isolated in `human_control.py`; state routing, selection,
auto-end, AUX cycling and interrupted movement have small integration changes.
The generated skill system is regenerated from its editable source. Existing
Blue-only behavior remains the fallback when the opt-in game var is absent.

The architectural assessment is in [ARCHITECTURE.md](ARCHITECTURE.md); later work
is in [ROADMAP.md](ROADMAP.md).
At that milestone no networking or campaign conversion had been started; current
networking status is recorded above.

## Verification

- Before engine changes: 7 existing AI fixture tests passed through the real
  engine harness, including sample level startup and gameplay states.
- Targeted suite: 73 tests (16 co-op plus 57 existing AI, movement, canto and save
  regressions). See TESTING.md for the exact command and final result below.
- Actual `run_coop.py --smoke`: passed; normal driver rendered Blue, Green, Red
  AI and Blue turn 2. Screenshots: `artifacts/coop-player.png` and
  `artifacts/coop-other.png`. Green screenshot was visually inspected.
- Editor smoke: passed, `EDITOR_SMOKE_OK`, with a disposable copy of the supported
  default sample. This verifies startup/project loading/rendering, not every
  editor tool.
- The full repository test suite was not run. No internet sessions, independent
  clients, latency, reconnection or synchronization tests have been performed.

## Findings and unsuccessful experiments

- Initially attempted editor startup without translation initialization; it
  correctly failed with missing `_`. The repeatable smoke script follows editor
  initialization and applies the engine's theme.
- The old `testing_proj.ltproj` has version-0 metadata and references missing
  `resources/portraits/lmaoooo.png`. Its migration path fails. Migration was
  attempted on a disposable copy only; the original fixture is unchanged. Use
  the supported `default.ltproj` for the editor and co-op experiment.
- The first draft used display names for an axe and terrain instead of their
  resource IDs. The scenario now uses `Iron_Axe` and terrain IDs `1`, `2`, `9`;
  tests assert resources exist.
- An initial path test incorrectly rejected allied tiles from reachability.
  LT permits passing through allies; the corrected test exercises MoveState's
  occupied-destination rejection instead of changing working movement rules.
- A victory check initially tried to observe `_win_game` between frames. LT
  consumes it immediately and performs chapter cleanup. The check observes the
  real completion path and previous-level marker instead.

## Earlier Phase 1 limits and next work

- Local hot-seat control uses one input device and one process. No player
  authentication, server or client synchronization exists.
- Green experience/leveling parity, supports, allied trades, roster menus,
  recruitment and persistent campaign ownership are not implemented or verified.
- Initiative, turnwheel and save/suspend are disabled in this demo. Existing
  single-player save regressions pass; that does not establish co-op save support.
- Some UI, sound and item icons come from installed sample resources; no release
  bundle was created and proprietary assets must not be redistributed.
- Human two-person exploratory playtesting is still outstanding. The next
  engineering milestone is a versioned authoritative command/snapshot design,
  then a minimal local host with two independent clients.

Final targeted-suite result: **73 passed in 27.730 seconds**, including completed
victory cleanup and defeat when either Blue or Green is eliminated.
