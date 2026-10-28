# Phase 6A: experimental shared allied rounds

The first manual one-PC playtest reported obscure defeat feedback, an overloaded
interface and isolated Blue/Green turns. This branch responds with shared allied
rounds, an optional details view, short committed results and prominent terminal
presentation. It is a playable experiment for comparison, not human acceptance of
the new pacing. Stable main remains `8027a8dea`; this work is published separately
on [codex/shared-allied-turns](https://github.com/Eren-Enou/FireEmblem-GBA-Coop/tree/codex/shared-allied-turns). Sequential remains the default on both branches.

## One-PC comparison and retry

From the actual `FE-GBA-Coop` root, with the existing Python 3.12 environment:

```powershell
# Sequential comparison: Blue -> Green -> Red (default).
.venv\Scripts\python.exe run_solo.py --turn-mode sequential

# Experimental: both commanders act, both Ready, then Red.
.venv\Scripts\python.exe run_solo.py --turn-mode shared
```

Each command opens a fresh native host and two independent visible Pygame clients.
Alt+Tab between Blue and Green; move windows side by side if convenient. The
launcher prints a unique ignored `artifacts/solo/run-...` directory for private
invitations/logs and, in sequential campaign mode, a **new** checkpoint directory.
It never restores or overwrites a previous run's saves. TLS/WAN is not configured
by this local loopback launcher.

1. Select Aren in Blue and Tovan in Green. Both can move in shared round one.
   A move is proposed locally; Enter confirms, Esc/right click cancels. The other
   client sees the committed position, not an unconfirmed proposal.
2. Select Mira/Sela, choose Heal and click the wounded opposite-army captain.
   Mint targets are legal healing; healing commits immediately through native LT.
   W waits; F shows combined enemy threats; I toggles inspection details.
3. Press E in one client: its army is READY and stops accepting actions. The
   other army can still act. Only its E starts native Red AI. Next round both
   readiness votes clear and surviving characters recover normal actions.
4. Try acting quickly from both clients. One request based on an old revision may
   reject. Read the resync notice, inspect the new board and choose again. There
   is no automatic replay. An uncertain/disconnected command must be resolved by
   rejoining with the same live host invitation, never guessed and resent.
5. Close one client to test pause. Reopen it using its printed invitation:
   `.venv\Scripts\python.exe run_network.py client --session-file <path>`.
   Its ready vote persists; new commands require both seats connected.
6. A terminal panel identifies SHARED VICTORY or SHARED DEFEAT and the eliminated
   army when known. To retry, close both clients, Ctrl+C the launcher, and rerun
   the same command. It starts a **new process, session and credentials**. There
   is no in-process reconstruction or mid-map recovery.

For three separate terminals, choose one host command, then both client commands:

```powershell
.venv\Scripts\python.exe run_network.py host --scenario campaign --turn-mode shared --seed 0 --session-dir artifacts/shared-manual
.venv\Scripts\python.exe run_network.py client --session-file artifacts/shared-manual/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/shared-manual/green.json

# Alternatively, start the unchanged sequential scheduler with a fresh save folder:
.venv\Scripts\python.exe run_network.py host --scenario campaign --turn-mode sequential --seed 0 --checkpoint-dir artifacts/sequential-comparison --session-dir artifacts/sequential-manual
.venv\Scripts\python.exe run_network.py client --session-file artifacts/sequential-manual/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/sequential-manual/green.json
```

Stop the first host before starting the alternative on the same default port.
Existing verified TLS options also work with `--turn-mode shared`; no insecure
remote fallback is introduced. See [Internet setup](INTERNET_PLAY.md).

## Exact native shared-round policy

`SharedSimulation` is an opt-in subclass in `app/coop/shared_turns.py`. The
sequential Simulation, native engine, campaign/preparation code and checkpoint
manifest/schema are unchanged. Neither tactical teams, permanent owners, parties,
classes, items nor chapter manifests are merged or replaced.

| Boundary | Native behavior |
| --- | --- |
| Round opening | Normal native transition into Blue increments turncount once, updates turn records/time regions, triggers TurnChange/Blue PhaseChange and performs Blue phase-change/reset/upkeep. Before publishing, the coordinator enters Green phase-change/reset/upkeep and triggers Green PhaseChange/OtherTurnChange once. |
| Allied input | Public phase is Blue (`player`), with `turns.mode=shared`. Each accepted action sets the native phase current pointer to its owning team for selection, combat and canto, invokes the unchanged adapter/native action, settles and restores Blue before publication. No reset/upkeep/phase event occurs between actions. |
| First Ready | Records only that army's vote. It cannot submit further tactical actions this round; the other army retains all legitimate remaining actions. Readiness is not an implicit Wait on its characters. |
| Second Ready | Blue native status_endstep runs once. The unchanged Green end-phase path runs Green endstep, transitions into Red, runs native AI/upkeep/endstep and enters the next Blue turn. Green opening upkeep then runs before the next public allied barrier. |
| Next allied round | Both votes clear. Both opening ResetAll calls happen before any input; neither can replenish an action mid-round. Red's own native reset also occurs while input is locked. |
| Terminal result | Native objective flags stop further commands. A terminal effect can short-circuit subsequent coordinator work; the frozen terminal board is never an actionable next round. |
| Chapter transition | Separate campaign intermission votes load the unchanged next chapter with native cleanup/start_level. Its normal Blue opening and explicit Green opening finish before publication. |

LT's `PhaseChangeState` normally calls ResetAll on **every** living unit, not just
the entering team. Consequently entering Green after Blue has acted would grant
extra actions. The experiment moves Green's full phase opening ahead of both
armies' input. `StatusUpkeepState` selects the current team, so it must run once
for each army; just bypassing wrong_phase would omit Green status/healing timers.
`human_control.selection_allowed` still checks the native current team. Scoped
phase selection makes owned Green actions legal through that existing check.
The pointer is restored even on rejection; unexpected resolution failures freeze
the host. PhaseController.previous is left to native transitions; no undo/turnwheel
or general story-event parity is claimed for the experimental scheduler.

Status Time decrements once per army's opening; EndTime once per closing endstep.
Native regeneration/item/terrain upkeep occurs once at that army's opening. Staff
and consumable healing occurs on the actual accepted action. Combat/defense XP,
weapon XP, growth, durability, RNG and caps remain native. Ready itself awards no
XP or healing and consumes no durability. Red attacks remain native AI decisions.

The host lock spans the whole command generator, native yields and publication.
Only transport/heartbeat work runs between steps. No thread concurrently mutates
the singleton, and no second simulation is constructed within a live host.

## Synchronization and UI

Wire v8 adds exact bounded `turns: {mode, ready}` and nullable `outcome` fields.
All three processes must update together. Every command still binds authenticated
army, session, revision, digest and phase. Only one same-revision submission can
commit; the stale one rejects **before native action/RNG**. The client requests a
fresh snapshot, clears proposals and asks for a new explicit choice. Another
army's update, including a colliding command ID, cannot clear your pending action.
Only your matching result/rejection resolves it; timeout requires rejoin.

Both readiness votes and unspent character counts are visible. A pending action,
resync or missing peer disables input. Readiness persists through disconnect and
same-seat rejoin. A command accepted before disconnect finishes atomically; new
commands pause until both peers reconnect. No reconnect/host restart auto-replay.

Default presentation shows selected HP/movement/action state, inventory, danger,
simple forecast metrics and short actual HP changes. I reveals full stats, mana,
weapon XP, advanced forecast notes, revision/digest, TLS diagnostics and history.
F retains native threat overlays. Local PROPOSED/SENT versus COMMITTED remain
distinct. Prominent terminal panels cover both clients and give retry instructions.
The full bounded host summary remains in the packet for diagnosis, rather than
being the primary gameplay message.

## Checkpoints and scope

**Shared mode is live-only: no checkpoint save, restore or intermission convoy/
equipment preparation.** CLI and constructor reject checkpoint/restore arguments
before native startup. Existing shared inventory items, Vulneraries, healing,
progression and live two-chapter continuation work. This restriction leaves the
current save contract untouched; it does not silently reinterpret sequential
phase/checkpoint state. Sequential preparation, checkpoint saving and fresh-host
restore retain their existing behavior. Old saves must still pass exact validation.
Do not add shared saves without a versioned lifecycle and recovery design.

No new classes, chapters, recruitment, promotion, trading, mid-map saves, assets,
or licensing changes. Original engine attribution and MIT license remain.

## Actual verification and remaining work

Initial focused native/transport/model run: **8 passed in 13.478 seconds**. An
earlier test fixture failed because it used generic Data instead of native
ComponentData for skill hooks; the fixture was corrected before that passing run.

TLS graphical campaign: `artifacts/shared-smoke/run-b9c3fbfb`, host **108652**,
clients **89368/149992**, **46 identical snapshots**, revision **45**, shared
victory across both chapters; digest
`b99f1569e5b193428d24b7cc605cbd27c721354f6ca40fc0b7d5533dddf6290a`.
Opening, one-ready (Chapter 2) and victory captures were visually inspected.
The smoke uses two headless SDL graphical clients rendering the real UI, not two
human-operated windows. It precedes final pending-ID/fault-message/detail fixes.

Final focused repair/input/model run: **20 passed in 34.951 seconds**. The first
combined run executed 229 tests in 545.681 seconds with one failure and one error:
a legacy assertion expected the raw rejection message, and the new artificial
50-pongs/second heartbeat test hit admission limits. Raw diagnostic rejection text
is now preserved alongside separate friendly gameplay feedback; heartbeat cadence
was corrected to 10/second. An intermediate retry was interrupted to fix a new
test teardown ordering hang (closing live clients before waiting for server close).
The focused pass covers both repairs, shared disconnect/readiness and existing
inventory/model input checks. Admission limits and native gameplay were not relaxed.

Final TLS shared victory: `artifacts/shared-smoke/run-6909c8c9`, host **152440**,
clients **117768/153096**, **46 matching snapshots / revision 45 victory**, digest
`fb75837f2a6176a5304a473fbc1b052ef1a2c30404af64f813ada459a177107d`.
Final TLS passive defeat: `artifacts/shared-smoke/run-2b0eb690`, host **144124**,
clients **5464/18848**, **13 matching snapshots / revision 12 defeat**, digest
`076942e42f41be7ee660d058e3d47b01e8f7e9d68be5ae88a1389e374464c37a`.
The latter is a real native Red AI loss with **Blue army eliminated**, not a
client-injected terminal flag. Opening, Chapter 1 one-ready, victory and defeat
captures were inspected. Read-only renders from the final revision-6 packet
(`artifacts/phase6a-ui-review`) compare basic/details forecast views: the same
packet/proposal, one observed state, no pending command and no sends. Stats,
WEXP, advanced notes and digests appear only in details; no overlaps were found.

An additional audit of those committed victory observations checked every
heal/attack's native action completion, XP increase, nondecreasing WEXP and
nonnegative own-item charge loss, plus unchanged units/RNG at first Ready.
Blue performed **6 heals / 4 attacks**, Green **5 / 5**, with **9 own-action
charges each**. Each captain had one missed attack with no charge loss, consistent
with LT's native Uses.on_miss/uses_options policy. No synthetic damage or XP.
Final surviving characters: Aren L2/89 XP, Mira L2/61, Tovan L3/72, Sela L2/50.

A second fresh shared launch (133524/109956/164972) and a sequential launch
(147524/161056/134432) both started three real processes and cleaned up all owned
children. New invitations differed between runs; the earlier invitation file was
byte-for-byte unchanged. No prior checkpoint directory was reused.

Final combined regression: **229 tests passed in 526.102 seconds** on October
28, 2026 (`artifacts/phase6a-regression-final.log`), using the full command in
[TESTING.md](TESTING.md). This includes all 218 selected prior checks plus the 11
shared-round cases. No runtime or test source changed after this passing run.
The run covers native shared mechanics, same-revision races, disconnect during
resolution/rejoin, model pending state, tactical/SDL input, sequential campaigns,
prepared checkpoint save/recovery, healing/progression, transport/TLS and selected
native movement/AI/XP/save regressions. This is a targeted regression selection,
not the full upstream suite. Final asset/credential audit stages only Python and
Markdown; native engine, sequential save rules and attribution remain unchanged.


Reproduce from the repository root:

```powershell
$env:PATH = 'C:\Ruby33-x64\msys64\usr\bin;' + $env:PATH
.venv\Scripts\python.exe -u -m unittest app.tests.test_shared_turns -q
.venv\Scripts\python.exe -u utilities/smoke_shared_turns.py --tls
.venv\Scripts\python.exe -u utilities/smoke_shared_turns.py --tls --defeat
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --preparation --tls --recovery corrupt
```

The controlled test interleaves Green movement, cross-army native Heal and Blue
actions before both votes, verifies ownership/extra-action rejection and real Red
movement, checks native XP/charge loss, Time/EndTime/Regeneration and exact upkeep/
endstep/phase-trigger counts. Transport tests race same-revision votes, pause on
disconnect, preserve readiness on rejoin and disconnect during AI resolution while
heartbeats continue. The graphical campaign exercises native combat for both
armies, live chapter cleanup/progression and identical per-action publication.

Mechanics verdict: the tested trusted scenarios provide a sound basis for comparing
shared and sequential rounds. Broader LT story events/phase-dependent skills,
supports/pair-up, turnwheel and arbitrary maps are not certified. Shared checkpoint
support remains blocked by a deliberately unextended save contract. Separate-PC
Internet play and a new human comparison of pacing, concurrency friction, details
discoverability and defeat/retry usability remain unperformed. Prior tactical
limitations (current blockers, no fog, unavailable complex forecasts) still apply.
