# Cooperative progression - Phase 4A

Core combat progression is implemented for both opted-in human armies. Campaign
persistence, promotions, recruitment, trading and full tactical parity remain
future work. Separate-PC Internet play remains unverified.

## Implemented rules and engine boundary

`human_control.is_human_team` identifies participation independently of the
active phase. `SimpleCombat.handle_exp` uses it for attacker and defender XP;
`handle_mana` uses it to select the existing player mana queue. A human defender
remains eligible during Red's phase. `unit_funcs.get_leveling_method` chooses the
configured player growth method for both armies. Without `_human_teams`, only
Blue qualifies, preserving ordinary single-player behavior. Red retains enemy
growth selection and does not receive player combat XP.

No reward formula, threshold or stat algorithm was replaced:

- Existing item playback and XP components determine damage/kill/miss rewards,
  minimum XP, level differences and skill multipliers. An unarmed defender still
  receives the same zero XP that Blue previously received. A miss with the normal
  axe follows the existing minimum-XP rule; no artificial participation bonus.
- `SimpleCombat` retains its per-combat XP bounds; `exp_funcs` and `ExpState`
  retain the 100-XP threshold, level/stat caps, legitimate growth actions, records
  and level-up events. Repeated combats can grant successive levels; a combat's
  existing maximum award remains 100. No new multi-level reward mechanism.
- Fixed, random and dynamic player growth selection is verified through real
  combat. Random/dynamic rolls derive from LT's unit-ID/internal-level/host-seed
  generator; different unit IDs can legitimately gain different stats. An
  unchanged global growth-stream state is expected for those local generators.
- Weapon XP already used a team-neutral path; it remains unchanged, including
  fractional skill multipliers. Mana uses existing skill contributions and caps.
  Mana skills and equations are tested with controlled fixtures; this milestone
  does not add new mana abilities to the normal training roster.
- Level-up maximum-HP growth follows LT's existing current-HP rules; it is not a
  new heal. Native presentation/roster/recruitment team checks were not broadly
  replaced. Map/animation combat inherit the reward methods, but a separate
  two-human native animation playtest was not performed.

The host alone executes rewards, growth RNG and stat actions. Read-only snapshot
differences provide result text and the client growth panel. Clients never roll
stats or submit rewards. Snapshots already contained XP/levels/stats/HP/max HP,
durability and all recorded RNG streams. **Protocol v4** carries healing choices alongside
mana/max mana and weapon-XP decimal strings, preserving fractional engine values
without JSON float payloads. Unknown command fields and old v1/v2/v3 peers reject.
Update host and both clients together; see [NETWORK_PROTOCOL.md](NETWORK_PROTOCOL.md).

## Separate original growth drill

The canonical training map and shipped projects are unchanged. The optional
`coop_progression/v1` drill clones the in-memory original training level. It uses:

- Blue Captain at `(9,3)`, Green Captain at `(9,5)`, each beginning level 1/95 XP.
- A separate human class with **40 starting HP**, other training bases unchanged,
  and inherited Fighter growth rates (including HP 85%, Strength 55%). Guards use
  that class too. This declared fixture HP gives time to inspect both captains
  after the first AI round; it is not a campaign default or a new combat formula.
- Red 1/2 at their normal adjacent positions; Red 3 begins at `(14,9)` and uses
  ordinary Pursue AI. Terrain, weapons and shared objectives are reused.
- Fixed growth by default, so the first level grants HP +1 and STR +1 to both.
  Only the **initial** 95 XP is fixture setup; subsequent XP, levels and stats
  are awarded through the real LT combat/level-up pipeline.

From the repository root, in three PowerShell terminals:

```powershell
.venv\Scripts\python.exe run_network.py host --scenario progression --seed 0
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Wait for HOST_READY. Each client initially selects its own living captain for
inspection. Click another unit to inspect it. Both must connect to act.

1. Blue Captain attacks adjacent Red 1. Expect level **2**, XP **5**, maximum HP
   **41**, STR **8**. The result and growth panel identify XP +10, LEVEL UP,
   HP +1 and STR +1. Current HP reflects the actual counterattack.
2. Select Blue Guard and press W, then E to pass to Green.
3. Green Captain attacks adjacent Red 2. Expect the same level/XP/max-HP/STR result.
   Wait Green Guard, then E to resolve Red AI and reach Blue turn 2.
4. Inspect both clients: HP, XP, levels, stats, uses, revision and Check must agree
   for each unit. Defense rewards can change XP during Red's phase. Blue can
   attack again using its grown Strength, or E to reach Green turn 2.
5. Press R: no extra rewards or levels should appear. Close and reopen Green using
   the same private invitation; its updated progression is restored. Do not
   replay an action whose outcome is unknown.

Following steps 1-3 and ending Blue turn 2 without another action gives the
three-process smoke baseline: **revision 7**, eight snapshots, Green turn 2.
Growth history stays visible after later commands, and selection shows level,
XP, important stats, current/max HP, mana, weapon XP and durability.

Host-only `--growth-method Random` or `--growth-method Dynamic` selects those LT
player methods for a fresh session; expected stat gains can differ by unit ID.
Default `host` still launches normal training with its original HP/XP/positions.
For private TLS, use the [Windows Internet procedure](INTERNET_PLAY.md) and add
`--scenario progression --seed 0` to the TLS host command. Invitations stay private.

## Reproduce automated evidence

```powershell
.venv\Scripts\python.exe utilities/audit_campaign_readiness.py
.venv\Scripts\python.exe -m unittest app.tests.test_coop_progression -q
.venv\Scripts\python.exe utilities/smoke_network.py --tls --progression
```

The audit originally showed Blue 10/Green 0 XP; after the fix both receive 10,
with identical HP and durability changes. Its save/roster findings still apply:
progression is live and characters remain nonpersistent.

The new suite has 16 tests, including real controlled solver hit/miss scripts,
actual network commands and three independent graphical processes. Controlled
fixtures set initial XP, HP, caps, skills or phase where needed; none patches the
XP/growth calculation or substitutes fake stat actions. A real second attack
verifies the grown Strength deals one extra damage. Socket tests compare full
host/client packets, exercise duplicate/resync/rejoin, forged reward fields and
v1 rejection. The final combined run passed **143 tests in 140.583 seconds**;
exact commands and post-layout checks are in [TESTING.md](TESTING.md).

No full repository-suite, manual two-human mouse play, separate-PC progression,
WAN session, campaign checkpoint or promotion result is claimed. Custom event
prompts/skills and other growth modes are not comprehensively covered by this
milestone; unsupported network prompts retain the existing fault boundary.
