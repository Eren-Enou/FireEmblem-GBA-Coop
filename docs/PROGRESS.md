# Progress - October 27, 2026

## Current milestone: Phase 5A persistent armies and first campaign

### Implemented and verified

- `campaign.py` defines the original **The First Alliance** (13x8) and **Holding
  the Line** (16x9), native unique persistent Aren/Mira and Tovan/Sela characters,
  distinct Blue/Green native parties and story factions, and an explicit owner
  map independent of tactical team. Normal rout/army-elimination events and Red
  Pursue AI resolve both chapters. All earlier scenarios remain unchanged.
- Native registry/cleanup/instance-level loading carries the actual unit, item
  and permanent skill objects forward. No reconstruction from the display JSON,
  second engine singleton, UID reset or replacement character/progression system.
  Tests compare native growth rates/points/caps, level/XP/stats, weapon XP,
  equipment instance/uses, personal fields and skill data across the boundary.
- Chapter 1 victory settles into intermission. Each authenticated commander can
  Ready once, independent of phase, under normal session/revision/digest/peer
  checks. The second vote loads only the next trusted chapter while holding the
  session lock and publishes once after settlement to Blue turn 1. Reconnect
  retains ready votes; duplicate/stale requests do not replay transitions.
- Protocol **v4** adds campaign/chapter/title/completion/readiness, intermission,
  owner/party/faction/class/persistence/skill/equipment metadata and actual map
  dimensions. Old v1/v2/v3 peers reject. The client scales maps and shows chapter
  objective/title and an intermission roster/next-title/Ready panel; roster rows
  select full character details. Host/client diffs now match stable IDs rather
  than assuming unchanged enemy lists.
- Native end-chapter cleanup restores HP, applies configured mana reset and
  component hooks, retires temporary enemies/items/skills and rebuilds local
  board/events/actions/phases. XP, stats, growth state and item uses persist.
  Explicit permadeath and disabled death convoy avoid native Blue-only casual/
  convoy branches. Fallen characters remain owned/registered with items and do
  not redeploy. See [CAMPAIGN.md](CAMPAIGN.md) for exact rules and manual play.
- Unexpected transition failure freezes the session. A missing-level projection
  publishes the last committed board marked fault with legal hints cleared,
  never a partially initialized playable chapter. This is not rollback/recovery.

### Executed verification

- **169 tests passed in 230.143 seconds**: 15 new campaign checks plus all 154
  selected Phase 4B/4A/earlier tests. Full repository suite not run. Covers real
  campaign continuity/victory, readiness/rejections, intermission rejoin,
  disconnect before/during transition, dead characters, separate ownership,
  strict schema, native skills/fields/mana and terminal lifecycle fault handling.
- Seed-0 campaign: Chapter 1 completion revision **18 / turn 4**; second ready
  vote loads Chapter 2 at **revision 20 / Blue turn 1**; final shared victory
  **revision 38 / Chapter 2 turn 4**. Both clients match complete host packets
  after every command. Both armies gain real combat/healing XP and levels.
- Aren carries level 3/16 XP/STR 8/Axe XP 41/axe UID 100 with 38 uses; Tovan
  carries level 2/14 XP/STR 8/Axe XP 33/UID 102 with 43 uses. Both healers carry
  level 2/28 XP and their original Heal items with 27 uses. A controlled real
  Chapter 2 hit deals **11 damage**, demonstrating Chapter 1 Strength growth
  (starting Strength yields 10). Native identities and component data, not the
  public projections, establish persistence.
- Initial campaign-only suite: **13 passed in 66.069 seconds**; two additional
  ownership/schema tests are included in the final 169. Contract/model baseline
  checks also passed (6 in 1.551 seconds). After roster-row selection and token
  centering polish, campaign/healing graphical and targeting checks passed again:
  **3 tests in 18.956 seconds**.
- A final native continuity recheck, strengthened with all-stream RNG equality
  and native party-object identity assertions, passed: **1 in 4.930 seconds**.
- Explicit TCP campaign smoke compared **39 identical snapshots**, revision 38,
  host PID 163432 and clients 89100/89052; ignored evidence at
  `artifacts/network-smoke/run-b453f6c2/`. Final explicit TLS campaign after the
  presentation recheck: host **145112**, clients **116560/41872**, **39 equal
  snapshots through revision 38**, evidence `artifacts/network-smoke/run-e7438a6a/`.
  Digest `ac6f62920943a1523e2d564a942e45ed0adf358420d062e44ccfb85d7b1bbeac`.
- Intermission graphical capture used three independent processes, stopped at
  revision 18 with equal client packets; host 119640, clients 145232/166776,
  evidence `artifacts/campaign-intermission-7ff91960/`. Final presentation capture
  at `artifacts/campaign-intermission-final-31ca1638/` used host 152752 and clients
  163976/6288, again with equal revision-18 packets. The intermission and TLS
  Chapter 2 final renders were inspected for title, roster/uses/XP, continuation,
  scaled geometry, stats/growth and transport display. This is scripted rendering
  evidence, not a human playtest.

### Investigated failures, limitations and next step

- Publication audit passed: **23 staged text files**, **11 Python syntax checks**
  and **95 resolving local links**. No engine source, assets, credentials,
  environments or local outputs are staged; licensing/attribution, dependencies
  and earlier fixtures remain untouched. Corrected Windows default-encoding
  damage in two edited documents before staging; UTF-8 checks now pass. This
  scoped audit does not establish historical asset rights or a full secret/
  security review. Repository root/remotes were verified and origin fetched
  without a remote divergence before implementation.

- The first exploratory tactic blindly prioritized cross-army support, sacrificed
  a critically wounded captain and lost Chapter 2. The acceptance driver now
  prioritizes the most vulnerable reachable ally and avoids unsafe attacks. No
  native combat/healing formula or prior scenario was changed to make it pass.
  An initial test command used a nonexistent test-class name; rerunning the
  actual ContractAndModelTests passed. There are no known failing selected checks.
- Native Blue-only party roster queries are bypassed for explicit campaign
  ownership, not globally rewritten. Casual revival, death-to-convoy transfer,
  arbitrary scripted skills/events and deployment need separate parity work.
- Continuity requires the live host. No disk save, restart recovery, checkpoints,
  migrations, recruitment, trading, promotion, shops or matchmaking are added.
  Separate-PC/WAN and two-human exploratory play remain unverified. Original
  installed UI/audio/icons still require an asset audit before redistribution.
- Recommended **Phase 5B**: strict chapter-boundary checkpoint A, native-state/
  ownership/component validation, atomic current/previous generations, corrupted/
  interrupted-write tests, and startup-only restore in a fresh process with fresh
  invitations. Never treat the public snapshot as a save or load remote pickle.

## Previous milestone: Phase 4B cooperative healing

### Implemented

- Protocol **v3** adds the strict `heal(unit, item, target)` command and required
  per-unit legal healing hints. Matching host/clients are required; v1/v2 reject.
  The host revalidates army/phase, actor action state, owned item instance,
  class/rank/availability/charges, range and eligible live ally before mutation.
- Native LT Heal/Mend spells provide targeting, HP caps, durability, XP, weapon
  XP and action completion. Both same-army directions and both cross-army
  directions work without ownership transfer. No engine files or healing solver
  were added or changed. Non-equippable staves are passed directly to native
  combat rather than equipped. Arbitrary item use is outside this command.
- The pygame client selects inventory rows by click or number, shows mint healing
  and orange attack targets for the selected item, and sends the matching action
  when an eligible ally is clicked. Results show restored HP, charges, XP/levels
  and stats using existing authoritative projections.
- Separate original `healing_demo.py` encounter: two injured frontline fighters,
  two Clerics, two choke points and three normal pursuing Red fighters. Cross-army
  allocation keeps both fronts supported; positions, healing actions and charges
  matter. Standard rout/elimination events remain. Training, progression and
  shipped projects are unchanged. See [HEALING.md](HEALING.md) for launch, fixture
  values and tested tactics.

### Executed verification

- **154 tests passed in 169.261 seconds**: 11 new healing authority/network/UI/
  graphical-process tests plus all 143 selected Phase 4A/earlier regressions.
  Includes normal full-battle victory/defeat, progression, TLS, engine movement,
  save round trip and XP/level timing checks. Full repository suite not run.
- New checks cover Blue/Green same- and cross-army healing, capped HP, Heal/Mend
  uses/XP/ranks, wrong army/phase/item/range/target, exhausted/unavailable/action-
  spent actors, duplicate/stale/forged commands, full host/client packet equality,
  live rejoin without replay and actual subsequent combat.
- Seed-0 full healing battle reached shared **victory at revision 18, turn 3,
  six heals** through normal commands; both clients matched every publication.
  A real Red round with support leaves both captains healthier than without it.
- After refreshing selection per queued UI event, focused UI and graphical
  process checks passed again: **2 tests in 5.010 seconds**. Final explicit TLS
  healing smoke used host **148472** and clients **53208/143124**, compared **13
  identical snapshots through revision 12**, and completed cross-army support in
  both directions, Red AI, level-ups and later combat. Ignored evidence is at
  `artifacts/network-smoke/run-c98a32bc/`; state digest:
  `da3371138a505c247db4f4c441481e315ff32e3aca0a4e564b80b2c4be6c1391`.
- Final TLS Blue render and earlier render at `artifacts/network-smoke/run-ece2cd09/`
  were visually inspected: TLSv1.3, healer level/XP, HP/stats/weapon XP, Heal uses,
  mint ally outlines and both level notices render without column overlap.
  Scripts exercise real model/command/rendering boundaries, not human mouse use.
- Publication audit passed: **19 staged text files**, **8 Python syntax checks**
  and **84 resolving local links**. No matching credential signatures, engine
  changes, assets, environments or local outputs are staged. Original licensing/
  attribution, resources, dependencies and both prior fixtures are unchanged.
  The first link-check attempt treated an inherited root-relative README image
  as a Windows drive path; resolving it from the repository root passed. This
  scoped audit is not a historical asset-rights or full secret/security review.

### Failures resolved and remaining limits

- Initial test assumptions used an occupied movement destination, the wrong
  native Staff D threshold and assumed a particular Red damage target. Tests now
  use legal free tiles, database rank requirements and actual deterministic
  engine outcomes. A naive support tactic starved Green; the separate encounter
  and cross-army support allocation now yield the tested legitimate victory.
  Native healing/combat formulas and canonical fixtures were not altered.
- Separate-PC/WAN and two-human exploration remain unverified. Other staves,
  scripted item prompts, trading, promotions, persistence and matchmaking remain
  unimplemented. The installed engine's sample UI/audio/icons still require an
  asset audit before redistribution. There is no blocker to this local milestone.
- Next recommended gameplay milestone: limited personal consumables, beginning
  with Vulnerary, with item/action previews and equivalent authority/recovery
  tests. See [ROADMAP.md](ROADMAP.md) for the broader campaign gates.

## Previous milestone: Phase 4A cooperative character progression

### Implemented and verified

- Reproduced the original audit **before modification**: equal seed-0 combat
  awarded Blue 10 XP and Green 0, with equal 10 HP damage/counterdamage and one
  axe use. After the engine fix, the same unchanged audit awards **10 XP to both**.
- `SimpleCombat.handle_exp/handle_mana` now use phase-independent human membership
  for attacker/defender rewards and the player mana queue. `unit_funcs` selects
  configured player growth for both armies. `human_control` documents the policy.
  Without the opt-in flag Blue remains the sole player; Red retains enemy policy.
- Kept existing hit/miss/kill/modifier formulas, weapon-XP awards, `exp_funcs`,
  ExpState, thresholds/caps, growth generators, stat actions and events. No new
  XP or leveling solver and no broad replacement of unrelated team checks.
- Real combat verifies fixed/random/dynamic levels, exact/below/above threshold,
  repeated level-ups, class/stat caps, Red-phase defense and counter-kills,
  unchanged unarmed/miss rules, fractional weapon XP and capped skill-driven mana.
  A subsequent real attack deals **11 instead of 10 damage** after Strength grows.
- Protocol **v2** adds mana/max mana and lossless decimal-string weapon XP to
  existing progression/state fields. Old v1 peers reject. All reward/state
  mutation remains on the authoritative host; forged reward fields reject.
  Full socket packet equality, no duplicate rewards on resync, same-army rejoin
  after level-up and normal Red AI are verified.
- Host results identify XP, LEVEL UP and stat gains first. The pygame client
  shows selected-unit stats, mana/weapon XP and bounded persistent growth notices.
  Initial selection and column layout make those values directly inspectable.
- Added a separate original `progression_demo.py` drill: 95 starting captain XP,
  a declared 40-HP human class inheriting Fighter growths, and a distant Red 3.
  Both captains reach level 2/5 XP/max HP 41/STR 8 through actual combat. Original
  training and shipped projects are unchanged. Run instructions and fixture
  choices are in [PROGRESSION.md](PROGRESSION.md).

### Executed tests and render evidence

- Combined suite: **143 passed in 140.583 seconds** = 112 previous selected checks
  (including Phase 3A and TLS), 16 new progression tests and 15 existing classic-XP,
  empty-level reroll and level-up timing tests. Full repository suite not run.
- Post-layout recheck: **2 graphical process tests passed in 8.861 seconds**,
  covering normal training and the progression drill after initial-selection/
  text-column changes. Earlier focused progression run: 14 passed in 43.314
  seconds; its added integration checks were included in the final combined run.
- Final explicit TLS growth smoke: host PID **158968**, clients **149844/167652**,
  **8 identical snapshots, revision 7**, Green turn 2. Both captains levelled,
  remained inspectable after Red AI and had increased HP/Strength. Green PNG
  visually inspected: TLSv1.3, level/XP/stats/mana/weapon XP, action hints and both
  level-up notifications render without column overlap. Reports/PNGs/invitations
  remain ignored at `artifacts/network-smoke/run-536fec41/`.
- Existing Phase 3A complete outcomes still pass: seed-1 victory revision 20/turn
  3 and defeat revision 6/turn 4, with identical states after accepted actions.

- Publication audit passed: **25 text files**, 15 Python syntax checks and 65
  resolving local document links. Only the three documented engine files change;
  normal training, shipped resources, dependencies, original license/credits and
  third-party notices are unchanged. No matching credential signatures, media,
  environments or tracked local outputs are staged. This scoped audit does not
  establish historical asset rights or a full secret/security review.

### Failures investigated and resolved

- First v2 schema check failed before running tests because a new weapon-XP loop
  shadowed the state parameter; renamed its local value. The six contract tests
  then passed; final regressions cover malformed progression projections.
- An early network follow-up assertion found the forward captain killed by Red
  AI. The separate drill now declares its survivable human HP/Red placement;
  canonical training was not changed and all normal victory/defeat tests remain.
- A follow-up attack test assumed every miss consumes a weapon use. This engine
  can preserve uses on a miss. The network check now respects that rule and
  verifies RNG/turn completion; a separate real scripted-hit test proves the
  increased Strength changes actual damage. No combat mechanic was altered to
  satisfy the assertion.

### Limits and next steps

Core live combat progression is complete; broader campaign parity is not.
No persistent rosters/checkpoints, recruitment, promotions, trading/convoy,
complex supports or new animations were implemented. Growth choice parity is
verified for Fixed/Random/Dynamic, not every custom growth mode/skill/event.
Random/dynamic unit-ID-derived rolls remain host-only and may differ between
characters; they need not advance the global growth stream. Custom prompts
still require future explicit network decisions. Asset rights remain unaudited.

Next: two-human inspection of the growth drill and the still-unverified private
two-PC Internet acceptance gate. Then persistence and additional tactical slices
under [CAMPAIGN_AND_PARITY.md](CAMPAIGN_AND_PARITY.md). Host restart still loses
the live battle. No firewall/router/service/account changes occurred.

## Previous milestone: Phase 3A online multiplayer playability

### Implemented

- Preserved verified TLS-before-token authentication and separate army seats.
  Added five-second host challenges, 20-second unanswered-challenge expiry,
  35-second client host-silence detection, and a 120-second pending-result
  deadline. Failed connections pause new gameplay without discarding live state.
  Correct credentials manually rejoin the same army at the latest boundary;
  uncertain commands are never automatically replayed.
- Per-peer readers detect EOF and answer/validate heartbeat traffic independently
  of tactical processing. LT now yields between engine steps on the **same
  event-loop thread**, keeping the session lock held through validation,
  resolution and publication. No engine threads, parallel mutations or new solver.
- Proportionate private-session safeguards: eight admitted application sockets,
  global admission burst 16/replenishment two per second, authenticated frame
  burst 30/replenishment ten per second, four queued requests per peer. Existing
  strict frame/schema/authentication and request-ID bounds remain intact.
- Pygame client now outlines legal attack targets, shows movement/tile/action
  information, distinguishes usable buttons, preserves useful disconnection and
  unknown-outcome messages, and identifies shared outcomes/deaths in host results.
  Windows UI close no longer waits on the network reader's buffered-stream lock.
  Ownership, active phase/turn, peers, HP, durability, pending/rejected state,
  revision and Check remain visible through the existing interface.
- Added `app/tests/test_network_playability.py`; extended only `app/coop/` and
  project records. Upstream engine source, licenses, sample assets, dependencies,
  single-player and hot-seat launchers were not changed by this milestone.

### Executed verification

- New suite: **9 passed in 22.182 seconds**. Covers real client heartbeat responses,
  silent peer expiry and rejoin, silent host detection without EOF, disconnect
  during held real LT resolution, post-TLS admission cap, bounded queue flood,
  sequential frame-rate rejection, malformed pong, controlled shutdown and
  pending-deadline no-replay behavior. Final combined run also asserts that
  deadline-driven UI close returns within one second instead of blocking 35.
- Real untouched seed-1 scenario driven through actual client/model sockets:
  **victory at revision 20, turn 3**; passive defeat at **revision 6, turn 4**.
  Both complete battles compare the entire authoritative packet on both clients
  after every accepted action. Movement, attack, wait, end-phase, repeated Red AI,
  HP, inventory/durability, death and shared terminal freeze use real LT. Commands
  after completion reject without changing state. No test kills units directly
  or modifies combat stats/objectives to manufacture these network outcomes.
- Full selected regression command in [TESTING.md](TESTING.md): **112 passed in
  79.877 seconds** (9 new + 8 TLS + 22 prior network + 73 selected hot-seat/AI/
  movement/canto/save tests). No full repository-suite claim. Final test-harness
  cleanup guard recheck: one test passed in 2.444 seconds.
- Explicit three-process TLS graphical smoke passed separately: host PID 96800,
  client PIDs 153284/151988, 10 equal snapshots through revision 9. Evidence is
  ignored under `artifacts/network-smoke/run-9809505c/`. Green PNG inspected;
  negotiated TLSv1.3, phase/turn/revision/board and connection controls rendered.
  Process automation exercises the command/model and rendering, not mouse input.

- Publication audit passed for 14 Python/Markdown files: six Python syntax
  checks, 51 resolving local document links, clean staged whitespace, no matching
  credential signatures/new media/tracked local outputs, and unchanged engine,
  license/credits/resources/dependencies. The inherited README license link was
  corrected to the existing LICENSE.txt and asset-policy distinction preserved.
  This is a scoped staged audit, not a historical secret or asset-rights audit.

### Failures investigated and resolved

- Initial admission-test teardown waited for listener shutdown before closing
  live real-client connections. On Windows/Python 3.12 that wait did not finish;
  the harness now closes its owned accepted sockets and bounds writer shutdown
  before awaiting listener closure. Interrupted diagnostic runs were not passes.
- A pending-result test exposed an actual 35-second client-close stall on the
  buffered-reader lock. Cleanup now belongs to the reader; UI socket shutdown
  returns promptly. The regression assertion passed in the combined suite.
- Initial naive offensive policies lost the battle, including a seed-0 run with
  missed attacks. The final deterministic seed-1 test uses legal defensive first
  turns and focused attacks. Its complete 20-command winning sequence is in
  [INTERNET_PLAY.md](INTERNET_PLAY.md), with no scenario modifications.

### Remaining risks and next steps

The private-overlay-plus-TLS Windows procedure is in
[INTERNET_PLAY.md](INTERNET_PLAY.md): environment, identity, host, private army
invitations, controls, full battle, loss/rejoin, diagnostics and evidence record.
**Physical two-PC Internet connectivity and two-human exploratory mouse play
remain unverified** and are the next human acceptance gate. No firewall/router
change, account creation, VPN installation or public exposure occurred.

Cooperative yields cannot preempt an individual stuck LT call; only the existing
bounded settle path is supported. Admission runs after TLS, not before the TLS
handshake or kernel backlog. No public-service security/load guarantee. Manual
relaunch is required after connection failure. Host restart loses the battle.
Token revocation/expiry UX, Windows ACL hardening, campaign persistence, Green
progression parity, healing/trading/recruitment/promotions and full presentation
remain deferred. Asset rights must be audited before standalone distribution.

Next: execute and record the private two-PC seed-1 acceptance test. Refine UX and
timeouts from measured feedback; do not replace that evidence with local tests.
Continue future campaign/parity work under its separate documented milestones.

## Previous milestone: Internet path, campaign-save and parity methods

### Implemented and verified

- Optional TLS transport with certificate/name verification before sending army
  credentials, TLS 1.2 minimum, explicit bind/advertise options, and private TLS
  join invitations. Plaintext remains loopback-only, including an actual-peer
  address check on local plaintext clients. Tactical protocol remains v1.
- Short-lived development identity setup using existing OpenSSL CLI; no extra
  Python package installed. Keys/certificates/invitations remain local ignored
  files; the helper refuses overwrites. Windows ACL hardening remains open.
- Real TLS socket tests for valid moves/rejoin, wrong name/untrusted identity
  failing before any hello, remote-plaintext rejection, and non-TLS traffic
  rejection on the TLS listener.
- One actual host plus two independently rendering TLS clients moved, attacked
  and passed turns through Red AI: 10 identical snapshots through revision 9.
  Explicit smoke run recorded host PID 163636 and client PIDs 160196/146648.
- Fixed Windows smoke cleanup to terminate its owned process trees before
  closing logs. The first TLS process test exposed a locked host log after
  stopping only the venv launcher; rerun passed after the fix.
- Standalone TLS suite: **8 passed in 9.150 seconds**. Final combined suite:
  **103 passed in 55.232 seconds** (8 TLS + 22 prior network + 73 selected engine,
  hot-seat, AI, movement, canto and save regressions). Full repository suite was
  not run. No upstream engine, licensing or binary-asset changes were needed.
- Additional policy recheck passed 3 tests in 0.075 seconds after adding explicit
  coverage for a localhost lookup whose actual peer is non-loopback. The TLS
  client render was inspected and showed negotiated TLSv1.3.
- Staged publication audit passed: 18 Python/Markdown files, valid Python syntax,
  43 resolving local document links, no matching credential signatures/new media,
  no tracked local artifacts, unchanged engine and original license files. This
  scoped check does not establish historical asset rights or a full secret audit.

### Concrete Internet path

[INTERNET_PLAY.md](INTERNET_PLAY.md) compares connectivity routes, chooses a
private-overlay-plus-TLS first pilot, gives identity/host/client procedures and
defines evidence required from two Windows PCs on different networks. Direct
public hosting is a later gated option; admission/rate limits, heartbeats and
silent-loss detection, long-resolution responsiveness, credential lifecycle and
load tests are still required. No router/firewall policy was modified, VPN account
created, public listener deployed or two-PC WAN session verified by this work.

### Campaign and tactical methods with evidence

[CAMPAIGN_AND_PARITY.md](CAMPAIGN_AND_PARITY.md) defines stable army ownership,
separate persistent parties, strict chapter-boundary DTO checkpoints followed by
supported mid-map barriers, fresh-process validated reconstruction, all RNG
streams, atomic file generations, corruption recovery, migrations and new session
epochs. It maps XP/growth, equipment/abilities, healing/trading, recruitment,
promotions, persistence, deployment/story/objectives to engine reuse and explicit
network acceptance gates. These are **design methods**, not implemented mechanics.

The reproducible `utilities/audit_campaign_readiness.py` probe verified:

- Identical adjacent combat from fresh seed-0 simulations caused 10 HP damage
  and 10 counterdamage and used one axe charge for both armies. Blue gained
  0 -> 10 XP; Green remained 0 -> 0. This matches the inspected Blue-only XP gate.
- All four human demo units are nonpersistent and use the same sample party.
- The engine save dictionary fails direct JSON encoding on a set. Its top-level
  fields contain no explicit phase and only `current_random_state` for RNG.
- Existing restore paths accept richer component/action state than a bounded
  external checkpoint should allow. Methods specify trusted-prefab reconstruction
  and whitelisted state instead of loading arbitrary engine dictionaries/pickle.

The diagnostic report and TLS smoke outputs are ignored under `artifacts/`.
No campaign save/restore, Green progression fix, healing/trade/promotion command,
multi-chapter game or Internet play capability is claimed as implemented.

### Remaining gates / next action

Next: two-human private two-PC TLS pilot and a bounded liveness/admission slice.
Then deliver XP/growth parity over network combat, introduce persistent original
two-party/two-chapter fixtures and implement chapter-boundary checkpoint A using
the documented schema/restore gates. Inherited asset rights still need an audit
before distribution. External WAN access/player evidence is unavailable in this
automated session; it is a pilot gate, not a passed test.

## Earlier Phase 2 local network multiplayer

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
