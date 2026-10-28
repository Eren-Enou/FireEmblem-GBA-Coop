# Tactical contract - version 6 with items and preparation

This is a **live tactical/campaign projection**. Checkpoint files use a separate
native-state format; actual WAN play remains unverified. It supports loopback plaintext or optional verified TLS with
explicit remote endpoint configuration. The executable validators live in
[`app/coop/protocol.py`](../app/coop/protocol.py). Unknown versions, fields and
actions are rejected. No network payload is passed to pickle, eval, event script
execution, engine save restoration or Python object construction.

## Version 6 additions

All packets use `v: 6`; exact field validation rejects older clients. Existing
session/id/revision/phase/digest gates cover every new command. `use` has exact
`unit,item,target` fields and permits only a trusted native Vulnerary self target.
`equip`, `deposit`, `withdraw` each have exact `unit,item` fields; no owner, party,
filename or effect data is accepted. They work only at Chapter 1 intermission
with configured storage. Permanent ownership and explicit native party selection
remain host responsibilities.

Each inventory item now includes bounded `effect` text. Each unit includes
`consumables`, with the same `{item,target}` shape as attack/heal hints. Campaign
metadata includes `convoys`, exactly `player` and `other` bounded item lists;
UIDs must be unique across all inventories and convoys. Checkpoint status also
accepts `dirty`. Preparation clears readiness and marks dirty; only a subsequent
saved/restored state permits Ready. Projection and commands remain JSON only.
See [PREPARATION.md](PREPARATION.md). Earlier version-specific sections below
record how the contract evolved; executable v6 validators are authoritative.

## Authority and process boundaries

One host process owns the LT simulation: units, movement/pathfinding, combat,
inventory durability, RNG streams, objectives, phases and Red AI. Two independent
pygame clients keep validated JSON state and draw a tactical map with their own
input handling. They never simulate combat, AI or random outcomes and never
receive video frames or remote keyboard events. Presentation and network code
are separate from the LT adapter in `app/coop/simulation.py`.

The host installs a trusted demonstration or two-chapter campaign in memory,
using the same engine systems and human-team policy as the hot-seat prototype. Phase 4A engine
edits are limited to human XP/mana eligibility and player growth selection as
documented in [PROGRESSION.md](PROGRESSION.md). Host-only presentation runs
offscreen while resolving states. Phase/preload saves are disabled, and normal
title/chapter transition UI is not entered.
Shared victory/defeat event conditions remain the same; their terminal scripts
set result flags and retain the final board instead of opening local title or
game-over screens. Terminal outcomes reject further tactical commands; campaign Chapter 1 instead
enters the explicit dual-ready intermission before the next chapter.

## Framing and player assignment

- Plain TCP is loopback-only. Optional TLS allows explicit remote endpoint/bind
  configuration; default remains `127.0.0.1:38670`. Port 0 selects an ephemeral port.
- Every message is one UTF-8 JSON object followed by LF. Maximum frame size is
  262,144 bytes including LF. Duplicate JSON keys, floating-point numbers,
  non-finite numbers, excessive nesting and malformed/truncated frames reject.
- The host generates independent 256-bit random bearer credentials for Blue
  (`player`) and Green (`other`). `hello` contains only `v`, `type`, and `token`.
  Army identity comes from the host's credential lookup, never a claimed player
  or team field in a command. A seat allows one live connection.
- Host-generated credentials go in ignored `artifacts/network/blue.json` and
  `green.json`. TLS invitations additionally include public `ca_pem` and expected
  `server_name` under a `tls` object. They contain no host private key. TLS
  certificate/name validation finishes before the client sends its token.
  Credentials are not in snapshots, reports or console output. Protect
  these files with local account permissions; Windows ACL hardening is not part
  of this slice. Whoever has a credential has that army's capability.
- Handshake timeout is 5 seconds; bounded outgoing writes also time out after
  5 seconds. Invalid framing/handshakes close that connection. Semantic command
  rejections leave a valid connection open.
- Plaintext has no server identity verification and cannot use remote endpoints.
  Optional TLS uses required certificate validation, expected-name checking and
  TLS 1.2 or newer. Private invitation delivery is a trust boundary. Public-service
  hardening and actual WAN verification remain open; see [Internet play](INTERNET_PLAY.md).

All messages have integer `v: 6` and a string `type`. Initial responses:

| Message | Other fields | Meaning |
| --- | --- | --- |
| `welcome` | `team`, `snapshot` | Host-assigned army and current complete state packet |
| `peers` | `teams` | Connected army IDs; separate from revisioned simulation state |
| `error` | `code` | Fatal connection/protocol failure |

Clients cannot act until both seats are connected. Join/leave status changes do
not change the simulation revision or digest.

## Tactical commands

A `command` requires these exact common fields:

| Field | Type / constraint |
| --- | --- |
| `v`, `type` | Integer 6, string `command` |
| `session` | Current host-generated session ID from the state packet |
| `id` | 1–64 ASCII letters, digits, `_` or `-`; unique per army for this host session |
| `revision` | Nonnegative integer copied from the current authoritative packet |
| `phase` | Phase ID copied from that packet |
| `digest` | The packet's 64-character lowercase SHA-256 state digest |
| `action` | One of the actions below |

| Action | Additional exact fields | Host validation and behavior |
| --- | --- | --- |
| `move` | `unit`: ID, `pos`: integer `[x,y]` | Active army owns a living, selectable, unfinished unit; has not moved; destination is reachable using current LT movement/terrain budget, unoccupied and in bounds; path cost rechecked. Runs LT Move/movement states. |
| `attack` | `unit`: ID, `item`: inventory UID, `target`: unit ID | Active army owns the available unit; weapon is actually in its inventory, equippable, available and usable; LT target/range/line-of-sight rules allow the enemy. Runs LT SimpleCombat through the existing combat state, including counters, RNG, HP, durability, death and events. |
| `heal` | `unit`: ID, `item`: owned UID, `target`: unit ID | Active army owns a living, selectable, unfinished actor that has not attacked; owned Heal/Mend spell passes LT availability/class/rank/charges, single-target restrictions and actual target-system range/eligibility. Target must be a live ally. Runs native spell combat without equipping a staff, including HP caps, durability, XP and action consumption. |
| `use` | `unit`, `item`, `target` | Active owner uses an available native Vulnerary on self, with normal availability, target/HP and action restrictions; native combat resolves effects and consumption. |
| `equip` | `unit`, `item` | Intermission only with checkpoint storage; permanent owner/team/party, owned unique supported weapon and native equip eligibility. |
| `deposit` | `unit`, `item` | Intermission only; own supported instance transfers to explicit own-party convoy (maximum 20); no copy or discard. |
| `withdraw` | `unit`, `item` | Intermission only; unique own-convoy instance transfers to own living character subject to native inventory capacity and class/rank availability. |
| `wait` | `unit`: ID | Active army owns the available unit. Runs normal actively-chosen LT wait and its events. |
| `save_checkpoint` | None | At a settled configured campaign intermission only; host captures native state and chooses the path. No filename/state/component/event fields. Both peers and normal base checks required; accepted save/retry publishes saved or error status. |
| `ready` | None | Only at campaign intermission, once per authenticated commander independent of active phase. Requires both peers and current base; the second vote atomically loads the next trusted chapter. No client-selected level, army or event fields. |
| `end_phase` | None | Requester owns the current phase. Runs existing endstep/turn-change/upkeep states. Blue passes to Green; Green passes through authoritative Red AI to the next Blue turn. |

The host independently computes legality; client movement/attack/heal hints are not
trusted. Payloads cannot supply damage, HP, a path, random rolls, ownership or an
event script. Movement is committed immediately, once per unit phase; v6 has no
move-preview cancellation, canto commands, abilities, cross-army trading or arbitrary items.

Before applying a command the host also checks both seats, session, request ID,
revision, digest and expected phase. Duplicate IDs, including rejected attempts,
are retained for the live session. There is no retry that applies twice: a
duplicate rejects rather than rerunning the action. The per-army request budget
is 10,000 to bound this memory; restart the demo for a new session afterward.

`reject` contains `v`, `type`, `id`, `code`, `revision`. Representative codes are
`not_owner`, `wrong_phase`, `illegal_move`, `illegal_attack`, `illegal_heal`, `unit_unavailable`,
`duplicate_command`, `stale_revision`, `state_mismatch`, `stale_phase`,
`peer_disconnected`, `wrong_session` and `session_finished`. Expected rejections
do not change simulation, revision or RNG. Clients do not automatically replay a
rejected tactical action. They request synchronization when their base is stale.

## Results and state

Every accepted command resolves to a quiescent human command boundary (or a
terminal outcome) on the host before another command is processed. An asyncio
session lock covers validation, resolution and ordered publication. Resolution
yields to network tasks between LT steps on the same event-loop thread. The
session lock remains held across those yields. No other command, snapshot
construction or engine operation can interleave with resolution. A single LT
step (including up to 200 immediate repeats) and snapshot construction remain
synchronous; a stuck Python extension or engine call cannot be preempted.

Both clients receive the exact same `state` packet:

| Field | Contents |
| --- | --- |
| `v`, `type` | Integer 6, string `state` |
| `session`, `revision` | Session ID and monotonically increasing accepted-command revision |
| `digest` | SHA-256 of canonical `state` JSON only: sorted dictionary keys, compact separators, UTF-8, no non-finite values |
| `state` | Schema-validated tactical/campaign projection described below |
| `result` | Null initially; otherwise command `id`, host-bound `team`, `action`, and a bounded authoritative outcome `summary` |

The projection contains a versioned `scenario` ID, a ruleset fingerprint,
map width/height/terrain, objective text, phase, turn, status, combat/growth/other
RNG state plus seed, and a stable ID-sorted unit list. Each unit includes ID/name,
team, position or null, current/max HP, dead/finished/moved/attacked flags,
movement remaining, level/XP, stats, weapon XP, mana/max mana, owner, party, story faction, class,
persistence flag, skill IDs, equipped weapon UID, inventory UIDs/names/durability, and advisory
legal move/attack/heal choices. The fingerprint hashes authoritative engine/co-op
Python files and the installed default project's JSON database. Clients need no
matching local engine/assets because they only present state; both must see the
same session and fingerprint. Digests check this **projection**, not every LT
internal registry, skill, party, event stack or campaign-save field.

The progression fields introduced in v2 and retained in v6 are `mana` and `max_mana` (integers 0-10000,
current <= maximum), plus `wexp` (at most 64 weapon IDs mapped to nonnegative,
finite decimal strings <= 10000, at most 64 characters each). For example,
`"Axe":"32.5"` preserves fractional engine modifiers without admitting JSON float
payloads. These are read-only projections. Clients cannot submit XP, levels,
stats, mana or weapon-XP changes; unknown command fields reject. v1 handshakes and
packets reject rather than silently losing progression data. Use matching v6
host/clients. Version 3 adds a required `heals` choice list with the same strict
`{item,target}` schema and inventory/target-ID checks as `attacks`. The new `heal`
command has the exact same IDs/base fields as attack; it accepts no amount, HP,
XP, team or other effect data. Only Heal/Mend single-target spells are supported.
There is no generic Use, potion, revive, AoE, sequence, enemy-healing or ownership
transfer capability. Moving before healing is allowed; healing consumes the
normal action and blocks another move/attack/heal. Rejections preserve state/RNG.
Host/clients must all use v6; v1/v2/v3/v4/v5 handshakes and snapshots reject. Scenario IDs include `coop_training/v1` or `coop_progression/v1` and `coop_healing/v1`, plus `coop_campaign/v1`;
scenario version and wire version are separate.

Authoritative result summaries place XP changes, level-ups and stat gains before
ordinary combat details; healing results first identify actor, target and HP
recovery. The client computes presentation-only differences for
a bounded growth history. Resync/rejoin only restores state, never runs rewards.
Random/dynamic level-up rolls derive from stable unit ID, internal level and host
seed; unchanged global growth-stream state does not mean a level-up was skipped.

Snapshots go out only at discrete command boundaries and on explicit resync or
join. There is no frame-by-frame screen/state replication. Green's End
includes all Red AI actions in one revision; clients see the resulting board and
authoritative outcome summary, not Red's intermediate animations.

If engine resolution unexpectedly faults after mutation may have begun, the
host publishes a new revision with terminal `fault` status and freezes commands.
It does not report an unchanged-state rejection or attempt unsafe rollback.
Restart and inspect the host log; persistent crash recovery is future work.

## Version 4 campaign state and continuation

Every state requires `campaign`: null for demonstrations, otherwise an exact
object with `id`, `chapter`, `title`, nullable `next_title`, unique `completed`
chapter IDs (at most 16), and unique `ready` army slots (at most Blue/Green).
`status` adds `intermission` alongside playing/victory/defeat/fault. `width` and
`height` remain bounded 1-64 and now come from the actual trusted level; terrain,
positions and legal destinations are validated against those dimensions.

Every unit additionally requires nullable `owner` (army slot), nullable native
`party`/story `faction`, `class`, boolean `persistent`, a bounded `skills` list
of IDs (at most 100) and nullable `equipped` weapon UID referencing its inventory.
These are read-only display fields; native growth/component state remains on the
host. They do not constitute a save schema. Dead and undeployed are distinct:
`dead` describes actual engine death, while `pos: null` may mean undeployed.

A `ready` command has only common base fields and action, no additional payload.
The host accepts either army during intermission, rejects repeated votes as
`already_ready`, and rejects continuation elsewhere as `not_intermission`.
The first vote publishes readiness; the second performs native cleanup and
loads the next allowlisted chapter within the same session lock. Both requests
obey duplicate/stale/digest/session/peer checks. Simultaneous stale votes require
resync and explicit retry; uncertain outcomes are never automatically replayed.
Readiness survives live-host reconnect. Reconnect during resolution receives the
committed result, never an intermediate level. Chapter completion is recorded
once, new enemies receive fresh IDs/instances, and diffs match units by stable ID.

Unexpected transition faults freeze the session. If lifecycle failure prevents
an active-level projection, the host publishes the last committed board marked
`fault` with no legal hints. It does not continue partially loaded gameplay or
claim rollback. Version 5 adds fresh-process chapter-boundary recovery; mid-map
recovery remains unsupported. See
[CAMPAIGN.md](CAMPAIGN.md) for ownership, cleanup/death policy and manual play.

## Version 5 checkpoint status (separate from save data)

The required campaign object adds `checkpoint`, an exact object containing
`status` (`disabled`, `pending`, `saved`, `error` or `restored`; v6 adds `dirty`), nonnegative
integer `generation` and bounded `message` (1-256 characters). No native
checkpoint payload, path, credential or key is transmitted in this field.
Non-campaign state still uses `campaign: null`. Older v1-v4 clients must update.

A configured host automatically saves on settled Chapter 1 completion under the
session lock, before publishing intermission. S sends the exact no-argument
`save_checkpoint` command to retry/create another generation at this boundary.
It does not run end-chapter cleanup or rewards. Errors publish clear checkpoint
status; Ready rejects with `checkpoint_required` until saved/restored. Disabled
storage remains available to in-memory harnesses. CLI campaign hosts enable
storage by default. Mid-map save attempts reject `not_intermission`; unconfigured
storage rejects `checkpoint_disabled`. Duplicate/stale/authentication checks
apply just as to all other commands. No network Load operation exists.

The checkpoint file is a separately validated native-state DTO, never this public
projection. `--restore` is startup-only before listening in a fresh host process.
A restored campaign has a new session ID/revision epoch and fresh bearer tokens,
cleared ready votes and the preserved native boundary. Both commanders Ready to
continue. Old tokens and old-session commands reject. Fallback diagnostics
identify rejected generations, and restored status identifies recovery. Disk
schema, compatibility, native-object verification and exact scope are described
in [CHECKPOINTS.md](CHECKPOINTS.md).

## Desynchronization, disconnect and recovery

- Clients validate full state shape and digest before replacing their displayed
  model. Older snapshots are ignored; conflicting same-revision snapshots or
  changed session/ruleset are rejected. A checksum failure pauses commands and
  requests a fresh packet. Malformed schema fails closed.
- A `sync` request contains only `v` and `type`. The host returns its latest state
  packet without incrementing revision or invoking the engine. Stale/digest
  rejections also trigger client resync; R provides manual resync.
- On disconnect, the host pauses new tactical commands while preserving its live
  state. Any command already accepted resolves atomically before that disconnect
  is processed. No speculative cancellation or rollback occurs.
- Reopen a client with the same credential file after its old connection closes.
  It reclaims the same army and receives the current snapshot. No automatic
  reconnect loop, durable reconnect token store, event-log replay or host-restart
  recovery through this wire protocol exists. Host restart generates new credentials;
startup checkpoint restoration is separately supported as described above.

## Liveness and bounded private-session service (Phase 3A)

Use the same current client/host commit. Current v6 includes campaign/roster metadata, weapon XP/mana and healing choices;
clients must understand both those fields and the existing ping/pong controls. Older
clients must update rather than silently disabling liveness checks.

- After welcome, the host sends `{v:5,type:"ping",nonce:N}` every five seconds
  when no challenge is outstanding. The client reader answers
  `{v:5,type:"pong",nonce:N}` immediately, independently of pygame polling.
  Host nonces start at one and increase per connection. Only the outstanding
  nonce is accepted. Unknown fields, booleans and unsolicited/replayed pong close
  the connection. Ordinary messages cannot substitute for the challenge response.
- An unanswered challenge expires after 20 seconds, checked on the five-second
  timer (about 25 seconds after the last acknowledged challenge). Host closes
  that socket, excludes it from command readiness, then publishes connected-seat
  status at the next command boundary. The live session and RNG are preserved.
- The client socket read deadline is 35 seconds without a host frame. A pending
  tactical command has a 120-second result deadline checked by UI polling. On
  expiry it disconnects with an **unknown outcome** warning; it never retries the
  command. Rejoin with the same invitation to learn the committed host state.
- A dedicated reader per peer processes heartbeats and EOF while the command
  processor awaits the simulation lock. There are at most four queued requests
  per peer. EOF/heartbeat failure closes the writer immediately, even during
  resolution; an already accepted command still finishes and publishes once.
  Subsequent commands require both non-closing seats. Rejoin and sync take the
  same lock and can only receive a completed authoritative boundary.
- At most eight accepted TCP/post-TLS application connections may be admitted,
  including two seats and pending hellos. Global admission uses a burst of 16
  with two new attempts/second replenishment. Hello has a five-second deadline.
  An authenticated peer has a burst of 30 frames with 10/second replenishment,
  including pong and sync. Queue/rate/admission violations close that connection
  without mutating the simulation. Existing five-second write/TLS timeouts and
  10,000 request IDs/army bounds remain.
- These are trusted-session safeguards. The application admission cap runs
  **after TLS negotiation**; it does not bound kernel backlogs or simultaneous
  TLS handshakes. There is no public-service DoS guarantee, token revocation,
  account system or durable recovery.
- The client reader owns buffered-stream cleanup. UI close shuts down the socket
  without waiting for its stream read lock, avoiding a Windows 35-second stall.
  Connection failure clears command readiness and leaves the last board visible.

This contract supports three demonstrations and one trusted live two-chapter
campaign. Mid-map checkpoints, deployment, recruitment, promotions, allied trades/
advanced healing, broader tactical parity and verified Internet play remain
later milestones. Core Green combat
XP/level/growth parity is implemented as described in [PROGRESSION.md](PROGRESSION.md). Version the contract explicitly
when expanding these fields/actions; do not treat this projection as a safe
replacement for complete engine save/load.
