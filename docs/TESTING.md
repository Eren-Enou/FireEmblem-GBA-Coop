# Environment and verification

## Phase 5C preparation verification

Run from the actual `FE-GBA-Coop` repository root with the existing Python 3.12
environment. OpenSSL is needed for TLS identity tests; prepend its existing
location only for the test process:

```powershell
$env:PATH = 'C:\Ruby33-x64\msys64\usr\bin;' + $env:PATH
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_inventory_ui app.tests.test_coop_preparation app.tests.test_coop_checkpoint app.tests.test_coop_campaign app.tests.test_coop_healing app.tests.test_coop_progression app.tests.test_network_playability app.tests.test_network_tls app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip app.tests.test_classic_exp app.tests.test_level_up_reroll app.tests.test_level_up_timing -q
.venv\Scripts\python.exe -u utilities/smoke_network.py --preparation
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --preparation
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --preparation --tls --recovery corrupt
```

Executed October 27, 2026: the final combined command above passed **201 tests
in 445.337 seconds** (190 selected prior regressions + 9 preparation/native/
process checks + 2 SDL input checks). The uninterrupted prepared campaign ended
at **revision 58 victory / 59 identical snapshots**. The shutdown/restored
prepared campaign ended at **new revision 29 victory / 30 + 30 identical
snapshots**. Baseline normal/corrupt/truncated/interrupted recovery, Random and
Dynamic native growth restoration, healing/progression/TLS and the listed engine
regressions all passed in that command. Full repository suite not run.

The earlier combined run passed 198/199 and failed the prepared checkpoint
report comparison: Blue could exit after its own save before Green's final save
revision arrived. The harness now waits for the shared final-save revision
before either report; the final 201-test run verifies the corrected boundary.
A final text-only shortening of the clipped unavailable-item label was followed
by **2 SDL input tests passing again in 5.841 seconds**, with visual inspection of
`artifacts/phase5c-ui-review/final-item-panel.png` rendered from the validated TLS
acceptance final packet. All other code remained unchanged after the 201-test run.

Separate verified-TLS/corrupt-current prepared recovery passed:
`artifacts/checkpoint-smoke/run-bf0f6134/`, hosts 169508/128584, clients
170236/136956 then 112936/170064. Histories matched **30 + 30 snapshots**; the
new session ended at **revision 29 victory**, digest
`316abc6e8a1e7577311c57edf718fe517ed99373f4c364473a7f86e8935abab0`.
The restored host verified exact native recapture and reported checksum failure
for current, then recovered generation **2**. Both generations contained the
prepared inventory. Old tokens/session commands rejected before continuation.

A separate two-test SDL input run passed in **5.701 seconds**. It drives actual
number-key selection/U through native self-use and mouse selection of the third
convoy row followed by T through native withdrawal, using the real Model/Session
with a local transport harness. The test prevents invisible battle buttons from
intercepting convoy clicks. A manually reviewed generated intermission render at
`artifacts/phase5c-ui-review/preparation.png` shows selected Hand Axe/native stats,
own convoy/eligibility/effects, UNSAVED notice and save/Ready controls without
text overlap. This is automated input/render inspection, not two-human usability.

The seven focused preparation checks cover native self-use/cap/last-charge removal/
action exhaustion, phase/owner/target/item/charge/full-health rejection, malformed
effect injection, dirty/vote/save-error/retry semantics, actual native inventory
capacity, class/rank, unique-instance conservation, stale/duplicate requests,
mid-map preparation rejection and a real Chapter 2 range-two Hand Axe combat.
Two additional process cases finish both prepared chapters uninterrupted and
through full shutdown/fresh restore, with independent graphical client histories.
The native restored checkpoint recapture includes all supported persistent state;
public comparisons separately check equipment, inventory, uses, convoys and RNG.

Prepared tactics use both personal Vulneraries, then both armies equip Hand Axe,
store Iron Axe/Heal and take Mend. Generation 2 and 3 both contain preparation so
the corrupt-current acceptance recovers the same choices from previous. Two
confirmed saves are an acceptance fixture, not a requirement for ordinary Ready.
Earlier Phase 5A/5B revision-38 and 19+21-snapshot baseline checks remain separate.
No two-human, physical mouse/key usability, WAN/two-PC or full-repository test
result is claimed. Screenshots/logs/credentials/save generations stay ignored
under `artifacts/`. See [PREPARATION.md](PREPARATION.md) for manual controls and
explicit old-manifest incompatibility; never bypass validation to replay old saves.

## Historical Phase 5B checkpoint verification

Use the existing Python 3.12 environment from the actual repository root.
OpenSSL CLI must be on PATH for TLS identities. No new dependencies are required.

```powershell
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_checkpoint -q
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_checkpoint app.tests.test_coop_campaign app.tests.test_coop_healing app.tests.test_coop_progression app.tests.test_network_playability app.tests.test_network_tls app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip app.tests.test_classic_exp app.tests.test_level_up_reroll app.tests.test_level_up_timing -q
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_checkpoint.CheckpointNativeTests.test_random_and_dynamic_native_growth_state_recovers -q
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --tls --recovery corrupt
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --recovery truncated
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --recovery interrupted
```

Executed October 27, 2026: initial **20 checkpoint tests passed in 110.527
seconds**. Final combined **189 passed in 350.772 seconds**, covering all 169
prior selected regressions plus those 20. One added Random/Dynamic growth recovery
test then passed in **16.390 seconds**, including both mode subcases. The current
commands include that addition and will enumerate 21 checkpoint/190 combined
tests; a 190-test combined run is not claimed. Full repository suite not run.
The final bounds audit then added a pre-write generation-overflow guard and
reserved UID allocation headroom. All **21 checkpoint tests passed again in
129.664 seconds** afterward, including the four process recovery cases. The
recorded 189-test combined run predates that small guard; no broader code changed.
Existing OpenSSL directory `C:\Ruby33-x64\msys64\usr\bin` was prepended to this
process's PATH only; no software or system settings changed.

Schema checks cover separate native data, strict fields/types/byte bounds,
duplicates, checksum/generation tampering, truncation, invalid encoding/depth,
unknown versions/components, ownership, classes/native caps, equipment eligibility,
UID/reference uniqueness, skill/party references, mode/RNG and forbidden client
filenames/state. Unsupported native skill data rejects rather than disappearing.

File checks cover verified current/previous generations and first-save mirror,
corrupt/truncated current fallback with diagnostics, both generations invalid,
partial orphan files ignored, injected fsync/rename failures and an actual Windows
file handle denying replacement. Abrupt writer-process exit before current
replacement leaves the previous committed state recoverable. No hardware
power-loss behavior or concurrent-host writing was tested.

Native/fresh-process checks preserve stable unit/item/skill IDs, native growth
rates/points/caps and XP/stats, weapon XP/uses, permadeath, personal fields,
mana/fatigue, real passive-skill effects, party money/BEXP and a used convoy item.
The loader requires exact native recapture equality before listening. Restore
inside a used process rejects; invalid startup emits no invitations/listener.
Mid-map saves reject without state/RNG mutation. Disk errors publish visible
failure, block Ready and recover through explicit retry without repeated rewards.

The four checkpoint process tests each start one host/two graphical clients,
finish Chapter 1, stop all three, restart a new host, reject old tokens and an
old-session request, join two new graphical clients and win Chapter 2. Cases are
normal/corrupt/truncated/interrupted. Full histories match: **19 snapshots before,
21 after**, ending new-session revision 20/turn 4 victory. Existing fresh campaign,
healing, progression, full battles, TLS/security/liveness/sync and selected native
engine regressions still pass.

Final explicit TLS corrupt-generation run after the bounds guard passed with
hosts 130472/94176, clients 147524/74528 then 124992/119496. Evidence remains
ignored at `artifacts/checkpoint-smoke/run-724048c4/`. Saved and final TLS renders were
visually inspected. A separate recovered-intermission render at
`artifacts/checkpoint-recovered-render-169918b5/` compared equal revision-0 packets
and displayed the previous-generation warning, preserved roster and continuation
controls. This is automated rendering, not a human playtest.

Manual save/close/startup-restore/TLS procedures and exact supported limits are
in [CHECKPOINTS.md](CHECKPOINTS.md). Separate-PC/WAN, two-human recovery, mid-map
and final-result saves, broad custom components and migrations remain unverified
or unsupported. Back up both generation files and use the matching native rules.

## Earlier Phase 5A campaign verification

Use the existing Python 3.12 environment from the actual repository root. OpenSSL
CLI must be on PATH for TLS identity tests. No new dependencies are required.

```powershell
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_campaign -q
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_campaign app.tests.test_coop_healing app.tests.test_coop_progression app.tests.test_network_playability app.tests.test_network_tls app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip app.tests.test_classic_exp app.tests.test_level_up_reroll app.tests.test_level_up_timing -q
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_campaign.CampaignProcessTests app.tests.test_coop_healing.HealingUITests app.tests.test_coop_healing.HealingProcessTests -q
.venv\Scripts\python.exe -u utilities/smoke_network.py --tls --campaign
```

Executed October 27, 2026: **169 passed in 230.143 seconds** (15 campaign plus
154 selected prior checks). Initial 13 campaign tests passed in 66.069 seconds;
the final suite includes two added ownership/schema checks. The six existing
contract/model checks passed in 1.551 seconds. After final roster-row selection/
token-centering polish, three focused graphical/targeting checks passed in
**18.956 seconds**. Full repository suite not run. Existing OpenSSL directory
`C:\Ruby33-x64\msys64\usr\bin` was prepended to this process's PATH only.
The native continuity test then passed again in **4.930 seconds**, including
explicit party-object identity and all-stream RNG continuity assertions.

Campaign acceptance uses real native unique units, combat/healing, AI and scoped
objective events. The seed-0 two-client run completes Chapter 1 at revision 18,
turn 4, loads Chapter 2 at revision 20 and wins at revision 38/turn 4. Compare
complete packets after every action, not just digest strings. Both armies gain
XP and real levels; items lose uses. At transition compare native unit identity,
item identity/data/UIDs, levels/XP/stats, growths/points/caps, weapon XP,
equipment, skills, personal fields and death state; never reconstruct from the
public snapshot. A native scripted-hit probe in Chapter 2 confirms retained
Strength produces 11 damage (starting Strength 7 produces 10).

Other checks reject continuation outside intermission, duplicate votes/IDs,
stale bases, forged chapter/team/event fields, invalid owner control even after
a tactical-team change, malformed metadata/equipment and old protocol versions.
Readiness is phase independent but peer gated. Rejoin during intermission
retains the vote/state without replay; disconnect before the second vote pauses
transition; disconnect during locked loading rejoins the one completed result.
Dead Blue/Green characters stay registered with their items and never redeploy.
Mana follows native reset settings, and permanent inert skill data/fields persist.
An injected lifecycle fault publishes a valid terminal last-board packet and
freezes commands. Training, progression, healing, shared battle outcomes, TLS,
liveness, movement, save round trip and XP/timing regressions remain green.

The three-process campaign smoke generates a deterministic command plan in a
closed preliminary harness, then starts a fresh host process and two independent
pygame clients. Only legal public commands drive gameplay. Every published
snapshot must match on both clients, including new terrain/enemies/readiness.
No independent live LT singletons coexist within a process. Both TCP and TLS
runs compared 39 snapshots through revision 38. Reports/PNGs/credentials remain
ignored under `artifacts/`; final TLS evidence is recorded in
[PROGRESS.md](PROGRESS.md). A separate three-process capture stopped at
intermission revision 18 and both client packets matched. Intermission and
Chapter 2 renders were visually inspected; scripts do not constitute mouse or
two-human testing.

Manual local/TLS instructions, fixture values, transition/death rules and tactics
are in [CAMPAIGN.md](CAMPAIGN.md). Complete Chapter 1, inspect each roster row,
press Ready on one client and verify it waits, then Ready on the other and
compare Chapter 2 levels/equipment on both. Rejoin with the same private
invitation around intermission. Separate-PC/WAN, human usability, casual revival,
general custom components and host restart recovery remain unverified/unsupported.

## Earlier Phase 4B healing verification

Use the existing Python 3.12 environment from the actual `FE-GBA-Coop` repository
root. OpenSSL CLI must be on PATH for TLS identities. This adds no dependencies.

```powershell
.venv\Scripts\python.exe -m unittest app.tests.test_coop_healing -q
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_healing app.tests.test_coop_progression app.tests.test_network_playability app.tests.test_network_tls app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip app.tests.test_classic_exp app.tests.test_level_up_reroll app.tests.test_level_up_timing -q
.venv\Scripts\python.exe -m unittest app.tests.test_coop_healing.HealingUITests app.tests.test_coop_healing.HealingProcessTests -q
.venv\Scripts\python.exe -u utilities/smoke_network.py --tls --healing
```

Executed October 27, 2026: combined **154 passed in 169.261 seconds** (11 healing
plus 143 existing selected checks). After a small queued-event selection refresh,
the focused two checks passed in **5.010 seconds**, followed by a successful final
explicit TLS smoke. Existing OpenSSL path used for this process only:
`C:\Ruby33-x64\msys64\usr\bin`; no system settings or software installation.

Authority tests use the real LT harness for all four army pairings, capped HP,
native Heal/Mend charges/XP/weapon XP/level/action completion and ownership
preservation. Rejections cover wrong phase/owner, item instance/type/class/rank,
charges, availability, finished/attacked/unselectable actor, range, dead/full-HP/
enemy/self/absent targets. Snapshot/RNG equality is checked across invalid
actions. Native Mend's D rank is read from the database (31), not invented by
the adapter. Network tests reject duplicates/stale/forged payloads, compare full
host/Blue/Green packets, rejoin and sync without repeated rewards, and fight
after support. A full battle wins legitimately at revision 18/turn 3 with six
heals. A supported-versus-unsupported Red round verifies a real tactical benefit.

The graphical smoke starts three independent processes and supports both cross-
army directions before later combat. Final TLS run: host PID 148472, client PIDs
53208/143124, **13 equal snapshots, revision 12**, Blue turn 3. Reports, PNGs,
certificates and invitations remain ignored under
`artifacts/network-smoke/run-c98a32bc/`. Final Blue render and earlier TLS render
at `run-ece2cd09` were visually inspected for mint targets, Heal uses, level/stats/XP and
TLSv1.3. The scripts drive real command/model/rendering, not physical mouse input.
The selected-item targeting rule also has a focused UI test.

Reproduce manual play with [HEALING.md](HEALING.md). To inspect same-army support,
move into the documented free adjacent tiles; to exercise cross support, select
the healer, choose Heal, click a mint ally and inspect HP/charges/XP/finished
state on both clients. Try an off-phase action and rejoin using the same private
invitation. Separate-PC/WAN, two-human exploration and the full repository suite
were not run. Initial test/fixture failures and their resolutions are recorded
in [PROGRESS.md](PROGRESS.md); there are no known failing selected checks.

## Earlier Phase 4A progression verification

Use the existing Python 3.12 environment. OpenSSL CLI must be on PATH for TLS
identity tests; the game transport and progression add no dependencies.

```powershell
.venv\Scripts\python.exe utilities/audit_campaign_readiness.py
.venv\Scripts\python.exe -m unittest app.tests.test_coop_progression -q
.venv\Scripts\python.exe -m unittest app.tests.test_coop_progression app.tests.test_network_playability app.tests.test_network_tls app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip app.tests.test_classic_exp app.tests.test_level_up_reroll app.tests.test_level_up_timing -q
.venv\Scripts\python.exe utilities/smoke_network.py --tls --progression
```

Executed October 27, 2026: **143 tests passed in 140.583 seconds**. That includes
16 new progression tests, all 112 prior selected regressions and 15 existing
classic-XP/reroll/level-up-timing checks. No full repository-suite claim. The
existing OpenSSL binary directory was prepended to this process's PATH as in
Phase 3A; no software or system settings changed.

The 16 tests cover real hit/miss/kill/counter/unarmed combat, Red-phase rewards,
XP multipliers, fractional weapon XP, skill-driven mana caps, exact/below/above
100-XP thresholds, Fixed/Random/Dynamic selection and actual stat application,
repeated combat level-ups and class/stat caps, single-player/nonhuman fallback,
Red exclusion, and an actual follow-up hit dealing one additional damage.
Controlled solver scripts and fixture initial conditions do not replace XP or
level calculations. Socket checks compare complete host/Blue/Green snapshots,
verify duplicate/resync/rejoin cannot reapply growth, recover after a level-up,
exercise the grown unit on a subsequent turn, reject forged progression fields
through ingress, reject v1 and validate malformed mana/weapon-XP projections.

The new three-process test uses the optional original progression drill. Both
captains start level 1/95 XP with a declared 40-HP human class inheriting Fighter
growths. Real combat reaches level 2/5 XP/max HP 41/STR 8; Red AI still runs.
Training/project data are unchanged. See [PROGRESSION.md](PROGRESSION.md) for
manual inspection, exact fixture differences and expected outcomes.

After a final layout adjustment, both training and progression graphical
process tests passed again: **2 in 8.861 seconds**. Explicit final TLS growth smoke
passed with host 158968 and clients 149844/167652, eight equal snapshots through
revision 7 on Green turn 2. Ignored evidence: `artifacts/network-smoke/run-536fec41/`.
Green render was inspected for selected stats, XP/level notices and TLSv1.3.
Scripts drive the actual command/model/rendering boundary, not physical mouse input.

Initial failures were a v2-validator local-variable shadow, a test fixture whose
captain died before follow-up inspection, and a mistaken test assumption that
misses always consume durability. All were resolved as documented in
[PROGRESS.md](PROGRESS.md), preserving combat rules and normal training. Earlier
focused 14-test progression run passed in 43.314 seconds; later additions are
included in the 143-test combined run. Separate-PC/WAN and two-human exploration,
custom event/promotions, persistence and a full asset audit remain outstanding.

## Earlier Phase 3A playability verification

From the actual repository root, using the documented Python 3.12 environment
and OpenSSL CLI on PATH for TLS test identities:

```powershell
.venv\Scripts\python.exe -m unittest app.tests.test_network_playability -q
.venv\Scripts\python.exe -m unittest app.tests.test_network_playability app.tests.test_network_tls app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip -q
.venv\Scripts\python.exe utilities/smoke_network.py --tls
```

Executed October 27, 2026: new suite **9 passed in 22.182 seconds**; final combined
suite **112 passed in 79.877 seconds**. In this environment the existing OpenSSL
binary directory `C:\Ruby33-x64\msys64\usr\bin` was prepended to this process's
PATH for the TLS checks; nothing was installed and system PATH was not changed.
The final combined run includes the under-one-second UI-close regression.

The new suite uses actual client reader threads, real TCP sockets and one real
LT simulation on the asyncio thread. Seed 1 is explicit. Complete victory uses
20 commands through turn 3; passive defeat uses six through turn 4. Every
accepted action compares the entire host/Blue/Green packet including revision,
digest, RNG, HP, inventories, positions and terminal state. Victory includes
move/attack/wait/end-phase; both outcomes include deaths and terminal rejection.
It does not replace Red AI or alter fixtures/stats/objectives.

Failure tests shorten heartbeat/read timers to fractions of a second. A silent
raw client never answers its challenge; a separate live client detects its loss,
pauses and accepts same-army rejoin. Another test silences host challenges without
sending EOF and checks client read timeout. A held real LT step lets the test
close Green while resolution owns the session lock, observe continued Blue
heartbeats and prompt Green EOF detection, then release resolution and compare
its single committed result after rejoin. No LT operation runs in a worker thread.
Other checks cover eight-socket admission, queue flood, sequential sync-rate
exhaustion, malformed pong, controlled socket closure and unknown-outcome expiry
without replay. Existing tests retain stale/duplicate/delayed/ownership, bad TLS
identity, resync and malformed-frame coverage. These are local controlled tests,
not measured WAN loss or public-service stress/security certification.

The explicit TLS graphical smoke passed with host 96800 and clients
153284/151988, ten equal snapshots through revision 9. Reports/logs/PNGs stay in
ignored `artifacts/network-smoke/run-9809505c/`; Green render was inspected and
showed TLSv1.3. The combined suite also runs the existing TCP and TLS
three-process smoke tests. Full repository suite and editor smoke were not run.

Initial diagnostic runs hung in new test teardown until accepted sockets were
closed before listener wait; these runs were interrupted, not counted as passes.
One test exposed a real Windows 35-second buffered-stream-close stall, fixed by
reader-owned cleanup. Naive offensive battle policies lost; the final untouched
seed-1 winning sequence is reproducible in [INTERNET_PLAY.md](INTERNET_PLAY.md).
That document also contains the exact two-PC Windows setup, secure invitation
transfer, controls, diagnostics, reconnection and human evidence checklist.
**Actual two-PC Internet play and two-human mouse play remain unverified.**

## Earlier TLS Internet-path foundation and campaign-readiness audit

Optional TLS uses standard Python `ssl`; generating identities and running TLS
tests also require OpenSSL CLI on PATH. Existing local TCP tests do not require
that tool. No additional Python dependency was installed. Identity helper accepts
`--openssl PATH` for setup; use the binary's directory on PATH for the test suite.

```powershell
.venv\Scripts\python.exe -m unittest app.tests.test_network_tls -q
.venv\Scripts\python.exe utilities/smoke_network.py --tls
.venv\Scripts\python.exe utilities/audit_campaign_readiness.py
```

TLS tests cover verified sockets, wrong hostname/untrusted identity rejection
before any credential hello, remote plaintext rejection, key-overwrite prevention,
live-host TLS rejoin and the full three-process tactical smoke. Negative identity
tests use disposable generated keys, never committed certificate/key fixtures.
The smoke is still run on localhost; it is not evidence of a two-PC Internet game.

The readiness audit uses two fresh engine simulations with identical combat
class/weapon/enemy/position/seed and writes diagnostics to ignored
`artifacts/campaign-readiness.json`. Observed XP was Blue 0 -> 10 versus Green
0 -> 0, with matching 10 HP damage/counterdamage and 45 -> 44 weapon uses. It also
reports nonpersistent demo rosters, the existing save dictionary's JSON failure,
missing explicit phase and top-level RNG fields. It is not a campaign save.

The Windows smoke helper stops its owned subprocess trees before closing logs;
this fixes a file-lock/venv-redirector cleanup failure found during TLS testing.

Full selected regression command for this milestone:

```powershell
.venv\Scripts\python.exe -m unittest app.tests.test_network_tls app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip -q
```

Standalone TLS run: 8 passed in 9.150 seconds. Final combined run: **103 passed in
55.232 seconds** (8 TLS, 22 existing network and 73 selected engine/hot-seat checks).
TLS smoke compared 10 snapshots through revision 9. Separate-PC
WAN connectivity, public-service load behavior, actual
campaign restore and full parity remain unverified/unimplemented as documented
in [Internet play](INTERNET_PLAY.md) and [campaign methods](CAMPAIGN_AND_PARITY.md).

## Phase 2: local network play

Use the same environment below; the new transport adds only Python standard
library dependencies. Run from this repository root in **three terminals**.

Terminal 1, authoritative host:

```powershell
.venv\Scripts\python.exe run_network.py host
```

The host defaults to deterministic seed 0. Wait for `HOST_READY`. Terminal 2, Blue client:

```powershell
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
```

Terminal 3, Green client:

```powershell
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Each client is a separate process/window with its own input and verified state.
Both must connect before actions are accepted. Click your army's unit to select
it, then a highlighted tile to commit a move or a legal enemy to attack. W waits
with the selected unit; E ends the active army's phase; R requests resync; Escape
or right-click deselects. Number keys choose an inventory weapon (the test map
currently has one axe per unit). Selecting the other army only inspects it.
The header shows army, active phase, turn, revision, digest and connected seats.

Moves commit immediately, with no preview cancellation. A unit gets one move
before attacking/waiting; canto, healing, trade and abilities are not v1 commands.
Green End resolves Red AI on the host and publishes the next Blue boundary.
Terminal victory/defeat freezes the shared board. Ctrl+C stops the host.

Close/reopen a client using the same credential file to rejoin a live host. The
other player pauses until both reconnect. Host restart creates a fresh map and
new credentials; there is no campaign persistence or host-restart recovery.
Credential files are private local bearer capabilities, not public game assets.
They and the process reports/screenshots are ignored under `artifacts/`. This
plain TCP mode rejects non-loopback connections. Optional TLS endpoint setup is
described above; actual Internet play is **not yet verified**.
See [the exact contract](NETWORK_PROTOCOL.md) for trust boundaries and limits.

### Automated network acceptance

```powershell
.venv\Scripts\python.exe -m unittest app.tests.test_network_coop -q
.venv\Scripts\python.exe utilities/smoke_network.py
```

The smoke utility launches the actual host CLI plus the actual pygame client CLI
twice, in three distinct OS processes, using an ephemeral loopback port. The
clients render with SDL's dummy video/audio drivers and execute local scripted
tactical intents through their real command/model interface. Reports are compared
for every revision, complete state, inventory/HP, RNG and digest. Acceptance
requires a move and real LT combat for each human army, changed durability,
host-driven Red AI, and identical final phase/turn. Current deterministic script
ends on Green turn 2 at revision 9 after comparing 10 snapshots.

It writes logs, credential files, scripts, reports and Blue/Green screenshots to
an ignored per-run directory under `artifacts/network-smoke/`, prints its path,
and terminates its own child processes. The unittest version uses a disposable
directory. Scripts exercise tactical commands and rendering, not mouse gestures;
two-human exploratory UI testing remains outstanding.

The network suite also exercises the real LT adapter, raw TCP sockets and real
client connections: ownership/range/path/occupancy/inventory rejection, stale and
duplicate requests, strict JSON/versions/schemas, engine-fault freeze, objectives,
bad authentication/seat theft, malformed/oversized frames, fragmented requests
with 20ms per-fragment delays, pause/rejoin, and automatic recovery after an
injected checksum-corrupt snapshot. Resync/rejection must not execute another
action or change revision/RNG. This is not a WAN/load/packet-loss test or a full
security audit. No internet, separate-PC, campaign-save or full-suite claims.

### Network plus existing tactical regressions

```powershell
.venv\Scripts\python.exe -c "from app.engine.codegen import source_generator; source_generator.generate_all()"
.venv\Scripts\python.exe -m unittest app.tests.test_network_coop app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip -q
```

Latest standalone network run: **22 passed in 23.580 seconds** on October 27,
2026. Final combined run: **95 passed in 52.002 seconds** (22 network plus 73
existing selected regressions). The final independent CLI smoke also passed with
10 identical snapshots ending at revision 9. Detailed evidence is in PROGRESS.md.

## Existing hot-seat environment and tests

Run commands from `FE-GBA-Coop`, not the parent repository. Verified on Windows
with Python 3.12.6, pygame-ce 2.5.7, PyQt5 5.15.10, Qt 5.15.2 and PyQt5_sip
12.20.0. Existing `.venv` is ignored, not part of the deliverable.

## Recreate

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements_editor.txt
.venv\Scripts\python.exe -c "from app.engine.codegen import source_generator; source_generator.generate_all()"
```

The current requirements also install PyInstaller 6.2.0; packaging is not part of
this milestone. The checks below use built-in unittest and do not need pytest or
the optional Pillow tests. Keep the source checkout's sample projects/resources.

## Play the prototype

```powershell
.venv\Scripts\python.exe run_coop.py
```

Blue acts first; use arrow keys and X to select a unit, select its destination,
then choose Attack or Wait. Z cancels, A cycles available units. Select an empty
tile to open the map menu and choose End to hand control to Green, then Red AI.
Bindings follow the existing `saves/config.ini`; these are the engine defaults.
Green units cannot be commanded during Blue's phase and vice versa. Hold S during
Red's phase to speed through AI presentation. Eliminate all Red units to win;
losing either entire human army loses the shared map.

This is one-machine hot-seat play. Save/suspend and turnwheel are omitted from
this demo. Closing and launching again starts a fresh scenario. Do not package
the sample's assets for distribution.

## Automated checks

```powershell
.venv\Scripts\python.exe -m unittest app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip -q
```

The local tests load the supported default project, install the original demo,
and drive the real state machine with SDL button events. The harness fixes the
random seed to 0, uses dummy SDL video/audio, and shortens phase banners. It does
not replace combat/pathfinding/AI with mocks; the ownership test deliberately
mocks a permissive selection skill to exercise the independent ownership guard.

Coverage includes faction rejection, movement/Wait for both armies, blocked or
out-of-range destinations, occupied allied tiles, real HP and durability changes,
AI target choice for either army, AUX cycling, manual/automatic phase handoff,
round accounting, shared victory/defeat, default control fallback, and removal
of unsupported demo saves. Existing movement, AI and save tests check regressions.
Networking/synchronization tests will be added with Phase 2, not simulated here.

## Actual driver/editor smoke checks

```powershell
.venv\Scripts\python.exe run_coop.py --smoke
.venv\Scripts\python.exe utilities\smoke_editor.py
```

The first renders a full Blue -> Green -> Red AI -> Blue round through MainLoop,
with normal banner timing, saves Blue/Green PNGs under `artifacts/`, and asserts
turn 2 was reached. It exits on success with `COOP_SMOKE_OK`. It advances phases
programmatically; tactical command verification comes from the harness tests.

The editor check opens/renders a disposable copy of `default.ltproj` and exits
with `EDITOR_SMOKE_OK`. It leaves the original project unchanged and does not
change the saved current-project/recent-project settings. It needs a Windows
desktop. This is a launch/render check, not exhaustive editor validation.

The older `testing_proj.ltproj` has v0 metadata and a missing `lmaoooo.png`
portrait. Opening it through the editor's migration path fails; existing engine
tests load it as a fixture at the current serialization version. Use the
supported `default.ltproj` for editor use and the co-op launcher. Do not mark the
old fixture migrated or silently replace its missing art.

Test results and remaining limitations are recorded in PROGRESS.md.

## Earlier repository-maintenance verification — October 27, 2026

The repository-maintenance milestone changed documentation and ignore rules only.
Code generation followed by the automated command above passed **73 tests in
28.443 seconds** on the existing Windows/Python 3.12.6 environment. The original
prototype's driver and editor smoke checks passed earlier on the same date;
they were not repeated for this documentation change. Full-suite, networking and
internet behavior remain untested.

Publication validation also passed: 8 staged Markdown/ignore files including
renames, 20 resolving project-document links, a clean staged whitespace check,
no matching credential signatures, no tracked private/local output paths and
unchanged original license/credits. This does not clear inherited assets or
constitute a full historical secret scan.

## Milestone publication procedure

Run from the actual project checkout, which has its own `.git` directory:

```powershell
git rev-parse --show-toplevel
git remote -v
git fetch origin
git status --short
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git ls-files .venv artifacts local_assets private_assets
git check-ignore .venv/probe artifacts/probe.png .env local_assets/probe.png private_assets/probe.png example.gba example.iso example.ciso
```

Expected remotes: GitHub `Eren-Enou/FireEmblem-GBA-Coop` as `origin`, rainlash's
GitLab `lt-maker` as `upstream`. The tracked-local-files command should print
nothing; check-ignore should list every probe path. The probes need not exist.

Review the staged content as well as filenames for credentials and proprietary
content. The earlier maintenance commit contained only Markdown and `.gitignore`.
The Phase 2 milestone permits its Python modules/tests/launchers and documentation;
no license/credits changes, new media, ROMs, credentials or local artifacts.
Check the authored Markdown's local links resolve after moving files to `docs/`.
These checks cover the new staged change, not a full historical licensing or
secret audit. See [asset policy](ASSET_POLICY.md).

After relevant tests and documentation are complete, commit explicit reviewed
paths and push the intended branch to origin. For the current main branch:

```powershell
git push origin HEAD:main
git rev-parse HEAD
git ls-remote origin refs/heads/main
git status --short
```

The two commit hashes must match. Do not force-push or claim success without
remote verification. Record actual failures if publishing is blocked. Subsequent
task branches should use their own explicit destination instead of `main`.
