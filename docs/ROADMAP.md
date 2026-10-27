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
parity: roster menus, supports and campaign saves remain deferred; Phase 4A
subsequently implements core Green combat XP/level/growth parity.

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
- [x] Basic action highlighting, movement counts, connection/error and terminal status.
- [ ] Refine tactical UX after two-human feedback.

This slice uses a separate lightweight client renderer; it does not mirror LT's
full menus/animations. Moves commit immediately; Red resolves atomically between
human phases. Client reconnect needs a manual relaunch; host-restart recovery,
durable saves, verified WAN play and full tactical/campaign parity remain open.

## Phase 3: Internet path (TLS foundation implemented; WAN pilot unverified)

- [x] Verified TLS host/client contexts and expected-server-name checking before tokens.
- [x] Opt-in endpoint/bind/advertise configuration; reject remote plaintext.
- [x] Short-lived identity generation, private per-army TLS invitations and setup docs.
- [x] Real TLS sockets: movement/rejoin and identity-failure checks before authentication.
- [x] Three graphical processes over TLS; identical state through revision 9.
- [x] Connectivity comparison, recommended private-overlay pilot and measurable gates
  in [INTERNET_PLAY.md](INTERNET_PLAY.md).
- [ ] Two Windows PCs on different networks complete the private pilot.
- [x] Phase 3A: heartbeat/host-silence/result deadlines, bounded admission/queues
  and frame rates, same-thread network yields during locked engine resolution.
- [x] Phase 3A: complete socket-driven battles to victory and defeat; identical
  snapshots/revisions after every accepted action; death and terminal freeze.
- [x] Phase 3A: silent loss, idle/resolution disconnect, rejoin, malformed pong,
  sequential rate and queue floods, controlled shutdown and UI-close regression.
- [x] Phase 3A: movement/attack/readiness hints and Windows private two-PC procedure.
- [ ] Invitation expiry/revocation and Windows private-file ACL UX.
- [ ] Bound individual engine calls/TLS pre-handshake resource use before public hosting.
- [ ] Representative WAN latency/jitter, half-open connections and reconnect storms.
- [ ] Public-host/relay connectivity design and operational/security review before exposure.

## Phase 4A: core progression (implemented and locally verified)

- [x] Human-army attacker/defender XP eligibility, including Red-phase counters.
- [x] Configured player fixed/random/dynamic growth methods and real LT level-ups.
- [x] Existing miss/kill/modifier/threshold/stat-cap/level-cap rules and weapon XP.
- [x] Mana queue parity with existing skill/resource caps where applicable.
- [x] Host-only progression, full client convergence, duplicate/resync/rejoin checks.
- [x] Protocol v2 fractional weapon XP/mana and visible stats/XP/level-up panel.
- [x] Separate reproducible progression drill, three-process rendering and TLS smoke.
- [ ] Two-human exploratory progression playtest; actual two-PC WAN remains unverified.

## Remaining Phase 4 tactical/campaign parity (not implemented)

Implementation methods are now documented in
[CAMPAIGN_AND_PARITY.md](CAMPAIGN_AND_PARITY.md), backed by a reproducible readiness
audit. These design tasks are complete; the mechanics/checkpoint gates below are not.

- Independent persistent rosters, equipment and inventory management.
- Recruitment, promotions and persistent ownership changes; core Green combat XP/growth is complete.
- Healing, supports, trade, paired interactions and permadeath audits.
- Shared campaign saves with an explicit phase/event/RNG schema.
- Chapter-boundary DTO first, then supported mid-map quiescent checkpoints;
  validated restore, atomic generation commit, corruption recovery and migrations.
- Explicit host-owned army identities/two persistent parties, followed by
  network Equip/Use/Heal/Trade/Recruit/Promote/deployment slices. Core combat
  XP/growth parity is implemented by Phase 4A.

## Phase 5: campaign integration (not started)

- Audit a permitted campaign's team assumptions, objectives and story events.
- Establish asset permissions and replace unauthorized assets before packaging.
- Preserve existing mechanics and single-player compatibility where practical.
