# Licensing, attribution and publication boundaries

The original Lex Talionis engine is by rainlash and contributors. Preserve its
[MIT license](../LICENSE.txt), [credits](../credits.txt), and third-party notices
in [licenses](../licenses/). Preserve upstream history and keep
`https://gitlab.com/rainlash/lt-maker.git` as the `upstream` Git remote.

The engine's code license does not establish rights to every sample image,
sound, font, map or story. The inherited repository includes sample game assets;
their presence on GitHub is not a redistribution permission. A complete asset
audit is outstanding. No standalone release or asset bundle is authorized by
the current milestone.

The existing local prototype commit adds code and documentation, including
procedurally drawn terrain/tokens. It does not add binary art or sound files.
The demo still loads the installed default project's UI, sounds and item icons;
it is not an independently cleared game distribution.

## Rules for new commits

- Do not add Nintendo ROMs, extracted game files, proprietary sprites/music,
  copied campaign content, credentials or virtual environments.
- Store untracked private development materials under `private_assets/` or
  `local_assets/` if needed. Both are ignored. Never reference a private asset as
  a required public build dependency.
- Ignore local screenshots, saves, logs, caches and builds. Inspect staged paths
  and file content before each commit; `.gitignore` is only a first defense.
- Before adding an asset, record its source, creator, license, attribution and
  redistribution permission here or in a dedicated asset manifest. If those
  rights are unresolved, keep it out of Git.
- Do not assume code's MIT terms cover artwork or remove existing notices.

## Current repository audit boundary

On October 27, 2026 the local prototype changes relative to engine baseline
`3ba9bd923c82b36c0d57767a75d540f2bcdbc166` consisted of Python, Markdown and
`.gitignore` changes. The default sample alone has 1,668 inherited tracked
resource files. These were already present in upstream history and GitHub's
existing `main`; this maintenance milestone does not add, clear or relicense
them. Removing them from a future distribution requires an asset-by-asset audit.
Removing them from shared history would require a separately planned history
migration; do not force-push or silently rewrite that history.

The maintenance milestone must contain documentation and ignore rules only.
Its staged-file audit does not constitute a full historical secret or licensing
audit. See [progress](PROGRESS.md) for the actual validation results.
