# Claude Code Weekly Usage Tracker

A persistent, append-only archive of Claude Code token usage and estimated
(API-equivalent) cost, broken down **per ISO week × account × model**.

## Why this exists

Claude Code stores per-session transcripts under `~/.claude/projects/**/*.jsonl`
and **deletes them after `cleanupPeriodDays`** (default 30 days). Tools like
`ccusage` and CodexBar only read what is still on disk, so they can never show
more than that retention window — that's why `ccusage claude monthly` only showed
the last ~2 months.

This tracker reads the same transcripts but **snapshots the aggregates into its own
archive that is never pruned**, so usable history accumulates for as long as you
keep running it. Combined with raising `cleanupPeriodDays` to `365`, you get a year
of raw logs *and* an archive that outlives them.

## What it produces

Everything lives in `~/.claude-usage-archive/`:

| File | Purpose |
|------|---------|
| `track.py` | the tracker (installed copy) |
| `weekly.json` | the durable archive — per week × account × model token sums. **Never shrinks.** |
| `account_timeline.json` | timestamped record of which account was active; drives the per-account split |
| `scan.log` / `account.log` | output of the scheduled LaunchAgents |

## How it works

1. **Source** — parses every `~/.claude/projects/**/*.jsonl`, taking each assistant
   message's `usage` block (input / output / cache-read / cache-write tokens, model,
   timestamp). Messages are de-duplicated by API `message.id`.
2. **Weeks** — each message is bucketed into its ISO week (`YYYY-Www`, Monday-based).
3. **Accounts** — transcripts contain **no account identity**. The only source is
   `~/.claude.json → oauthAccount.emailAddress`, which is the *currently* logged-in
   account. So each run records the active account into `account_timeline.json`, and
   every message is attributed to whichever account was active at its timestamp.
   - ⚠️ All history *before the first run* collapses onto whatever account is active
     on that first run. Past usage genuinely cannot be split — the data isn't there.
   - Switches *after* setup are captured (the account sampler runs every 30 min).
4. **Merge** — fresh aggregates are **max-merged** per `(week, account, model)` cell.
   While a week is still in the logs the value grows; once the logs age out, the last
   recorded value is frozen. History is monotonic and never lost.
5. **Cost** — estimated from a Claude price table (`PRICING` dict in `track.py`).
   You're on a subscription, so this is an **API-equivalent** figure: what the usage
   *would* cost at API list prices — a proxy for how hard you lean on the plan, not a
   real bill.

## Install

```bash
cd $HOME/personal/personal_notes/_automation/claude-usage-tracker
./install.sh
```

This copies `track.py` to `~/.claude-usage-archive/`, generates the two LaunchAgent
plists with your real home path, loads them, and runs an initial backfill.

## Scheduled jobs (LaunchAgents)

| Label | Schedule | Action |
|-------|----------|--------|
| `com.sklavit.claude-usage.scan` | daily 09:05 + on login | full scan + merge + report → `scan.log` |
| `com.sklavit.claude-usage.account` | every 30 min + on login | sample active account → timeline (cheap) |

The frequent account sampler is what makes the per-account split accurate: it notices
login switches between the daily scans.

## Manual use

```bash
/usr/bin/python3 ~/.claude-usage-archive/track.py            # scan + merge + report
/usr/bin/python3 ~/.claude-usage-archive/track.py --report   # print archive, no scan
/usr/bin/python3 ~/.claude-usage-archive/track.py --by-model # per-model breakdown
/usr/bin/python3 ~/.claude-usage-archive/track.py --csv ~/usage.csv   # export CSV
/usr/bin/python3 ~/.claude-usage-archive/track.py --record-account    # sample account only
```

Uses the stable system `/usr/bin/python3` and only the standard library — no deps.

## Maintenance notes

- **Pricing** — edit the `PRICING` dict at the top of `track.py`. Unknown models fall
  back to the `sonnet` tier and are flagged in the output (e.g. `claude-fable-5`).
- **Back up `weekly.json`** — it's the irreplaceable part. The script can rebuild
  recent weeks from logs, but weeks that have aged out only exist here.
- **Editing the script** — edit the copy in *this* folder (source of truth), then
  re-run `./install.sh` to deploy it to `~/.claude-usage-archive/`.

## Uninstall

```bash
./uninstall.sh          # unloads + removes LaunchAgents
./uninstall.sh --purge  # also deletes ~/.claude-usage-archive (DESTROYS history)
```

## Related config

- `~/.claude/settings.json → "cleanupPeriodDays": 365` keeps raw logs for a year so the
  archive has more to draw from.
