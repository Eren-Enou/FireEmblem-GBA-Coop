# Two Banners: cooperative campaign

Phase 5A links two original chapters in one authoritative LT host session. Blue
and Green have permanent characters and separate native parties. This is live
continuity during battles, with Phase 5B [chapter-boundary checkpoints](CHECKPOINTS.md)
for complete host shutdown/restart after Chapter 1. Mid-map saving, cross-army trading,
recruitment, promotion, shops and deployment menus remain unsupported. All peers
must run the same protocol-v7 version.

Phase 5C adds [personal items and intermission preparation](PREPARATION.md).
Captains carry Vulneraries; separate party convoys offer Hand Axe and Mend.
Equipment changes clear readiness and require a confirmed save. Use a **new
checkpoint folder** for these changed rules; Phase 5B manifests reject explicitly.
The revision-38 statistics below describe the baseline tactic without preparation;
the prepared acceptance uses a different reproducible sequence.

## Play locally

From the actual `FE-GBA-Coop` repository root, run these in three terminals:

```powershell
.venv\Scripts\python.exe run_network.py host --scenario campaign --seed 0 --checkpoint-dir artifacts/campaign-5c
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Use the invitation directory printed by the host if overridden. For remote TLS,
follow [INTERNET_PLAY.md](INTERNET_PLAY.md), adding `--scenario campaign --seed 0`
to the host command. Keep certificate/name verification enabled. Separate-PC/WAN
campaign play has not been tested; loopback TCP/TLS process tests are recorded in
[TESTING.md](TESTING.md). Do not distribute an unauthorized sample-asset bundle.

Click your unit to select it. Click a reachable empty tile to propose movement,
then Enter confirms or Esc cancels. F toggles enemy threats. See
[TACTICS.md](TACTICS.md) for native forecasts and terrain/risk inspection.
Choose an item row or number key, then hover an orange enemy for its forecast and click to propose an attack
(Enter confirms), or click a mint
ally to heal. W waits; E ends your phase; R resynchronizes. Blue and Green each
control their own army during its phase; Red AI runs on the host after Green.

After Chapter 1 rout victory, both clients show **CHAPTER COMPLETE**, surviving
and fallen characters, levels/XP, equipment/uses, readiness and the next title.
Select characters for full stats and weapon XP. Both commanders independently
press **Ready [E]**. One ready vote does not load the next map. Readiness survives
a client disconnect/rejoin while the host lives. With a disconnected peer, new
commands pause. If simultaneous votes use the same old revision, the stale one
rejects and resynchronizes; press Ready again after seeing the updated state.
Never replay a command whose outcome is unknown; rejoin first.

## Characters and transition rules

| Character | Stable ID | Owner / native party | Story faction | Role |
| --- | --- | --- | --- | --- |
| Aren | `Blue_Captain` | Blue / `Blue_Banner` | River Wardens | Vanguard, Iron Axe |
| Mira | `Blue_Healer` | Blue / `Blue_Banner` | River Wardens | Cleric, Heal |
| Tovan | `Green_Captain` | Green / `Green_Banner` | Hill Watch | Vanguard, Iron Axe |
| Sela | `Green_Healer` | Green / `Green_Banner` | Hill Watch | Cleric, Heal |

The host's explicit owner mapping is separate from tactical `team`, story
`faction`, native `party`, and connection credentials. Changing a tactical team
does not transfer campaign ownership. Allies may heal one another without
changing any of these identities. Native unique `UnitPrefab`/`UniqueUnit`
characters are persistent, rather than generic demo units with copied stats.

At the second ready vote, the host calls native `GameState.clean_up()` and the
**same instance's** `start_level()` with the next trusted manifest ID. Native
`LevelObject.from_prefab` reuses registered characters by ID. Neither a display
snapshot nor a second Simulation reconstructs them. The native unit/item/skill
objects, IDs, classes, levels/XP, stats, growth rates/points/caps, weapon XP,
equipment and uses, personal fields and applicable permanent skills remain.
Native end-chapter item/skill hooks apply; arbitrary custom components are not
an audited persistence guarantee.

Native cleanup restores HP to max, resets guard/action/chapter-local state,
removes nonpersistent enemies and unused enemy items/skills, and resets mana
only when the database's `reset_mana` rule is enabled. Existing RNG streams are
continued, not reseeded. Level loading rebuilds board/AI/events/phase systems;
Chapter 2 starts Blue turn 1. No item uses, XP, levels or rewards are refilled.

This campaign explicitly uses **permadeath** and disables convoy-on-death for
both armies. Dead characters remain registered and owned with their equipment;
they are not redeployed or resurrected. Native cleanup can fill their HP field,
but `dead` remains authoritative and HP does not revive them. If either army
loses all deployed characters, the shared defeat event ends the campaign.
Casual revival and automatic death-to-convoy behavior remain outside this slice.

Chapter 1 intermission is automatically checkpointed by the normal campaign
host before either vote applies native cleanup. Wait for the saved confirmation
before closing all processes. S saves/retries at this boundary. A save failure
blocks Ready until a successful retry; see [CHECKPOINTS.md](CHECKPOINTS.md) for
restore commands, compatibility, generation fallback and supported native state.

The session lock covers both votes' mutations and the complete transition. The
second vote publishes one revision only after reaching a human command boundary.
No intermediate half-loaded map is broadcast. Unexpected lifecycle faults freeze
the session; if no valid active level remains, clients receive the last committed
board marked `fault`. There is no in-process rollback; recovery uses the last valid chapter-boundary
checkpoint in a new host process.

## Chapters and tested tactics

**The First Alliance** is a 13x8 map with two crossings through a central wall.
Blue starts at the upper crossing and Green at the lower; protected healers can
coordinate across banners. Three native Red pursuers threaten the crossings.
Vanguards declare HP 36/DEF 7 and inherited Fighter growths; Clerics retain native
HP 18/MAG 1. All four start at 95 XP and captains at 16 HP to expose real combat
and support growth quickly. Those are declared original fixture conditions.

**Holding the Line** is a wider 16x9 map, with its barrier/crossings shifted,
different forest and Red placements, and a more distant reserve. The surviving
characters start recovered but with the same used equipment and earned stats.
Both chapters use native pursuit AI, shared rout and army-elimination events.

The seed-0 acceptance driver heals the most vulnerable reachable ally (cross-army
on equal need), holds positions on turn 1, attacks weak adjacent enemies on later
turns when healthy enough, and advances after turn 3 if needed. Blue's healer
can reach both captains; Green's initially reaches Blue. Prefer urgent care over
blindly alternating cross-army heals, and avoid attacking with a critically
wounded frontliner. These are tactics for the declared fixture, not universal
victory guarantees.

The tested run completes Chapter 1 at revision 18/turn 4; both ready votes load
Chapter 2 at revision 20. Final shared victory is revision 38/Chapter 2 turn 4.
At transition Aren retains level 3/16 XP, STR 8, Axe XP 41 and axe UID 100/38
uses; Tovan retains level 2/14 XP, STR 8, Axe XP 33 and UID 102/43 uses. Both
healers retain level 2/28 XP and their original Heal instances with 27 uses.
A separate controlled real Chapter 2 hit proves earned STR 8 deals **11 damage**,
where the starting STR 7 yields 10 under the same native damage rules.

Training, progression and Mutual Aid remain separate unchanged scenarios.
Generated maps/tokens are original code; inherited UI/audio/icons still require
an asset audit before a standalone release.

## Chapter-boundary recovery and next gates

Checkpoint A is now implemented for this campaign's Chapter 1 intermission;
see [CHECKPOINTS.md](CHECKPOINTS.md) and actual [test results](TESTING.md).
Next gates are a two-human/two-PC TLS recovery pilot and deliberate expansion of
the supported native-state matrix. Mid-map checkpoints require a separate schema
and quiescent event/phase/terrain contract; they are not implied by boundary saves.
