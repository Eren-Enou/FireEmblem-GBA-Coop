# Phase 4B: cooperative healing

The `healing` scenario supports Blue-to-Blue, Green-to-Green, Blue-to-Green and
Green-to-Blue healing through native Lex Talionis Heal/Mend spell combat. The
host validates the acting army, phase, action state, actual item instance,
class/rank/availability/charges, range and live wounded allied target before
starting native combat. Rejections leave state and RNG unchanged. Healing never
transfers unit ownership. Both peers must use protocol v5.

## Launch and play

From the repository root, use three terminals:

```powershell
.venv\Scripts\python.exe run_network.py host --scenario healing --seed 0
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Each client command belongs in its own terminal. Use the invitation paths printed
by the host if different. For TLS, follow [INTERNET_PLAY.md](INTERNET_PLAY.md) and
add `--scenario healing --seed 0` to the host command; retain certificate checks.

During your army's phase, click its healer, select the Heal inventory row (or
press its number key), then click a mint-outlined ally. Orange outlines are
attack targets. Clicking another unit without a legal selected-item action
inspects it. The selected inventory marker, HP, uses, level/XP, stats, weapon XP
and result/level-up notices show the authoritative outcome. Legal movement may
precede healing; healing finishes the healer's action.

Initially Blue's healer can support either frontline captain; Green's healer
can support Blue's captain. Assign cross-army support so both fronts receive
care. For same-army demonstrations, move Blue's healer to `(6, 2)` or Green's
healer to `(6, 4)` when available (zero-based map coordinates).

The first Heal restores a captain from 16 to 27 HP, consumes one of 30 uses,
awards 11 native XP and 2 Staff weapon XP, and raises the healer from level 1/95
XP to level 2/6 XP. Healing caps at target max HP. Native Mend requires Staff D
(31 weapon XP in this database), starts with 20 uses, heals MAG + 20 and awards
12 XP; automated tests exercise it, while the encounter starts with Heal.

## Encounter and completion

`app/coop/healing_demo.py` creates a separate in-memory original encounter,
**Two Banners: Mutual Aid**. It clones the procedural training map and adds walls
at `(7, 4)` and `(7, 6)`, leaving two choke points. Each army has a frontline
fighter and a native Cleric. Frontline class bases declare HP 36/DEF 7 and units
start wounded at 16 HP. Clerics retain HP 18/MAG 1 and start at 95 XP to expose
real support leveling. Three Red fighters pursue using normal AI. Training,
the progression drill and shipped project files are unchanged.

The existing rout and army-elimination events determine victory/defeat. There
is no scripted win shortcut. The seed-0 automated full battle wins on turn 3,
revision 18, with six real heals: support the opposite army's captain each phase,
hold the fronts on turn 1, then attack the weakest legal adjacent Red target on
turns 2/3 before ending phases. Enemy names may swap lanes. These are tested
tactics for this seed and action order, not a guarantee for arbitrary play.
Holding choke points protects healers; advancing exposes them. Healing spends
an action and limited charges, so support allocation matters.

## Verification and scope

See [TESTING.md](TESTING.md) for commands and recorded results. Tests cover same-
and cross-army support, HP caps, real XP/levels/durability, rank and action rules,
illegal targets/items, forged fields, duplicate/stale commands, full snapshot
equality, rejoin without replay, subsequent combat and complete shared victory.
The three-process smoke performs cross-army support in both directions, Red AI
and later combat. Its final explicit TLS run compared 13 identical snapshots.

Only single-target native Heal/Mend are exposed. There is no generic item-use
tunnel, trading, recruitment, promotion, cooperative save/load or matchmaking.
Custom scripted item prompts and other staves are outside this adapter's scope.
Unexpected engine faults retain the existing terminal-session policy. Separate-
PC/WAN and two-human mouse exploration remain unverified. Local evidence does
not establish Internet reachability or asset redistribution rights.

Recommended next gameplay milestone: narrowly validated personal consumables
(starting with Vulnerary), with item/action previews and the same authority,
recovery and real-engine regression checks.
