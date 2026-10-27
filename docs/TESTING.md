# Environment and verification

Run commands from `FE-GBA-Coop`, not the parent repository. Verified on Windows
with Python 3.12.6, pygame-ce 2.5.7, PyQt5 5.15.10, Qt 5.15.2 and PyQt5_sip
12.20.0. Existing `.venv` is ignored, not part of the deliverable.

## Recreate

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements_editor.txt
.venv\Scripts\python.exe -c "from app.engine.codegen import source_generator; source_generator.generate_all()"
```

The current requirements also install PyInstaller 6.2.0; packaging is not part of
this milestone. The checks below use built-in unittest and do not need pytest or
the optional Pillow tests. Keep the source checkout's sample projects/resources.

## Play the prototype

```powershell
.venv\Scripts\python.exe run_coop.py
```

Blue acts first; use arrow keys and X to select a unit, select its destination,
then choose Attack or Wait. Z cancels, A cycles available units. Select an empty
tile to open the map menu and choose End to hand control to Green, then Red AI.
Bindings follow the existing `saves/config.ini`; these are the engine defaults.
Green units cannot be commanded during Blue's phase and vice versa. Hold S during
Red's phase to speed through AI presentation. Eliminate all Red units to win;
losing either entire human army loses the shared map.

This is one-machine hot-seat play. Save/suspend and turnwheel are omitted from
this demo. Closing and launching again starts a fresh scenario. Do not package
the sample's assets for distribution.

## Automated checks

```powershell
.venv\Scripts\python.exe -m unittest app.tests.test_local_coop app.tests.test_ai_blocked_path_fallback app.tests.test_secondary_ai_blocked_path app.tests.test_move_selection_lifecycle app.tests.test_canto_movement app.tests.test_save_round_trip -q
```

The local tests load the supported default project, install the original demo,
and drive the real state machine with SDL button events. The harness fixes the
random seed to 0, uses dummy SDL video/audio, and shortens phase banners. It does
not replace combat/pathfinding/AI with mocks; the ownership test deliberately
mocks a permissive selection skill to exercise the independent ownership guard.

Coverage includes faction rejection, movement/Wait for both armies, blocked or
out-of-range destinations, occupied allied tiles, real HP and durability changes,
AI target choice for either army, AUX cycling, manual/automatic phase handoff,
round accounting, shared victory/defeat, default control fallback, and removal
of unsupported demo saves. Existing movement, AI and save tests check regressions.
Networking/synchronization tests will be added with Phase 2, not simulated here.

## Actual driver/editor smoke checks

```powershell
.venv\Scripts\python.exe run_coop.py --smoke
.venv\Scripts\python.exe utilities\smoke_editor.py
```

The first renders a full Blue -> Green -> Red AI -> Blue round through MainLoop,
with normal banner timing, saves Blue/Green PNGs under `artifacts/`, and asserts
turn 2 was reached. It exits on success with `COOP_SMOKE_OK`. It advances phases
programmatically; tactical command verification comes from the harness tests.

The editor check opens/renders a disposable copy of `default.ltproj` and exits
with `EDITOR_SMOKE_OK`. It leaves the original project unchanged and does not
change the saved current-project/recent-project settings. It needs a Windows
desktop. This is a launch/render check, not exhaustive editor validation.

The older `testing_proj.ltproj` has v0 metadata and a missing `lmaoooo.png`
portrait. Opening it through the editor's migration path fails; existing engine
tests load it as a fixture at the current serialization version. Use the
supported `default.ltproj` for editor use and the co-op launcher. Do not mark the
old fixture migrated or silently replace its missing art.

Test results and remaining limitations are recorded in PROGRESS.md.

## Latest verification — October 27, 2026

The repository-maintenance milestone changed documentation and ignore rules only.
Code generation followed by the automated command above passed **73 tests in
28.443 seconds** on the existing Windows/Python 3.12.6 environment. The original
prototype's driver and editor smoke checks passed earlier on the same date;
they were not repeated for this documentation change. Full-suite, networking and
internet behavior remain untested.

Publication validation also passed: 8 staged Markdown/ignore files including
renames, 20 resolving project-document links, a clean staged whitespace check,
no matching credential signatures, no tracked private/local output paths and
unchanged original license/credits. This does not clear inherited assets or
constitute a full historical secret scan.

## Milestone publication procedure

Run from the actual project checkout, which has its own `.git` directory:

```powershell
git rev-parse --show-toplevel
git remote -v
git fetch origin
git status --short
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git ls-files .venv artifacts local_assets private_assets
git check-ignore .venv/probe artifacts/probe.png .env local_assets/probe.png private_assets/probe.png example.gba example.iso example.ciso
```

Expected remotes: GitHub `Eren-Enou/FireEmblem-GBA-Coop` as `origin`, rainlash's
GitLab `lt-maker` as `upstream`. The tracked-local-files command should print
nothing; check-ignore should list every probe path. The probes need not exist.

Review the staged content as well as filenames for credentials and proprietary
content. For this maintenance milestone, only Markdown and `.gitignore` may be
staged; no runtime source, license/credits changes, media, ROMs or local artifacts.
Check the authored Markdown's local links resolve after moving files to `docs/`.
These checks cover the new staged change, not a full historical licensing or
secret audit. See [asset policy](ASSET_POLICY.md).

After relevant tests and documentation are complete, commit explicit reviewed
paths and push the intended branch to origin. For the current main branch:

```powershell
git push origin HEAD:main
git rev-parse HEAD
git ls-remote origin refs/heads/main
git status --short
```

The two commit hashes must match. Do not force-push or claim success without
remote verification. Record actual failures if publishing is blocked. Subsequent
task branches should use their own explicit destination instead of `main`.
