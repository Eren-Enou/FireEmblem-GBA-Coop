# Local cooperative prototype

Work only in this Lex Talionis checkout. Do not modify or depend on the separate
Path of Radiance project. The upstream baseline is
`3ba9bd923c82b36c0d57767a75d540f2bcdbc166` from
https://gitlab.com/rainlash/lt-maker.

Current scope is local hot-seat play: Blue -> Green -> Red AI. Networking and
campaign conversion require a later milestone. Read ARCHITECTURE.md, PROGRESS.md,
ROADMAP.md and TESTING.md before changing the prototype.

- Keep ordinary single-player behavior when `_human_teams` is absent.
- Separate control ownership from team alliances and story factions.
- Extend the existing state machine, pathfinder, combat solver and AI.
- Edit `app/engine/component_system/skill_system_base.py`, never the generated
  `app/engine/skill_system.py`; regenerate with source_generator.
- Keep the original test scenario in `app/engine/coop_demo.py`. It installs only
  in memory; do not rewrite the shipped `.ltproj` projects.
- Add engine-harness tests for ownership and tactical behavior. Follow TESTING.md
  for the targeted checks. Record actual outcomes and unresolved failures.
- Do not add networking until local acceptance checks pass; never describe
  local ownership checks as network security or synchronization.
- Do not redistribute the sample's proprietary graphics, sounds or story. The
  new terrain/token drawing code is original, but the runtime still uses the
  installed sample's UI, audio and item icons. A standalone release needs an
  asset audit and authorized replacements.
- Maintain this file and the roadmap/progress/testing documents as scope changes.

No subagent work is required by these instructions.
