---
name: claude-usage
description: Report, maintain, or troubleshoot the persistent Claude Code usage archive — weekly tokens + estimated cost AND % of subscription limit consumed, split per account. Use when the user asks "usage", "how much Claude have I used", "weekly usage", "usage per account", "% of my limit", "subscription utilisation", "why does ccusage/CodexBar only show recent months", "back up my usage history", or wants to change pricing/schedule of the usage tracker.
---

# Claude Code Usage Archive

A persistent, append-only weekly archive of Claude Code token usage and estimated
API-equivalent cost, split per account. The runtime archive is at
`~/.claude-usage-archive/` (override with `CLAUDE_USAGE_ARCHIVE`); the source-of-truth
project is the [llm-subscription-utilisation-tracker](https://github.com/Sklavit/llm-subscription-utilisation-tracker)
repo (cloned locally at `~/personal/llm-subscription-utilisation-tracker/`).

## Background the user usually wants

Claude Code deletes transcripts (`~/.claude/projects/**/*.jsonl`) after
`cleanupPeriodDays` (default 30). `ccusage` and CodexBar can only read what's still on
disk, so they max out at ~30 days / ~2 calendar months. This archive snapshots the
aggregates so history survives the cleanup. Raising `cleanupPeriodDays` (e.g. to 365)
gives the archive more raw logs to draw from.

## "usage" → % of subscription limit consumed

```bash
uv run ~/.claude-usage-archive/budget.py check              # report
uv run ~/.claude-usage-archive/budget.py --record-limits    # sample now
```

True % can't come from tokens (Anthropic publishes no fixed limit, stores no history).
It's sampled live every 30 min into `limit_samples.jsonl` and accrues going forward —
**not backfillable**. Primary source: `claude auth status --json` + `claude -p '/usage'`
(same credential store, so account and reading always match; includes the per-model
weekly bucket). Fallback: CodexBar CLI — its oauth path can serve a cached account, so
fallback readings are re-attributed by weekly reset anchor. Report shows peak % of the
weekly limit per weekly cycle per account, plus latest session (5h) + weekly readings.

## Read token usage / cost

```bash
uv run ~/.claude-usage-archive/budget.py report             # whole archive
uv run ~/.claude-usage-archive/budget.py report --by-model  # + per-model rows
uv run ~/.claude-usage-archive/budget.py scan --csv ~/usage.csv
```

`report` does NOT rescan. The bare command (same as `scan`) scans logs and merges
into the archive, then prints the `check` view rather than the token table.

A read-only snapshot is also mirrored into the project's `data/` folder
(`weekly.json`, `weekly.csv`, `report.txt`, `account_timeline.json`) by the daily agent
via `--export-dir`. Use those for quick reading/backup; the authoritative archive is
`~/.claude-usage-archive/weekly.json`.

## How attribution works (state honestly)

- Per-week/per-model totals come from parsing transcripts — accurate.
- Per-**account** split is best-effort: transcripts have no account field. The tracker
  samples `~/.claude.json → oauthAccount.emailAddress` every 30 min and attributes
  usage by timestamp. **History before tracking began is all on one account.** Don't
  overstate accuracy.

## Maintain

- **Pricing wrong / new model unpriced:** edit `PRICING` in the project's `budget.py`,
  then run the project's `./install.sh` to redeploy. Unknown models fall back to the
  `sonnet` tier and are flagged in output.
- **Change schedule:** edit plist generation in the project's `install.sh`, re-run it.
- **Verify agents:** `launchctl list | grep claude-usage` (last-exit col should be 0).

## Troubleshoot

- **No new data:** check `~/.claude-usage-archive/scan.log`. Confirm agents loaded
  (`launchctl list | grep claude-usage`). Re-run `scan` manually.
- **Account split looks wrong:** inspect `~/.claude-usage-archive/account_timeline.json`.
  Switches are only caught when the 30-min sampler runs while that account is active.

## Never do

- Never overwrite/delete `~/.claude-usage-archive/weekly.json` without explicit
  confirmation — aged-out weeks exist nowhere else.
- Keep the script stdlib-only (LaunchAgents run `/usr/bin/python3`; manual/interactive
  use runs it via `uv run` instead).
