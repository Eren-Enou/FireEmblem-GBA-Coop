# Assessment: smallest local second-army extension

Inspected installed baseline `3ba9bd923c82b36c0d57767a75d540f2bcdbc166`,
engine version `2026.10.18a`, on October 27, 2026. Source:
[Lex Talionis / LT-Maker](https://gitlab.com/rainlash/lt-maker).
Findings below come from this checkout, not an assumption of built-in multiplayer.

## Existing engine

| System | Relevant source | Findings and implications |
| --- | --- | --- |
| Team identity and alliances | `app/data/database/teams.py`, `app/engine/objects/team.py` | Unit `team` controls tactical allegiance and palette. TeamCatalog orders phases and stores symmetric alliance pairs. `player` and `other` are allied by default; `other` already has green palettes. Alliance does not grant human control. |
| Factions and rosters | `app/data/database/factions.py`, `app/data/database/level_units.py`, `app/engine/objects/unit.py` | Story faction, party, persistence and tactical team are distinct. Generic units derive names/icons from a faction. Changing story faction cannot implement ownership. Persistent player rosters and party queries are often hardcoded to `player`. |
| Input and selection | `app/engine/input_manager.py`, `app/engine/general_states.py` | SDL inputs become abstract buttons. FreeState selects units through `skill_system.can_select`; MoveState checks movement membership and occupancy before action.Move. The skill default selects only `player`. Skill overrides can change that, so co-op needs a separate ownership guard. |
| Phase routing | `app/engine/phase.py`, `TurnChangeState`, `PhaseChangeState`, `AIState` in `general_states.py` | PhaseController cycles DB.teams and skips empty phases except Blue. TurnChangeState originally enters `free` only for `player`; every other team enters `ai`. Blue increments the round counter and handles turn/level-start events. End and auto-end also run an AI pass for the outgoing army. |
| Movement | `app/engine/pathfinding/path_system.py`, `app/engine/pathfinding/`, `app/engine/movement/`, `MoveState` | Existing terrain costs, allied pass-through, enemy blocking, occupied-destination rejection and movement action playback can be reused. Interrupted movement originally returned only Blue to human control. |
| Combat and progression | `app/engine/combat/interaction.py`, `simple_combat.py`, `map_combat.py`, `solver.py`, `app/engine/action.py`, `exp_funcs.py`, `unit_funcs.py` | Actions already resolve HP, damage, weapon uses and deaths. Enemy/ally skill checks consult alliances, so Red can target either army. Experience, leveling rules, alerts and some animation/menu decisions still special-case `player`; full parity needs a later audit. |
| Randomness | `app/utilities/static_random.py`, `combat/solver.py`, RNG-recording actions in `action.py` | Combat uses an LCG and records RNG changes for the turnwheel. Growth and other random streams also exist. A combat seed alone is not a complete multiplayer determinism contract. |
| Save/load | `app/engine/game_state.py`, `save.py`, `objects/unit.py`, `objects/level.py` | Save dictionaries include units, inventories, teams, game/level vars, state stack, events, action log and combat RNG state; disk saves use pickle. Runtime systems including PhaseController are rebuilt on load. Current phase/order and all RNG streams need an explicit multiplayer snapshot contract. Never deserialize remote pickle data. |
| Events and objectives | `app/events/triggers.py`, `event_manager.py`, `event_functions.py` | Generic PhaseChange carries a team; named Player/Enemy/Other turn triggers and scripts often assume Blue is the only player. Recruitment via ChangeTeam and campaign cleanup also special-case `player`. Existing campaign scripts cannot be presumed safe for co-op. |

## Chosen local change

1. Add `human_control.py`: `_human_teams` in existing game vars opts in to local
   ownership; without it the human team remains `player`. This is a policy helper,
   not a new simulation or transport.
2. Keep canonical team IDs. Reorder the **in-memory demo DB** to `player`, `other`,
   `enemy`, `enemy2`, and explicitly ally Blue and Green. Empty Purple is skipped.
3. Route the opted-in Green phase to the existing FreeState. Keep Blue's existing
   round accounting and event sequence. Focus the cursor on Green at phase start.
4. Allow human-team selection in the generated skill default, then independently
   enforce active-army ownership in FreeState even if a skill says selectable.
   Existing skill restrictions continue to apply.
5. Use active-team units for auto-end and AUX cycling. Skip the outgoing AI pass
   for explicitly human-controlled armies, including unfinished units after End.
6. Return interrupted human movement to the existing human control states.
7. Install a new scenario in memory: original 15x10 terrain, original geometric
   tokens, two Blue units, two Green units, three Red pursuers, ordinary axes,
   shared rout victory, and defeat if either allied army is eliminated.

The prototype uses one keyboard/mouse and one game process. Passing the phase
passes control to the next person. There are no separately authenticated players.
The demo disables initiative, turnwheel and campaign save/suspend options; these
require broader work than the local experiment. There is no networking code.

## Next architecture decision: host authority

Use one authoritative engine simulation and discrete commands, rather than
continuous position replication. Keep commands distinct from presentation input:
an SDL SELECT press is context-dependent and is not a suitable network command.

Before implementing a transport, define Move/Attack/Wait/EndPhase requests with
session/player identity, unit ID, expected phase/revision, a unique request ID,
and destination/item/target IDs. The host must independently validate ownership,
unit state, movement costs/path/occupancy, item availability, attack range and
targets against its current state. The local FreeState check is not sufficient.

The host alone advances combat/growth/event RNG, enemy AI and event sequencing.
Publish ordered resolved results plus monotonically increasing revisions and a
canonical simulation-state digest. Clients animate accepted results; they must
not reroll combat. Pin engine/project versions and asset/data hashes at join.
Start with no client prediction and serialize commands during phase transitions,
combat, dialogue and event execution.

First define stable, schema-validated snapshots (not pickle) for unit/item/skill
registries, ownership, phase/order, turn, objectives, event progress and all RNG
streams. Snapshot only at defined quiescent boundaries initially. Reconnect uses
an authenticated session token, last acknowledged revision, snapshot plus ordered
results; stale/duplicate commands cannot apply twice. On a digest mismatch, stop
commands and restore an authoritative snapshot before proceeding. Mid-animation
reconnect and custom Python event side effects need separate investigation.

Campaign work then needs independent rosters and inventories, Green XP/leveling,
recruitment ownership, allied support/healing/trade policy, death/cleanup and
campaign objective audits. These changes are intentionally absent here.
