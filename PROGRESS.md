# Progress — October 27, 2026

## Delivered

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

The architectural assessment is in ARCHITECTURE.md; later work is in ROADMAP.md.
No networking or campaign conversion was started.

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

## Limits and next work

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
