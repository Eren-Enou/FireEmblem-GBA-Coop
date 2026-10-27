# Campaign saves and full tactical parity: implementation methods

Status: **design and engine-readiness audit**, not a save/load or parity feature.
This document follows the tested [Internet transport path](INTERNET_PLAY.md).
It preserves the full goal: two allied commanders completing multiple chapters
with independent development, equipment and persistent ownership.

## Evidence from the actual engine

Reproduce the audit without writing/loading a game save:

```powershell
.venv\Scripts\python.exe utilities/audit_campaign_readiness.py
```

It writes an ignored diagnostic report. Both combat probes use the same class,
weapon, enemy, adjacent position and combat RNG state in fresh simulations; the
only army/phase difference is Blue versus Green. This isolates a concrete parity
gate without promising that all mechanics are equivalent.

| Finding | Source / consequence |
| --- | --- |
| Combat XP is gated on `team == 'player'` for attacker and defender | `app/engine/combat/simple_combat.py:handle_exp`; Green needs both active and counterattack XP |
| Growth method treats non-Blue as enemy leveling | `app/engine/unit_funcs.py:get_leveling_method`; parity cannot stop at XP |
| Default trading requires the same team as well as alliance | `app/engine/component_system/skill_system_base.py:Defaults.can_trade`; Blue/Green alliance alone is insufficient |
| Recruit-to-player clears AI only for Blue | `app/engine/action.py:ChangeTeam`; Green recruitment needs controller ownership and AI updates too |
| Party/roster queries filter `player` and persistence | `app/engine/game_state.py:get_all_units_in_party`, `get_all_player_units`; deployment/cleanup need owned-roster queries |
| Training units are generic, nonpersistent and share one sample party | The current demo is not a usable two-army campaign roster |
| Training bootstrap clears campaign events and freezes terminal boards | `coop_demo.install_demo()` and the network adapter are scenario fixtures, not campaign startup/transition logic |
| `GameState.save()` includes registries, event/action state and non-JSON values | Direct JSON dumping fails on a set in the probe; conversion alone would not validate restoration semantics |
| Only combat RNG is a top-level saved random-state field, with no explicit phase field | New checkpoints must include phase/order and all RNG streams rather than assuming the current dictionary is complete |

## Keep four identities separate

1. **Army slot** (`blue`, `green`): stable campaign ownership, persisted across
   chapters and sessions. This is not the current TCP connection or bearer token.
2. **Tactical team** (`player`, `other`): engine allegiance/palette/phase. Preserve
   these IDs and alliance mechanics; do not globally replace every `player` test.
3. **Story faction**: narrative identity, unaffected by which friend controls it.
4. **Party**: inventory convoy, money and roster/deployment organization. Introduce
   two real parties or an explicit per-army resource ledger; the sample's shared
   `Eirika` party is not sufficient.

The host owns a stable unit-ID-to-army mapping, including dead/undeployed units.
After a saved campaign is loaded, issue fresh session credentials mapped to those
army slots. Do not store TLS private keys, bearer tokens or socket IDs in a save.
Remote clients cannot claim an arbitrary saved army during unauthenticated join.

## Campaign bootstrap and expected input barriers

Create a separate trusted campaign bootstrap rather than extending the training
map's event-clearing setup. Preserve audited campaign events and original
objectives, attach persistent armies/parties, and select chapter IDs only from
the authorized campaign manifest. A client cannot provide a level filename or
event script. Resolve chapter rewards, recruitment and level-end events once,
then enter an explicit intermission/checkpoint/deployment barrier for both armies
before starting the next chapter. Do not keep the prototype's terminal-board
freeze as campaign progression logic.

Extend the host's resolution interface to return an expected decision/prompt
boundary, not just `free` or engine fault. Dialogue, shops, promotions, deployment
and story decisions need host-issued prompt IDs, allowed answers, authorized
army slots, revision checks and a specified timeout/default policy. An expected
input prompt must not exhaust the current synchronous `settle()` frame limit.
Only the host resumes the event after validating a reply. Save requests defer or
reject while an unsupported prompt is open. These phase/status/prompt additions
need an explicit protocol version and matching client controls.

## Save method A: chapter-boundary checkpoints first

Implement a separate **strict JSON DTO**, e.g. `coop-campaign/1`, with exact
fields, scalar ranges, entity-count/size limits and referential checks. It is not
the public display projection and is not a renamed pickle or arbitrary output
of `GameState.save()`. Initial boundary is after chapter results have resolved,
before deployment for the next chapter; no running combat/dialogue/event stack
is supported. Use original, authorized two-chapter fixtures with persistent
unique units, not the temporary generic training roster.

Required field groups:

| Group | Required state / invariants |
| --- | --- |
| Identity/version | Schema version, campaign/project ID, engine/rules manifest, checkpoint ID/generation, completed and next chapter IDs, boundary kind |
| Ownership/parties | Army slots, unit ownership map, persistent party IDs, convoy/money/deployment order; every owned unit has exactly one owner |
| Units | Stable IDs and trusted prefab/class IDs, level/XP, stats, growth points/rates, weapon XP/ranks, permanent skills, HP/mana/fatigue, dead/permadeath flags, persisted fields |
| Items | Unique instance IDs, trusted item prefab IDs, owner/convoy location, uses and whitelisted component state, equipment/accessory and parent/subitem references; no duplicated item ownership |
| Skills/supports | Unique instance IDs, trusted skill IDs, whitelisted counters, source ownership, support pairs/ranks/progress; rebuild transient aura children |
| Campaign state | Allowlisted game variables, event completion flags, recruited IDs, objectives/results, unlocked lore, records and supported mode options |
| Randomness | Seed and combat/growth/other generator state; stable leveling identifiers; exact manifest required for deterministic continuation |

Resolve variable/component-state schemas from trusted project definitions. Unknown
IDs, unknown types, arbitrary component code, polymorphic class names and event
scripts from a save must reject before mutation. Do not use dynamic `getattr`
action restoration on external records. If a project needs unsupported custom
state, declare the checkpoint unsupported instead of silently dropping it.

Restore into a **new host simulation**, not an already running one: validate all
types/IDs/limits/uniqueness/references; allocate trusted unit/item/skill objects;
resolve cross-references and ownership; restore permanent values; rebuild the
board, auras, ranges, fog and derived caches; set UID generators above all restored
IDs; set all RNG streams; then validate invariants again. Do not broadcast or
swap the live session until the candidate is complete. Avoid loading arbitrary
item/skill component arrays: their existing restore paths accept component values
beyond the limited state required by the checkpoint contract.

LT modules import a shared `game` singleton. Initial Load should therefore be
startup-only in a fresh host **process**, before listening for clients, with
pure DTO validation before reconstruction. Do not instantiate a second Simulation
inside a live server and expect isolated globals. Future live-load handoff needs
a separate candidate process and an explicit session/connection handoff design.

Define a stable save-compatibility manifest from canonical project data, versioned
simulation code and explicit supported-component schemas. The current display
ruleset fingerprint also hashes presentation files and raw working-copy bytes;
it should not become a long-term save-compatibility policy by accident. Normalize
source line endings and distinguish presentation changes from rules migrations.

## Save method B: mid-map quiescent checkpoints next

After A passes chapter-transition tests, extend the schema/version for a human
command boundary: chapter/terrain/layers, units/enemies on-map, regions/fog,
phase **ID and phase order**, round, action flags and movement remaining,
objective state, supported timed/status effects, region timers, supported event
completion state and all three RNG streams. No mid-animation save is needed.

The host's command/session lock defines a barrier: drain the accepted action and
result, verify no pending combat/event/dialogue/promotion/region action, capture
the DTO and revision, then save. If a prompt is pending, refuse/defer the save
with a visible reason. The existing `free` state alone does not prove every
external event effect is safely serializable.

Prefer not to persist the turnwheel/action log in early multiplayer saves. The
network session already has turnwheel disabled. Rebuild a clean action log from
the restored command boundary. If exact event continuation is later required,
add explicit allowlisted event continuation records; do not serialize Python
processor objects or executable scripts supplied by the client.

## Disk commit, recovery and migrations

- Host-only save authority. An eventual client Save command requests a checkpoint
  at the current revision; it does not supply filenames or replacement state.
- Serialize canonical validated JSON plus checksum and generation. A checksum
  detects corruption, not an attacker who can rewrite both payload and checksum.
  Import files remain untrusted and require complete validation.
- Write a new file in the destination directory, flush and fsync it, close it,
  then atomically replace the manifest pointer/file. Keep a previous good
  generation; acknowledge Save only after the commit step succeeds. Test exact
  Windows crash/antivirus/locked-file behavior rather than assuming POSIX durability.
- On restart, validate current and fallback generations and report any recovery.
  Never silently substitute an incomplete checkpoint or partially load the live
  session. Reject future versions; migrations are explicit pure transformations
  between known DTO schemas with fixture tests and a backup of the original.
- A load creates a new session epoch and fresh invitations. Old queued commands
  must fail session/revision checks even when an old revision number repeats.
- Add a bounded command/result journal only after checkpoints work; persist
  commands/results with commit ordering and replay under the exact rules manifest.
  Deduplication must survive journal recovery. A display snapshot is not that journal.

## Tactical parity method and acceptance matrix

Use explicit predicates for **human participant**, **acting controller**,
**ally** and **persistent owned roster**. Human participation includes both armies
even during Red counters; acting-controller permission stays phase-bound. Keep
single-player fallback when co-op ownership is absent. Audit each hardcoded Blue
check by its purpose rather than replacing strings indiscriminately.

| Increment | Engine reuse / protocol work | Required proof |
| --- | --- | --- |
| XP, growth and level-up | Use common human-participant policy in combat XP, mana, weapon XP/alerts and growth-method selection; host resolves level-ups, clients display actual deltas | Isogenic Blue/Green hit, miss, kill and Red counter tests; fixed/dynamic/random growth; XP thresholds/caps; saved continuation matches |
| Equipment, abilities and items | Add explicit Equip/UseItem/UseAbility commands validated against inventory, charges, targets, range and skill restrictions; reuse LT ability/item systems | Equip changes stats/range correctly; used item/skill charges and cooldowns match on both clients; illegal inputs do not mutate |
| Combat variants | Extend approved target selection for spells, area effects and multi-target/sequence items into LT's existing interaction system; never accept client-supplied damage/playback | Ranged/counter/crit/miss, area and sequence targeting, skill modifiers and per-use costs match for both armies and both clients |
| Healing and allied interactions | Permit valid allied targets through LT target rules; requester owns the actor, not necessarily the ally; host resolves healing/support actions | Blue heals Green and vice versa, range/HP caps/XP/durability, enemy heal rejection, support/pair-up/rescue/canto cases |
| Trade/resources | Host atomic transaction for two unique item instances and explicit army resource ownership. Proposed default: cross-army transfers require receiving commander consent bound to revision and offer ID | No item duplication/loss on stale consent, full inventory, disconnect or retry; convoy/money ownership stays independent. Confirm consent UX before implementing it |
| Recruitment | Event chooses destination army explicitly; update tactical team, ownership, party, AI, supports and roster as one host transition | Recruit into either army; unauthorized/duplicate recruit denied; unit persists next chapter with correct controller |
| Promotion/classes | Host validates trusted promotion choices and resolves class/stat/weapon/skill changes using LT; publish explicit prompt ID, controlling army and legal choices | Both armies promote from identical inputs; pending choices pause resolution; stale/out-of-owner answers rejected; checkpoint waits for prompt completion |
| Permadeath/persistence | Owned-roster tracking includes dead/undeployed units; cleanup and next-level setup respect both armies | Casual/permadeath modes, equipped drops, dead-unit exclusion and persistent identity across two chapters |
| Deployment/story/objectives | Per-army owned roster queries and deployment commands; host orders story events and shared objective decisions | Two original chapters completed by two clients; event/recruit/defeat flags fire once; a commander cannot deploy another army's unit |
| Fog/status/terrain | Preserve host-side vision and phase/upkeep effects. Proposed co-op view is shared allied vision; filter snapshots, legal-action hints and summaries before publication | Hidden enemies never leak through packets, highlights or logs; visible-client digests agree; poison/regen/status timers and terrain apply once at the proper LT boundary |

Extend public snapshots/versioned events for new visible state (mana, equipped
item, skill charges, class/promotion choices, supports). Preserve host-only RNG
and strict command validation. Do not advertise healing/trade/promotions merely
because corresponding LT modules exist; each requires an actual network command,
client control and synchronized evidence.

## Delivery sequence and completion gates

1. Finish the private two-PC TLS pilot and liveness/admission slice from
   [Internet play](INTERNET_PLAY.md); record unverified WAN conditions honestly.
2. Add the first parity vertical slice: both armies gain XP and level up from
   real network combat, including counters, with identical published results.
3. Introduce persistent original rosters/two parties and two original chapters;
   implement checkpoint A, corruption/atomicity/migration tests and host restart.
4. Expand Equip/Use/Heal/Trade and promotion/recruitment/deployment with the matrix
   above; add checkpoint B only for supported quiescent state.
5. Verify two clients on separate Windows PCs finish both chapters, restart the
   host from a committed checkpoint, reclaim their original armies, and continue
   with matching state/XP/inventory/RNG and no duplicate rewards or events.

This plan does not assert any of those future mechanics already work. Each gate
needs automated engine/transport tests plus the matching-scope player evidence,
documentation update and a tested GitHub milestone commit.
