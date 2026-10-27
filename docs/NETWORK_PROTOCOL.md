# Phase 2 tactical contract — version 1

This is a **live training-map session**, not a campaign-save format or a verified
Internet service. It supports loopback plaintext or optional verified TLS with
explicit remote endpoint configuration. The executable validators live in
[`app/coop/protocol.py`](../app/coop/protocol.py). Unknown versions, fields and
actions are rejected. No network payload is passed to pickle, eval, event script
execution, engine save restoration or Python object construction.

## Authority and process boundaries

One host process owns the LT simulation: units, movement/pathfinding, combat,
inventory durability, RNG streams, objectives, phases and Red AI. Two independent
pygame clients keep validated JSON state and draw a tactical map with their own
input handling. They never simulate combat, AI or random outcomes and never
receive video frames or remote keyboard events. Presentation and network code
are separate from the LT adapter in `app/coop/simulation.py`.

The host installs the existing original training map in memory, using the same
engine systems and ownership policy as the hot-seat prototype. There are no new
edits to upstream engine modules in this milestone. Host-only presentation runs
offscreen while resolving states. Phase/preload saves are disabled, and normal
title/chapter transitions are not entered.
Shared victory/defeat event conditions remain the same; their terminal scripts
set result flags and retain the final board instead of opening local title or
game-over screens. All further tactical commands then reject as session finished.

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

All messages have integer `v: 1` and a string `type`. Initial responses:

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
| `v`, `type` | Integer 1, string `command` |
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
| `wait` | `unit`: ID | Active army owns the available unit. Runs normal actively-chosen LT wait and its events. |
| `end_phase` | None | Requester owns the current phase. Runs existing endstep/turn-change/upkeep states. Blue passes to Green; Green passes through authoritative Red AI to the next Blue turn. |

The host independently computes legality; client movement/attack hints are not
trusted. Payloads cannot supply damage, HP, a path, random rolls, ownership or an
event script. Movement is committed immediately, once per unit phase; v1 has no
move-preview cancellation, canto commands, abilities, trading or arbitrary items.

Before applying a command the host also checks both seats, session, request ID,
revision, digest and expected phase. Duplicate IDs, including rejected attempts,
are retained for the live session. There is no retry that applies twice: a
duplicate rejects rather than rerunning the action. The per-army request budget
is 10,000 to bound this memory; restart the demo for a new session afterward.

`reject` contains `v`, `type`, `id`, `code`, `revision`. Representative codes are
`not_owner`, `wrong_phase`, `illegal_move`, `illegal_attack`, `unit_unavailable`,
`duplicate_command`, `stale_revision`, `state_mismatch`, `stale_phase`,
`peer_disconnected`, `wrong_session` and `session_finished`. Expected rejections
do not change simulation, revision or RNG. Clients do not automatically replay a
rejected tactical action. They request synchronization when their base is stale.

## Results and state

Every accepted command resolves to a quiescent human command boundary (or a
terminal outcome) on the host before another command is processed. An asyncio
session lock covers validation, resolution and ordered publication. Resolution
currently blocks host I/O briefly; no real-time responsiveness claim is made.

Both clients receive the exact same `state` packet:

| Field | Contents |
| --- | --- |
| `v`, `type` | Integer 1, string `state` |
| `session`, `revision` | Session ID and monotonically increasing accepted-command revision |
| `digest` | SHA-256 of canonical `state` JSON only: sorted dictionary keys, compact separators, UTF-8, no non-finite values |
| `state` | Schema-validated training-map projection described below |
| `result` | Null initially; otherwise command `id`, host-bound `team`, `action`, and a bounded authoritative outcome `summary` |

The projection contains `scenario: coop_training/v1`, a ruleset fingerprint,
map width/height/terrain, objective text, phase, turn, status, combat/growth/other
RNG state plus seed, and a stable ID-sorted unit list. Each unit includes ID/name,
team, position or null, current/max HP, dead/finished/moved/attacked flags,
movement remaining, level/XP, stats, inventory UIDs/names/durability, and advisory
legal move/attack choices. The fingerprint hashes authoritative engine/co-op
Python files and the installed default project's JSON database. Clients need no
matching local engine/assets because they only present state; both must see the
same session and fingerprint. Digests check this **projection**, not every LT
internal registry, skill, party, event stack or campaign-save field.

Snapshots go out only at discrete command boundaries and on explicit resync or
join. There is no frame-by-frame screen/state replication. In v1, Green's End
includes all Red AI actions in one revision; clients see the resulting board and
authoritative outcome summary, not Red's intermediate animations.

If engine resolution unexpectedly faults after mutation may have begun, the
host publishes a new revision with terminal `fault` status and freezes commands.
It does not report an unchanged-state rejection or attempt unsafe rollback.
Restart and inspect the host log; persistent crash recovery is future work.

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
  recovery exists. Host restart generates new credentials and a fresh map.

This contract is deliberately limited to the test map. Persistent campaigns,
deployment, recruitment, promotions, allied trades/healing, full Green leveling
parity and verified Internet play remain later milestones. Version the contract explicitly
when expanding these fields/actions; do not treat this projection as a safe
replacement for complete engine save/load.
