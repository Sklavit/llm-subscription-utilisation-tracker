---
name: claude-usage
description: Report, maintain, or troubleshoot the persistent Claude Code weekly usage archive (tokens + estimated cost, split per account). Use when the user asks "how much Claude have I used", "weekly usage", "usage per account", "why does ccusage/CodexBar only show recent months", "back up my usage history", or wants to change pricing/schedule of the usage tracker.
---

# Claude Code Usage Archive

A persistent, append-only weekly archive of Claude Code token usage and estimated
API-equivalent cost, split per account. Located at `~/.claude-usage-archive/`; the
source-of-truth project lives at
`$HOME/personal/personal_notes/_automation/claude-usage-tracker/`.

## Background the user usually wants

Claude Code deletes transcripts (`~/.claude/projects/**/*.jsonl`) after
`cleanupPeriodDays` (default 30). `ccusage` and CodexBar can only read what's still on
disk, so they max out at ~30 days / ~2 calendar months. This archive snapshots the
aggregates so history survives the cleanup. The user has set `cleanupPeriodDays: 365`.

## Read current usage

```bash
/usr/bin/python3 ~/.claude-usage-archive/track.py --report      # whole archive
/usr/bin/python3 ~/.claude-usage-archive/track.py --by-model    # + per-model rows
/usr/bin/python3 ~/.claude-usage-archive/track.py --csv ~/usage.csv
```

`--report` does NOT rescan; the bare command (no flags) scans logs, merges, and prints.

## How attribution works (state honestly)

- Per-week/per-model totals come from parsing transcripts — accurate.
- Per-**account** split is best-effort: transcripts have no account field. The tracker
  samples `~/.claude.json → oauthAccount.emailAddress` every 30 min and attributes
  usage by timestamp. **History before tracking began is all on one account.** Don't
  overstate accuracy.

## Maintain

- **Pricing wrong / new model unpriced:** edit `PRICING` in the project's `track.py`,
  then run the project's `./install.sh` to redeploy. Unknown models fall back to the
  `sonnet` tier and are flagged in output.
- **Change schedule:** edit plist generation in the project's `install.sh`, re-run it.
- **Verify agents:** `launchctl list | grep claude-usage` (last-exit col should be 0).

## Troubleshoot

- **No new data:** check `~/.claude-usage-archive/scan.log`. Confirm agents loaded
  (`launchctl list | grep claude-usage`). Re-run the bare command manually.
- **Account split looks wrong:** inspect `~/.claude-usage-archive/account_timeline.json`.
  Switches are only caught when the 30-min sampler runs while that account is active.

## Never do

- Never overwrite/delete `~/.claude-usage-archive/weekly.json` without explicit
  confirmation — aged-out weeks exist nowhere else.
- Keep the script stdlib-only (LaunchAgents run `/usr/bin/python3`).
