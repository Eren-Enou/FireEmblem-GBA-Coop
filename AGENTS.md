# Fire Emblem GBA cooperative project

Work only in this Lex Talionis checkout. Do not modify or depend on the separate
Path of Radiance project. The upstream baseline is
`3ba9bd923c82b36c0d57767a75d540f2bcdbc166` from
https://gitlab.com/rainlash/lt-maker.

The goal is two independent online clients, each owning an allied army against
shared enemy AI, followed by cooperative campaign progression. Current completed
scope includes hot-seat play and a loopback network vertical slice: one LT host,
two independent graphical clients, Blue -> Green -> Red AI, versioned commands,
authoritative state and live-host reconnect/resync. Optional verified TLS and
remote endpoint configuration, heartbeat loss detection, bounded private-session
admission/rates, cooperative same-thread engine resolution and complete network
battles are implemented and tested locally. Rejoin is a manual client relaunch;
separate-PC Internet play remains unverified. Phase 4A adds human-army XP/mana
eligibility and player growth selection, real fixed/random/dynamic combat level-ups,
weapon XP/mana projections and a separate progression drill. Phase 4B adds
protocol-v3 Heal/Mend staff commands, allied healing hints/UI and the separate
Mutual Aid scenario. Phase 5A adds native persistent unique characters, distinct
Blue/Green parties and a live two-chapter campaign with dual-ready intermission.
Phase 5B adds validated native chapter-boundary checkpoints, atomic generations
and fresh-process recovery. Phase 5C adds native Vulnerary use and own-party intermission equip/convoy
preparation, dirty/save acknowledgement and supported equipment recovery.
Phase 5D adds native read-only threat/forecast/terrain/path projections and
cancellable movement/attack proposals. Protocol v8 carries shared-turn/outcome metadata, tactical data plus consumables, item explanations, convoys and checkpoint status. Mid-map saves and full tactical parity remain open.

Read [architecture](docs/ARCHITECTURE.md), [progress](docs/PROGRESS.md),
[roadmap](docs/ROADMAP.md), [testing](docs/TESTING.md) and
[asset policy](docs/ASSET_POLICY.md) and [network contract](docs/NETWORK_PROTOCOL.md)
before changing the prototype. These are the
canonical project records; `docs/source/` remains upstream engine documentation.
Read [Internet play](docs/INTERNET_PLAY.md) and
[campaign/parity methods](docs/CAMPAIGN_AND_PARITY.md) for the next stages.

## Phase 6A experimental branch

- `codex/shared-allied-turns` is an opt-in experiment; sequential stays default,
  and stable main must not be replaced or automatically merged. Read
  [shared rounds](docs/SHARED_TURNS.md) before modifying phase scheduling.
- `SharedSimulation` extends the unchanged sequential adapter in `shared_turns.py`.
  Enter Green native phase-change/upkeep only at the opening barrier, before
  either army acts. Execute each owned action with the native current-team pointer
  set to its owner; restore Blue before publication. Never reset flags or run
  upkeep between interleaved commands. Both Ready votes close Blue then Green
  endsteps, followed by native Red AI and next-round Blue/Green opening upkeep.
- Readiness belongs to the living host and survives rejoin. One vote locks only
  that army. No undo-ready or automatic command replay. Preserve Session's lock
  across every native generator yield and publication; no second native thread.
- Shared mode forbids checkpoint directories and restore before engine startup.
  Shared campaign preparation/storage is disabled; both chapters can continue live.
  Do not add the experimental module to the sequential checkpoint manifest or
  weaken validation to load a shared state. Existing sequential native files and
  save schema remain unchanged. Fresh retry uses a new process and credentials.
- Wire v8 adds `turns` and `outcome`. Both clients must update. A pending command
  clears only on its own army's matching result or matching rejection; another
  army's revision or colliding request ID is not an acknowledgement. Stale
  requests resync, clear proposals, and require a new explicit choice.
- Basic UI keeps HP/actions/readiness/danger/forecast visible. I reveals full
  stats/WEXP/calculation notes/digests; terminal overlay explains shared outcome.
  `run_solo.py` creates fresh private run directories and terminates only its own
  children. Never silently reuse old invitations or overwrite prior checkpoints.

## Repository

- The project root is this `FE-GBA-Coop` directory, with its own `.git` directory.
  The enclosing workspace has a separate empty Git repository. Run Git commands
  here; do not add this checkout to the parent as a nested repo or submodule.
- `origin`: `https://github.com/Eren-Enou/FireEmblem-GBA-Coop.git`.
- `upstream`: `https://gitlab.com/rainlash/lt-maker.git`. Keep it for engine updates.
  Verify remotes/root before configuration changes. Never push project work there.
- The local prototype milestone is `36f6552ddbc7004fdbfa7fb5e99df0907983bba3`.
- Preserve upstream history, `LICENSE.txt`, `credits.txt`, `licenses/` and original
  attribution. The engine's MIT code license does not establish asset rights.

## Architecture and conventions

- Keep ordinary single-player behavior when `_human_teams` is absent.
- Separate control ownership from team alliances and story factions.
- Extend the existing state machine, pathfinder, combat solver and AI.
- Edit `app/engine/component_system/skill_system_base.py`, never the generated
  `app/engine/skill_system.py`; regenerate with source_generator.
- Keep the original test scenario in `app/engine/coop_demo.py`. It installs only
  in memory; do not rewrite the shipped `.ltproj` projects.
- Use Python 3.12, four-space indentation, clear names and the surrounding style.
  Prefer small, focused changes with useful type hints.
- Keep co-op behavior in dedicated modules where practical. Limit engine edits
  to explicit integration points and describe them in the architecture document.
- Keep future command/transport code independent of SDL input and presentation.
  Host validation must not rely on the current local UI ownership guard.
- Extend `app/coop/` and `run_network.py` for networking; do not create another
  combat solver or import the test harness into production. `simulation.py`
  adapts LT, `server.py` serializes authority, `protocol.py` validates JSON,
  `client.py` maintains verified state, and `view.py` presents it independently.
- Use `human_control.is_human_team` for XP/mana eligibility and player growth
  selection, independent of the active phase. Preserve Blue-only fallback without
  `_human_teams`; do not broaden unrelated team checks. Keep LT's formulas,
  caps, growth generators and ExpState/actions as the only progression mechanism.
- Keep the controlled `app/coop/progression_demo.py` drill separate from canonical
  training: 95 starting XP and 40 human HP are declared fixture initial conditions,
  not rewards or normal campaign defaults. Keep `healing_demo.py` separate too;
  its injured frontliners, Cleric healers and two chokepoints are original fixture
  conditions. Protocol v8 requires matching clients.
- Healing is a narrow Heal/Mend spell slice: delegate availability/rank/range/
  target restrictions and all effects to LT. Never equip non-equippable staves,
  transfer target ownership, accept client healing amounts, or turn `heal` into
  arbitrary item/event execution. No native engine edits were needed for Phase 4B.
- Keep `campaign.py` as the trusted manifest/bootstrap for live continuity. Reuse
  native unique units, registry, cleanup and instance `game.start_level`; never
  call module-level `game_state.start_level` during transition (it clears the game),
  create a second live Simulation, reset UIDs, or rebuild units from display JSON.
  Explicit ownership must agree with command authority independently of team.
  Separate Blue/Green parties and factions remain distinct. The campaign uses
  permadeath with convoy-on-death disabled; casual revival is not supported.
- Both commanders ready at intermission, under normal revision/session checks.
  Only the trusted next manifest chapter may load, under the existing session lock.
  Native cleanup hooks/HP recovery apply once. Publish after settlement; lifecycle
  failure freezes the session. Use ID-based diffs when the chapter roster changes.
  Read [campaign instructions](docs/CAMPAIGN.md) before extending this lifecycle.
- Keep `preparation.py` narrow: native Vulnerary self-use and the five audited
  items only. Use native item availability/targets/combat/actions, never client
  effect amounts. Own-party convoy actions must pass an explicit party ID;
  `StoreItem` uses the active Blue party and is unsuitable for Green. Validate
  permanent owner/team/party, unique instance references, native capacity/rank
  before mutations. Unexpected hook failures freeze the session.
- Preparation requires storage at Chapter 1 intermission. Any equipment/transfer
  mutation clears both votes, publishes dirty status and blocks Ready until a
  confirmed save. Do not auto-save dirty changes or silently overwrite an
  incompatible old campaign. See [preparation](docs/PREPARATION.md).
- Tactical data belongs in read-only `tactics.py`, attached in
  `Session.state_projection`; `Simulation.snapshot` remains native-only. Tests of
  complete transport state should compare `Session.state_projection`. Do not put
  game mechanics in this presentation layer or mutate equipment/position, create
  skills, run combat/actions/events or consume RNG for a preview. Use native path,
  targeting and combat calculations. Unknown complex effects must show unavailable.
- `tactics.py` is excluded from the native checkpoint manifest because it is
  read-only; Phase 5C saves remain compatible. A future gameplay mutation there
  would violate that boundary and must instead live in the native adapter/schema.
  Shared projections fail closed for fog until a full visibility contract exists.
- Client proposals bind session/revision/digest, require explicit confirmation,
  and clear on state refresh/resync/disconnect. No speculative rollback or replay.
  Show native HIT as a displayed rating, not exact True Hit odds; counts are up
  to native strikes and counters require survival. Threats assume current blockers,
  not a simulated future formation. Read [tactical controls](docs/TACTICS.md).
- Keep `checkpoint.py` as a separate bounded, versioned native-state DTO/storage
  contract; never serialize display JSON or accept pickle/component code. Capture
  only settled Chapter 1 intermission before native cleanup; unsupported state
  must reject explicitly. Restore only in a fresh constructor/process before
  listening, with trusted prefabs, verified references, rebuilt registries/derived
  state and exact native recapture equality. Never load into an existing host.
- Keep checksums over generation and payload, fsynced temporary files, atomic
  replacement and previous-good fallback. Do not rotate corrupt bytes over the
  good fallback. On save errors publish clear status and block Ready until retry
  succeeds; S requests a host-configured checkpoint, never a client filename.
  Use a new session/credentials after startup recovery. Keep save files ignored
  under `artifacts/`; read [checkpoint rules](docs/CHECKPOINTS.md) before changes.
  Native rules compatibility is conservative and normalized; no load bypass or
  speculative migrations. No mid-map support until its separate gates pass.
- Hold the session lock across cooperative engine-step yields and publication.
  Heartbeat/read tasks may run between steps but must never access engine state.
  Do not put LT simulation in independent threads or automatically replay a
  command whose outcome is unknown. Keep transport queues and deadlines bounded.
- Plaintext networking remains loopback-only. Remote endpoint configuration
  requires TLS with certificate/name verification before army authentication;
  never add an insecure fallback. Do not expose a public service before its
  admission/liveness/security gates pass or load remote data through pickle. Credential files and
  process reports belong under ignored `artifacts/`. A state projection is not
  a campaign save; follow the versioned contract when extending it.
- Identity generation and TLS tests require OpenSSL CLI on PATH (setup/test only).
  Keep generated certificates/keys and army invitations out of Git. Do not install
  VPN software or alter OS/router policy as an incidental test action.
- Do not treat the current generic demo roster as persistent campaign data or
  broaden all Blue-only checks indiscriminately. Follow the audited ownership,
  human-participant, ally and persistent-roster distinctions in the methods.
- Add engine-harness tests for ownership and tactical behavior. Follow docs/TESTING.md
  for the targeted checks. Record actual outcomes and unresolved failures.
- Preserve the passed local acceptance checks; never describe local ownership
  checks alone as network security or synchronization.
- Do not redistribute the sample's proprietary graphics, sounds or story. The
  new terrain/token drawing code is original, but the runtime still uses the
  installed sample's UI, audio and item icons. A standalone release needs an
  asset audit and authorized replacements.
- Add synchronization/reconnection tests when those systems exist. Never describe
  hot-seat behavior as client synchronization or authentication.
- Maintain this file and the roadmap/progress/testing documents as scope changes.

## Required milestone workflow

The user authorizes committing and pushing completed, tested milestones to
GitHub. After each meaningful development milestone:

1. Verify root, branch, working tree and remotes. Fetch origin and account for
   remote changes without overwriting others' work. Preserve unrelated user
   changes. Use `codex/` for new task branches when appropriate.
2. Implement and run relevant checks from `docs/TESTING.md`. Resolve failures or
   clearly record an incomplete milestone; never claim checks that were not run.
3. Update `docs/PROGRESS.md` with behavior, successful checks, current blockers
   and next steps. Update `docs/ROADMAP.md` and `docs/TESTING.md` to match. Update
   architecture and these instructions when their content changes.
4. Review the exact staged diff and asset/credential exposure. Stage explicit
   paths. Never commit virtual environments, secrets, credentials, ROMs,
   proprietary assets, generated screenshots, saves, caches or build outputs.
   Ignore rules do not untrack existing files or erase history. New assets need
   documented redistribution rights.
5. Create a focused milestone commit and push the intended branch explicitly to
   **origin**. Do not force-push, rewrite shared/upstream history or automatically
   merge another branch. No releases/bundles until the asset audit permits them.
6. Verify the remote branch points at the committed revision; report its link,
   tests and limitations. If push fails, record the actual failure and report
   that the commit remains local. Never claim an unsuccessful push succeeded.
