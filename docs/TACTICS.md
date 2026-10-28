# Phase 5D: tactical reading and decisions

The host supplies tactical information with each committed protocol-v7 snapshot.
Clients select and compare that information locally. Hovering, toggling an overlay,
proposing, cancelling or comparing weapons sends no preview request, consumes no
request IDs, advances no revision and cannot control another army. Actual confirmed
commands retain the existing ownership/session/revision/digest and native checks.

## Launch and controls

Use the existing Python 3.12 environment from the repository root:

```powershell
.venv\Scripts\python.exe run_network.py host --scenario campaign --seed 0 --checkpoint-dir artifacts/campaign-5c
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

All peers must update to **protocol v7**. The normal campaign and trusted save
format are unchanged; Phase 5C chapter checkpoints remain compatible. Restore
with the existing `host --restore PATH` command and new invitations. Remote
verified TLS uses [INTERNET_PLAY.md](INTERNET_PLAY.md). Actual WAN/two-PC acceptance
remains unverified. No mid-map save, undo, new campaign or engine formula exists.

- Click an enemy to inspect its movement/weapon reach; right-click an enemy
  inspects it even when a selected weapon could attack it. **F** toggles combined
  active Red/hostile-army reach; selecting an enemy also shows its own reach.
- Red outer borders show attacks from current enemy positions. Orange shows
  potential attacks after native movement. Purple outlines show movement-only
  squares. These describe possible danger, not AI intent or guaranteed attacks.
- Cyan inner borders show your selected unit's legal movement. A gold border is
  a proposed destination. Unit tokens/occupied terrain and unavailable movement
  are labelled when inspected. A warning marks threatened allied positions.
- Click a reachable empty tile to **propose** a move. Read terrain, native path
  cost/remaining movement and danger before pressing **Enter** or Confirm.
  **Esc**, right click or Cancel cancels without sending. There is no undo after
  confirmation. W/End phase, healing, personal use and preparation retain their
  existing controls; see [PREPARATION.md](PREPARATION.md).
- Select an owned unit and weapon by inventory row or number. Hover a legal enemy
  for its forecast. Click that target to propose an attack; **Enter** confirms.
  Change the selected weapon to compare forecasts; changing selection cancels
  the prior proposal. The current equipped defensive weapon is named separately.
- Terrain inspection shows the trusted terrain name, base DEF/RES/avoid bonuses,
  and the selected class's native movement cost. Occupied/reachable/unreachable
  labels are independent of threat colour. Blue/Green/Red identity, HP, class,
  equipped weapon/uses and action state remain visible.
- R requests authoritative resynchronization. New authoritative snapshots,
  resync, disconnect/reconnect and changed equipment/chapters invalidate proposals.
  A proposal binds session, revision and digest; confirmation never replays an
  old command automatically. Previews pause while pending/resynchronizing or
  disconnected. An acknowledged command is labelled COMMITTED with its revision.

## Calculations and their limits

`app/coop/tactics.py` is a read-only transport projection. `Session.state_projection`
attaches it to the existing native board snapshot. `Simulation`, the campaign,
preparation, checkpoint schema/native reconstruction and upstream engine remain
unchanged. Both clients receive the same complete tactical fields and digest.

| Information | Native source |
| --- | --- |
| Movement and costs | `PathSystem.get_move_selection`/`get_valid_moves`, `get_path`, `get_path_cost`, `movement_funcs.get_mcost` |
| Enemy current attack area | `TargetSystem.get_attackable_positions` with an actually available/equippable weapon |
| Enemy reach after movement | Native boundary `_get_all_attackable_positions` for each available weapon; native movement and guard-AI zero-move rules |
| Forecast | `combat_calcs.compute_damage`, `compute_hit`, `compute_crit`, `compute_attack_phases`, `compute_multiattacks`, `can_counterattack`, `compute_overall_advantage` |
| Terrain | `game.get_terrain` and trusted static terrain-skill components; native applied terrain skills participate in actual combat calculations |

Enemy pathfinding permits native allied traversal, but occupied stopping squares
are removed. A hostile body can block a route. Equipment availability, native
range/no-attack-after-move and configured line of sight govern coverage. Native
line of sight is explicitly labelled on/off; the UI never invents wall-blocking
for weapons when the engine disables it. Terrain tint does not make an impassable
wall a movement destination.

Threats use **current board occupancy**. Moving a blocking vanguard can open an
enemy route that was blocked when the proposal was drawn. Inspect the formation,
and recheck the new authoritative ranges after a confirmed move. The client does
not predict future AI movement, ally commands or hypothetical future formations.
A tile outside the shown weapon area is labelled that way, never guaranteed safe.

Forecasts cover the audited Iron Axe/Hand Axe and simple supported stat passives,
Canto and Forest terrain in the campaign's True Hit mode. Other RNG/combat modes
(such as Grandmaster's altered damage) explicitly show unavailable forecasts. Only inspected component types are accepted. Complex
proc skills, paired/assisted combat, arbitrary items, sequence/splash effects and
unsupported terrain effects show unavailable values rather than invented numbers.
No hypothetical equip, relocation, action, skill creation, combat solver or RNG
call is used to create a forecast. A forecast uses the selected weapon at the
**actual current position**; it does not forecast an uncommitted destination.

HIT is LT's **displayed rating out of 100**, not a claim that True Hit's multi-RN
rolls give that exact probability. The native RNG mode is named. CRIT is the native
critical value, or `--` when unavailable/disabled. Strike counts are native planned
phases/multiattacks, capped by uses as in LT's forecast. They are **up to** counts:
a kill, death or changed combat conditions can stop subsequent hits. A counter
requires native eligibility and survival of the opening attack. No predicted XP,
level-up, exact outcome probability, AI target preference or total guaranteed
damage is shown. Existing unsupported network canto commands remain outside this
slice; the native single-player/canto systems are unchanged.

The current shared board contract supports no fog. Active fog or fog regions
reject projection before any board is transmitted; there is no hidden-enemy
omniscient overlay fallback. Future fog/stealth needs a separate visibility
contract for units, terrain, occupancy/path hints and allied information sharing.
It must not merely hide enemy tokens in the renderer.

## Reproducible decision demonstration

```powershell
.venv\Scripts\python.exe -u utilities/smoke_network.py --tactical
.venv\Scripts\python.exe -u utilities/smoke_network.py --tactical --tls
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_tactics -q
```

The graphical driver completes the original two-chapter campaign over real
sockets with two independent renderers. It uses only legal native commands and
public snapshot hints. Local overlay/proposal/cancel operations are inserted
between explicit commands, so both observers still see identical revision history.
Evidence remains ignored under `artifacts/network-smoke/run-*/`:

1. **Positioning:** `positioning.png` proposes Mira at crossing `(6,2)` while the
   native threat fields warn of potential attacks. Her current protected `(5,3)`
   position is outside the shown weapon reach. Cancel keeps her in formation.
   The separate controlled native AI test actually compares those choices:
   coordinated healing preserves her; moving her onto the crossing kills her.
2. **Weapon:** after normal intermission preparation, retain Iron Axe and take/
   equip Hand Axe. `iron-forecast.png` and `hand-forecast.png` compare the same
   legal Chapter 2 defender at the same committed revision. Iron trades higher
   damage/accuracy for range one; Hand offers range two and ranged counters at
   lower damage/accuracy. At adjacent range both may be countered. A separate
   controlled real ranged hit proves an Iron-equipped defender cannot counter
   the Hand Axe from distance two; native HP/durability agree with the forecast.
3. **Cooperation:** Blue and Green heal across armies and protect the crossings.
   The demonstration finishes both chapters with retained characters/resources.
   The controlled reckless comparison uses the same native enemy AI and seed,
   rather than inventing an enemy phase or suppressing deaths.

The executable validators bound every field, position, item/unit reference,
forecast metric, list and frame. Unsupported/malformed requests cannot submit
preview effects or other-army commands. Native purity tests compare unit/item/
skill state, action flags/log size, events, progression records, RNG streams and
UID generators before and after repeated queries. Actual results are recorded in
[TESTING.md](TESTING.md) and [PROGRESS.md](PROGRESS.md).

## Manual two-person checklist (not yet performed)

- Both people update to the same commit; launch campaign host and Blue/Green
  clients, using verified TLS for a two-PC pilot. Confirm army names/revisions.
- Each inspect an enemy and toggle F. Identify current reach versus after movement,
  ranged versus melee equipment, a blocked wall and occupied stopping tile.
- Blue proposes Mira at the crossing. Green explains the risk; Blue cancels.
  Confirm neither client changed revision, HP, uses or position.
- Hover forest and plain with a selected healer/vanguard; read step cost and
  DEF/avoid. Propose then confirm one legal move; both see the same result.
- At Chapter 2, compare Iron/Hand on the same defender. Explain damage, HIT rating,
  CRIT, doubling and counter eligibility before confirming. Try a range-two attack.
- Coordinate both healers/guards through Red's phase; record surprises rather
  than assuming the overlay predicts AI intent. Recheck after a blocker moves.
- Cancel another proposal, resync/rejoin, and verify it cannot be confirmed stale.
- Save prepared intermission, stop all processes, restore and finish Chapter 2.
- Record readability, colour/contrast and confirmation mistakes for both people.
  No human, separate-PC or Internet success is implied by automated tests.

Recommended next gameplay milestone: use that two-person pilot to refine formation
and forecast UX, then expand one native skill/item interaction at a time with
matching purity, forecast, authority and persistence tests.
