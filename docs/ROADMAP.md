# Roadmap

## Repository maintenance (established)

- [x] GitHub `origin` and original Lex Talionis `upstream` verified.
- [x] Canonical progress, roadmap, testing and architecture under `docs/`.
- [x] Goals, conventions and test/document/commit/push workflow in `AGENTS.md`.
- [x] Existing local prototype committed on GitHub (`36f6552dd`).
- [x] Preserve attribution and document inherited-asset audit boundary.
- Ongoing: after every completed, tested milestone update the records, audit the
  staged diff, commit, push to origin and verify the remote branch revision.

## Phase 0: environment and assessment

- [x] Inspect installed upstream engine and pin its baseline commit.
- [x] Run existing sample gameplay via the engine harness.
- [x] Open/render supported default sample in the editor using a disposable copy.
- [x] Document team/phase/input/state/combat/event architecture and local extension.
- [x] Document reproducible environment and targeted tests.
- [ ] Audit all assets before any standalone distribution.

## Phase 1: local two-army experiment

- [x] Separate opt-in human ownership policy with ordinary Blue-only fallback.
- [x] Blue -> Green -> Red phase sequence, one round increment per Blue turn.
- [x] Original map/tokens; two Blue, two Green, three Red units.
- [x] Both armies select/move/wait/attack through existing engine systems.
- [x] Reject the inactive army and Red units even with a selectable skill override.
- [x] Preserve Red AI targeting both human armies.
- [x] Shared rout objective and allied-army elimination loss condition.
- [x] Automated tactical tests and actual driver rendering smoke check.
- [ ] Two-person exploratory playtest of the small scenario.

The implemented experiment meets the local control goal. It is not full gameplay
parity: Green XP/leveling, roster menus, supports and campaign saves are deferred.

## Phase 2: local network vertical slice (implemented and automated)

- [x] Versioned, bounded JSON commands and authoritative state/result contract.
- [x] One LT host and two independent graphical clients over loopback TCP.
- [x] Host-issued bearer credentials bound to exclusive Blue/Green seats.
- [x] Engine-based move/attack/wait/end-phase validation and authoritative RNG/AI.
- [x] Monotonic revisions; duplicate, stale, malformed and wrong-army rejection.
- [x] Full discrete state snapshots with HP, positions, durability and digest checks.
- [x] Pause on disconnect; same-seat live-host rejoin and authoritative resync.
- [x] Real-client automatic recovery from an injected corrupt snapshot.
- [x] Three-process graphical acceptance test compares every observed revision,
  demonstrates movement/combat for both armies and resolves Red AI.
- [ ] Two humans explore the client controls and play the full test map to an outcome.
- [ ] Improve tactical presentation/command UX after that feedback.

This slice uses a separate lightweight client renderer; it does not mirror LT's
full menus/animations. Moves commit immediately; Red resolves atomically between
human phases. Client reconnect needs a manual relaunch; host-restart recovery,
durable saves, internet transport and full tactical/campaign parity remain open.

## Phase 3: internet sessions (not started)

- Document host/join setup and choose a connectivity strategy.
- Review TLS/server identity and credential handling before public connectivity;
  v1 loopback plaintext must not be exposed through forwarding.
- Authenticate reconnects; retain results/snapshots by revision.
- Test latency, dropped/duplicated traffic, disconnects, reconnects and malformed
  commands before making internet-play claims.

## Phase 4: tactical/campaign parity (not started)

- Independent persistent rosters, equipment and inventory management.
- Green experience/leveling, recruitment and ownership changes.
- Healing, supports, trade, paired interactions and permadeath audits.
- Shared campaign saves with an explicit phase/event/RNG schema.

## Phase 5: campaign integration (not started)

- Audit a permitted campaign's team assumptions, objectives and story events.
- Establish asset permissions and replace unauthorized assets before packaging.
- Preserve existing mechanics and single-player compatibility where practical.
