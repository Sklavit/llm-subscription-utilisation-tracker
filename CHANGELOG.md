# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Standalone repository scaffolding: `LICENSE` (MIT), `CHANGELOG.md`,
  `CONTRIBUTING.md`, `.editorconfig`, and a `docs/` set (architecture, data model).
- `pyproject.toml` — installable via `pip`/`uv` with a `claude-usage-tracker`
  console entry point (still zero runtime dependencies).
- Configurable data locations via the `CLAUDE_USAGE_ARCHIVE` and
  `CLAUDE_PROJECTS_DIR` environment variables (defaults unchanged).
- **Daily burn** view — the share of the weekly limit spent each local day, ×7, so
  100% is the break-even pace and overspending is visible without waiting for the
  week to close.

### Changed
- Rewrote `README.md` as a standalone-project readme: removed vault-era framing and
  hardcoded personal paths, generic clone/install instructions, and moved the
  `launchd` cheat-sheet into `docs/launchd.md`. Repointed the stale source path in the
  `claude-usage` skill to this repo.
- Weekly cycles are now segmented on **resets detected in the readings**, not on the
  reported reset timestamp, which the provider moves on its own schedule. A fall in
  weekly utilisation of ≥3 points (or to zero) is treated as a window reset.
- Extracted from the `personal_notes` vault into its own repository; the generated
  `data/` snapshots (which embed account emails/UUIDs) were purged from history and
  are now git-ignored.

## [0.1.0] — 2026-06-29

### Added
- Initial usage tracker: parses `~/.claude/projects/**/*.jsonl`, aggregates token
  usage and estimated (API-equivalent) cost per ISO week × account × model, and
  max-merges into a persistent archive that outlives Claude Code's transcript
  retention window.
- Account attribution via `~/.claude.json → oauthAccount`, sampled into an
  account-activity timeline.
- Live subscription-limit sampling from the Claude CLI (`/usage`), stored as a time
  series in `limit_samples.jsonl`.
- `install.sh` / `uninstall.sh` and LaunchAgents for scheduled scanning and account
  sampling on macOS.

[Unreleased]: https://github.com/Sklavit/llm-subscription-utilisation-tracker/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Sklavit/llm-subscription-utilisation-tracker/releases/tag/v0.1.0
