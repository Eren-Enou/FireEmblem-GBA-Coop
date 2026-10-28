# Phase 5C: equipment and personal resources

The Two Banners campaign now gives each captain a three-charge native Vulnerary.
Each independent party starts with one Hand Axe and one Mend in its own convoy.
The original Iron Axes and Heal staves remain. No new assets, engine changes or
item formulas are introduced. Training, progression and Mutual Aid are unchanged.
All host/client processes must run protocol **v7**.

Phase 5D adds [tactical previews](TACTICS.md); preparation and checkpoint mechanics
are unchanged, and Phase 5C saves remain compatible.

## Personal use during battle

Select an owned character and their Vulnerary row (or number key), then press
**U**, or click that character's mint target ring. Native LT resolves self-use:
10 HP before any native modifiers, capped at maximum HP, one charge on a hit,
removal after the last charge, and a finished action. It cannot heal another
character or replace a staff action. Move first if useful; using it spends the
character's remaining action. Full-health, exhausted, dead, finished, wrong-owner,
wrong-phase and unavailable item requests reject. The host accepts only the
trusted Vulnerary and a self target; clients never provide healing amounts.
The selected item explains its effect and whether current action conditions
allow use. Staves still use the existing allied healing path.

## Prepare at Chapter 1 intermission

Start the campaign with a fresh checkpoint folder; see [CAMPAIGN.md](CAMPAIGN.md)
and [CHECKPOINTS.md](CHECKPOINTS.md). After victory, select your character in the
roster, then click an inventory row or use its number key:

- **Q: Equip** the selected carried weapon. An already equipped weapon rejects
  without change. The panel names current equipment.
- **D: Deposit** the selected carried item into your party's convoy.
- Click a convoy row, or use **Up/Down** to select through it; **T: Take** transfers
  it to the selected character. The convoy displays the selected item's effect.
- **S: Save** the complete current preparation. Wait for the saved confirmation.
- Both commanders press **E: Ready** after saving. Any later equipment mutation
  clears both votes and requires another save.

The host checks permanent owner, tactical team and party independently. Item UID
must identify exactly one native inventory/convoy reference with matching owner.
The five supported prefabs are Iron Axe, Hand Axe, Heal, Mend and Vulnerary.
Native inventory capacity and item availability/class/weapon rank apply when
withdrawing; native equip eligibility applies when equipping. Fallen characters
cannot prepare. A convoy is bounded to 20 entries; transfers cannot cross parties.
Preparation requires configured checkpoint storage. It is phase-independent at
the intermission, while battle item use requires the owning army's active phase.
No command creates, purchases, discards or copies an item.

| Choice | Native benefit and cost |
| --- | --- |
| Iron Axe | E Axe, range 1, might 8, hit 75, 45 initial uses |
| Hand Axe | E Axe, range 1-2, might 7, hit 60, 20 initial uses; enables ranged attacks/counters at lower damage/accuracy |
| Heal | E Staff, adjacent ally, MAG+10 HP capped, 30 initial uses |
| Mend | D Staff, adjacent ally, MAG+20 HP capped, 20 initial uses; more healing with a smaller reserve |
| Vulnerary | Any character, self +10 HP capped, 3 initial uses; consumes that character's action |

Vanguards have native Axe eligibility; Clerics have native D Staff eligibility.
An item may remain stored for later; taking a weapon does not change another
character's ownership. Native autoequip can select a newly taken weapon if the
character had none. Explicit equip determines the defensive weapon; battle
attacks can still select any legal carried weapon and equip it normally.
Native cleanup fills HP at Chapter 2 start but **never replenishes item uses**.
Money and bonus EXP remain separate and persist; this phase adds no resource UI
or spending command.

## Saved and unsaved preparation

The first settled intermission is saved automatically. Each accepted preparation
operation marks the boundary **dirty / UNSAVED** and clears both Ready votes.
This status is published at the command's new revision. A save acknowledgement
means the atomic store finished its generation write; only saved/restored states
permit Ready. Disk failure publishes an error and keeps Ready blocked until S
succeeds. Clients resynchronize on stale revisions and must not replay unknown
outcomes. All mutation, capture and publication occur under the host session lock.

Closing with UNSAVED changes restores the last confirmed boundary, not those
changes. A previous-generation fallback can also predate the newest preparation;
read the visible recovered-generation notice before deciding how to continue.
The acceptance driver saves twice after preparation so both generations contain
its chosen equipment. Ordinary users need only one confirmed save; the previous
generation intentionally remains a recovery alternative.

The strict native DTO keeps its `/1` structure and extends the audited item list
with Hand Axe/20 and Vulnerary/3, including selected weapon eligibility. Exact
native recapture verifies all item instances, uses, equipment and convoys before
restored hosts listen. The native rules manifest now also includes
`preparation.py`. **Phase 5B saves are incompatible with these changed campaign
rules.** Preserve them and use their matching Phase 5B checkout to finish them,
or start a new Phase 5C campaign in a new folder such as
`artifacts/campaign-5c`. No migration or bypass exists. Both incompatible
committed files cause restore/save refusal; fresh saves never overwrite them.

## Reproduce gameplay acceptance

```powershell
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_preparation -q
.venv\Scripts\python.exe -u utilities/smoke_network.py --preparation
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --preparation
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --preparation --tls --recovery corrupt
```

The scripted clients use the actual verified model/command path and independent
pygame renderers. Both captains use a Vulnerary in Chapter 1. At intermission
both armies equip a Hand Axe, store the Iron Axe, store Heal and take Mend, then
confirm two saved generations. The campaign completes uninterrupted, or all
three processes exit and a new host/two new clients restore and finish Chapter 2.
Full histories match within each session; native reconstruction and public
inventories/equipment/convoys/RNG match across restart. The driver checks capped
personal healing, charge consumption/action completion, unique references and
Mend heals exceeding Heal's native capacity. A controlled Chapter 2 test proves
Hand Axe distance-two targeting/real durability use where Iron Axe cannot target.
Exact executed results are recorded in [TESTING.md](TESTING.md).

Two-human usability and actual separate-PC/WAN acceptance remain unverified.
No shops, recruitment, promotion, loot generation, cross-army trading, general
storage system, extra chapters or mid-map saves are included.
