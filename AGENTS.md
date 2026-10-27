# Fire Emblem GBA cooperative project

Work only in this Lex Talionis checkout. Do not modify or depend on the separate
Path of Radiance project. The upstream baseline is
`3ba9bd923c82b36c0d57767a75d540f2bcdbc166` from
https://gitlab.com/rainlash/lt-maker.

The goal is two independent online clients, each owning an allied army against
shared enemy AI, followed by cooperative campaign progression. Current completed
scope is local hot-seat play: Blue -> Green -> Red AI. The next milestone is a
host-authoritative command/snapshot design and a local network proof of concept.

Read [architecture](docs/ARCHITECTURE.md), [progress](docs/PROGRESS.md),
[roadmap](docs/ROADMAP.md), [testing](docs/TESTING.md) and
[asset policy](docs/ASSET_POLICY.md) before changing the prototype. These are the
canonical project records; `docs/source/` remains upstream engine documentation.

## Repository

- The project root is this `FE-GBA-Coop` directory, with its own `.git` directory.
  The enclosing workspace has a separate empty Git repository. Run Git commands
  here; do not add this checkout to the parent as a nested repo or submodule.
- `origin`: `https://github.com/Eren-Enou/FireEmblem-GBA-Coop.git`.
- `upstream`: `https://gitlab.com/rainlash/lt-maker.git`. Keep it for engine updates.
  Verify remotes/root before configuration changes. Never push project work there.
- The local prototype milestone is `36f6552ddbc7004fdbfa7fb5e99df0907983bba3`.
- Preserve upstream history, `LICENSE.txt`, `credits.txt`, `licenses/` and original
  attribution. The engine's MIT code license does not establish asset rights.

## Architecture and conventions

- Keep ordinary single-player behavior when `_human_teams` is absent.
- Separate control ownership from team alliances and story factions.
- Extend the existing state machine, pathfinder, combat solver and AI.
- Edit `app/engine/component_system/skill_system_base.py`, never the generated
  `app/engine/skill_system.py`; regenerate with source_generator.
- Keep the original test scenario in `app/engine/coop_demo.py`. It installs only
  in memory; do not rewrite the shipped `.ltproj` projects.
- Use Python 3.12, four-space indentation, clear names and the surrounding style.
  Prefer small, focused changes with useful type hints.
- Keep co-op behavior in dedicated modules where practical. Limit engine edits
  to explicit integration points and describe them in the architecture document.
- Keep future command/transport code independent of SDL input and presentation.
  Host validation must not rely on the current local UI ownership guard.
- Add engine-harness tests for ownership and tactical behavior. Follow docs/TESTING.md
  for the targeted checks. Record actual outcomes and unresolved failures.
- Do not add networking until local acceptance checks pass; never describe
  local ownership checks as network security or synchronization.
- Do not redistribute the sample's proprietary graphics, sounds or story. The
  new terrain/token drawing code is original, but the runtime still uses the
  installed sample's UI, audio and item icons. A standalone release needs an
  asset audit and authorized replacements.
- Add synchronization/reconnection tests when those systems exist. Never describe
  hot-seat behavior as client synchronization or authentication.
- Maintain this file and the roadmap/progress/testing documents as scope changes.

## Required milestone workflow

The user authorizes committing and pushing completed, tested milestones to
GitHub. After each meaningful development milestone:

1. Verify root, branch, working tree and remotes. Fetch origin and account for
   remote changes without overwriting others' work. Preserve unrelated user
   changes. Use `codex/` for new task branches when appropriate.
2. Implement and run relevant checks from `docs/TESTING.md`. Resolve failures or
   clearly record an incomplete milestone; never claim checks that were not run.
3. Update `docs/PROGRESS.md` with behavior, successful checks, current blockers
   and next steps. Update `docs/ROADMAP.md` and `docs/TESTING.md` to match. Update
   architecture and these instructions when their content changes.
4. Review the exact staged diff and asset/credential exposure. Stage explicit
   paths. Never commit virtual environments, secrets, credentials, ROMs,
   proprietary assets, generated screenshots, saves, caches or build outputs.
   Ignore rules do not untrack existing files or erase history. New assets need
   documented redistribution rights.
5. Create a focused milestone commit and push the intended branch explicitly to
   **origin**. Do not force-push, rewrite shared/upstream history or automatically
   merge another branch. No releases/bundles until the asset audit permits them.
6. Verify the remote branch points at the committed revision; report its link,
   tests and limitations. If push fails, record the actual failure and report
   that the commit remains local. Never claim an unsuccessful push succeeded.
