# Chapter-boundary campaign recovery (Phases 5B and 5C)

The host automatically checkpoints **Chapter 1's settled intermission** before
end-chapter cleanup. Both friends can close all processes and return later.
Recovery starts a fresh host at that intermission with new invitations; both
commanders Ready to load Chapter 2. Native cleanup/recovery hooks run once on
that continuation, not while capturing the checkpoint.

This format supports the original Two Banners campaign's nonterminal boundary,
not mid-map Chapter 1/2 saves or a final-victory archive. It supports own-party preparation; it does not add cross-army trading,
recruitment, promotion, deployment menus, migrations or live-session loading.

## Phase 5C compatibility and preparation

Read [PREPARATION.md](PREPARATION.md) for controls and the exact five-item scope.
Each preparation mutation marks the boundary **dirty / UNSAVED**, clears both
Ready votes, and blocks continuation until S confirms saving. The previous
checkpoint remains valid if the host closes with dirty changes; they are lost
on that restart. Save errors stay visible and also block Ready.

The `/1` DTO structure is retained with an expanded trusted item list. Native
rules changed, including the campaign's starting resources and preparation
adapter. The conservative manifest therefore **rejects Phase 5B checkpoints**.
Keep old saves untouched with their matching engine checkout, or start a new
Phase 5C campaign using `--checkpoint-dir artifacts/campaign-5c`. There is no
migration/bypass; incompatible existing generations are never overwritten.
The compatibility manifest includes `preparation.py` as native rules.

## Save, close and return

Start a new campaign in one terminal, then the two clients in separate terminals:

```powershell
.venv\Scripts\python.exe run_network.py host --scenario campaign --seed 0 --checkpoint-dir artifacts/campaign-checkpoints
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Complete The First Alliance normally. The intermission and host console report
**Checkpoint saved; safe to close the host** only after the store returns from
its file commit. S explicitly saves another generation or retries a failure.
Clients cannot choose filenames, replacement state, events or a load operation.
If saving fails, the intermission shows the error and Ready remains blocked.
Resolve the host directory/permission problem and press S again. A failed save
may have committed a generation before its final acknowledgement; recovery
always validates the actual files instead of assuming the last attempt failed
completely. Never delete generations merely because an acknowledgement failed.

Close both clients and stop the host (Ctrl+C in its terminal). Later:

```powershell
.venv\Scripts\python.exe run_network.py host --restore artifacts/campaign-checkpoints
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/blue.json
.venv\Scripts\python.exe run_network.py client --session-file artifacts/network/green.json
```

Wait for the new `HOST_READY` before opening the newly written invitation files.
The saved campaign, seed and growth settings are authoritative; do not supply
`--seed`, `--growth-method` or a different scenario with `--restore`. The default
save directory for a campaign host is `artifacts/campaign-checkpoints`; use a
different directory for a separate campaign. Use one host writer per directory.
Keep both generations when backing up or moving a checkpoint directory.

TLS works with the same certificate/name/bind options as
[INTERNET_PLAY.md](INTERNET_PLAY.md). Supply those options again on the restored
host; TLS keys and army tokens are never in a checkpoint. Redistribute the new
private invitations to the commanders. Old tokens and old-session commands
reject. All peers must update to **protocol v6**. Actual separate-PC/WAN recovery
and two-human play remain unverified.

The restored intermission retains character health and permanent state. Its
map uses trusted nominal roster positions and a fresh phase/turn display; this
is not restoration of a tactical board. Dead characters have no position.
Ready votes reset so both commanders independently consent to continuation.
Temporary Red units are absent. Both Ready votes load the trusted next chapter,
restore HP under native cleanup rules and resume Blue -> Green -> Red normally.

## Persisted native state and trust boundary

`checkpoint_native.capture` reads native registries and objects directly.
`checkpoint.py` validates a separate `coop-chapter-checkpoint/1` JSON contract.
No public client snapshot, screen, pickle, component code or arbitrary event
processor is a restoration source.

| Group | Stored and validated |
| --- | --- |
| Boundary | Campaign/version, compatibility manifest, completed chapter and trusted next chapter |
| Characters | Exactly four stable original IDs; explicit owner, tactical team, party/faction, trusted class, level/EXP, base stats, growth rates/points, cap modifiers, weapon XP, HP/mana/fatigue/guard, death, personal fields and equipment references |
| Items | Unique instance UIDs, trusted Iron Axe/Hand Axe/Heal/Mend/Vulnerary IDs, owner or convoy reference, droppable flag, remaining/starting uses; no duplicate or orphan ownership |
| Skills | Unique UIDs, trusted supported passive IDs, owner, source/type and exact supported data schema |
| Parties | Distinct Blue/Green IDs, leaders, money, bonus EXP, convoy instances and roster order |
| Campaign | Supported mode/permadeath, chapter completion event IDs and bounded native combat/progression/history records |
| Randomness | Seed, combat/growth/other stream state, native item/skill UID generators above all restored instances |

The supported passives are Strength Plus 2/5, Resistance/Defense/Speed/Skill/Luck
Plus 5 and Canto from the trusted database. Their persistent data schema is empty;
effects still come from LT. The recovery tests include a real personal Strength
Plus 2 instance and prove its derived stat bonus works after restart. Unknown
skills, component counters, compound items/auras, modified presentation fields,
custom campaign variables/support state, accessories and mutable tags/notes
reject explicitly rather than silently disappearing. Derived terrain/aura/item/
region skills are omitted and rebuilt by native level setup. The original
campaign does not award unsupported state. This is not a general LT save format.

The file is limited to 1 MiB, with exact field sets, bounded arrays/scalars,
strict booleans/integers and canonical decimal strings for native fractional
growth/weapon XP. Duplicate JSON keys, floating/nonfinite JSON numbers, unknown
versions, invalid references, impossible equipment and incompatible rules reject.
UID generators are capped at one billion to leave native allocation headroom;
generation overflow rejects before changing either committed file.
Parties/owners must match the trusted campaign manifest. A checksum detects
corruption, not an editor who changes both data and checksum; valid bounded saves
are not an anti-cheat signature scheme.

Startup validates the complete DTO and trusted catalog references before native
construction. Native `UnitObject.from_prefab` uses trusted character prefabs;
item/skill factories use trusted database components without file-supplied
component arrays. Registries and references are rebuilt, native equipment and
skills are attached, the intermission board/derived systems are initialized,
and all RNG streams/UID generators are restored. A second native capture must
equal the entire validated payload before the host listens or emits invitations.
`NATIVE_CHECKPOINT_VERIFIED` in the host log records that comparison.

Restoration is constructor/startup-only in a process that has not run a previous
Simulation. There is no network Load command or in-process replacement of a live
game singleton. The native boundary does not retain transient action flags,
positions or running event/combat stacks. Historical records are reconstructed
through a fixed native record-class map, never a class name supplied by JSON.

Compatibility hashes normalized engine/rules-adapter source, checkpoint schema
and canonical project database JSON. Co-op presentation/client/transport modules are
excluded; native engine/adapter changes conservatively invalidate old saves.
Only the exact supported manifest loads; no speculative migration framework or
override bypass exists.

## File generations and recovery

`current.json` and `previous.json` contain a generation, payload and SHA-256 over
both generation and payload. Saving validates the DTO, writes a unique temporary
file in the same directory, flushes/fsyncs it, and replaces the destination with
`os.replace`. The existing verified current (or verified fallback) is rotated to
previous before replacing current. The first confirmed save also keeps a
verified mirror. A corrupt current is never copied over a good previous file.

Startup validates current first. If missing, corrupt, truncated or incompatible,
it tries previous and prints `CHECKPOINT_RECOVERY` diagnostics identifying each
rejected file; the intermission also identifies previous-generation recovery.
The selected generation is printed as `CHECKPOINT_RESTORED`. Fallback may lose
changes made after that previous valid generation. If neither is valid, startup
fails before listening or producing invitations. Preserve damaged files for
diagnosis; do not turn off validation. Existing invalid generations are not
silently overwritten by a fresh save; choose a new directory if starting over.

Orphan `.pending-*.tmp` files are ignored, never interpreted as committed saves.
Tests cover process death before current replacement, incomplete temporary
files, flush/replace exceptions, corrupt/truncated current, both generations
invalid, and an actual Windows handle denying destination replacement. These
establish tested process/file-failure recovery on this machine, not a guarantee
against every storage device or power-loss behavior. No directory fsync guarantee
or concurrent multi-host writer protocol is claimed.

## Reproduce acceptance

```powershell
.venv\Scripts\python.exe -u -m unittest app.tests.test_coop_checkpoint -q
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --tls --recovery corrupt
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --recovery truncated
.venv\Scripts\python.exe -u utilities/smoke_checkpoint.py --recovery interrupted
```

The smoke starts one host and two independent graphical clients, completes
Chapter 1 and verifies the automatic checkpoint, then exits all three processes.
It starts a new host, tests old-token/session rejection, reconnects two new
graphical clients and completes Chapter 2. Complete client histories match:
19 snapshots before shutdown and 21 after restoration, ending in revision-20
victory in the new session. Native continuity is checked before serving clients,
in addition to public field comparisons. Evidence stays ignored under
`artifacts/checkpoint-smoke/`. Exact executed results are in
[TESTING.md](TESTING.md) and [PROGRESS.md](PROGRESS.md).
