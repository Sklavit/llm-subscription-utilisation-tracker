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
| `usage.py` | the tracker (installed copy) |
| `weekly.json` | the durable archive — per week × account × model token sums. **Never shrinks.** |
| `account_timeline.json` | timestamped record of which account was active; drives the per-account split |
| `scan.log` / `account.log` | output of the scheduled LaunchAgents |

## `check` — % of subscription limit consumed

> Ask for **"usage"** to see *% of your weekly limit consumed, per week, per account.*

Anthropic publishes **no fixed limit number** and stores **no history** of your
utilisation — the live % only exists behind the authenticated claude.ai endpoint
(what Claude Code's `/usage` shows). So this can't be reconstructed from tokens or
backfilled. Instead, the scheduler **samples the live % every 30 minutes** and
appends each reading to `~/.claude-usage-archive/limit_samples.jsonl`. History
accrues from now on.

Sampling sources, in order:

1. **Claude Code itself** (primary): `claude auth status --json` for the account
   identity + `claude -p '/usage'` for the live limits (session, weekly, and the
   per-model weekly bucket, e.g. Fable). Both read the same credential store, so the
   (account, reading) pair cannot diverge. Samples carry `"src": "claude-cli"`.
2. **CodexBar CLI** (fallback, `"src": "codexbar"`): kept because it worked before,
   but its `--source oauth` path may serve a *cached* account after a login switch.
   Fallback readings are therefore attributed by their **weekly reset anchor** (each
   account's weekly window advances in exact 7-day steps, so the reset time mod 7
   days is a per-account fingerprint), not by trusting the logged-in email.

Failed sampling attempts are recorded too, with an `err` field, so gaps in the
series are explainable rather than silent.

```bash
uv run ~/.claude-usage-archive/usage.py check              # the report
uv run ~/.claude-usage-archive/usage.py --record-limits    # sample now
```

It reports, per account, the **peak % of the weekly limit** reached in each weekly
cycle, plus a **daily burn** view (share of the weekly limit spent per day, ×7, so
100% is the break-even pace) and the latest live session (5-hour) and weekly
readings. Cycles are split on resets **detected in the readings**, not on the
reported reset time — the provider moves the weekly window on its own schedule, so a
fall of ≥3 points (or to zero) is treated as a reset. The active Claude Code account
is whatever's sampled; switching accounts is captured automatically over time. See
[docs/architecture.md](docs/architecture.md) for the details.

Requires the `claude` CLI (always present on this machine). CodexBar
(`brew install --cask steipete/tap/codexbar`) is optional — only used as fallback.

## Collected statistics (in this folder)

The daily scan also mirrors a snapshot into `data/` here, so the stats live in your
notes (backed up / synced) and not only in `~/.claude-usage-archive/`:

| File | Purpose |
|------|---------|
| `data/weekly.json` | full archive copy (machine-readable) |
| `data/weekly.csv` | one row per week × account × model (for spreadsheets) |
| `data/report.txt` | human-readable table with per-model breakdown + a `Generated:` stamp |
| `data/account_timeline.json` | account-activity timeline copy |
| `data/limit_samples.jsonl` | time series of live subscription-limit readings |
| `data/usage.txt` | the `% of limit consumed` report (per cycle, per account) |

This is refreshed automatically by the daily LaunchAgent (via `--export-dir`). To
refresh on demand:

```bash
uv run ~/.claude-usage-archive/usage.py scan \
  --export-dir $HOME/personal/llm-subscription-utilisation-tracker/data
```

> The `data/` copy is a snapshot for reading/backup. The **live, authoritative**
> archive that must never shrink is still `~/.claude-usage-archive/weekly.json`.

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
5. **Cost** — estimated from a Claude price table (`PRICING` dict in `usage.py`).
   You're on a subscription, so this is an **API-equivalent** figure: what the usage
   *would* cost at API list prices — a proxy for how hard you lean on the plan, not a
   real bill.

## Install

```bash
cd $HOME/personal/llm-subscription-utilisation-tracker
./install.sh
```

This copies `usage.py` to `~/.claude-usage-archive/`, generates the two LaunchAgent
plists with your real home path, loads them, and runs an initial backfill.

## Configuration

Data locations default to the paths above and can be overridden with environment
variables — no source edit needed:

| Variable | Overrides | Default |
|---|---|---|
| `CLAUDE_USAGE_ARCHIVE` | where the durable archive + limit series live | `~/.claude-usage-archive` |
| `CLAUDE_PROJECTS_DIR` | where Claude Code transcripts are read from | `~/.claude/projects` |

```bash
# Keep the archive in a synced folder instead of the home dir:
CLAUDE_USAGE_ARCHIVE=~/Sync/claude-usage uv run usage.py
```

To make it permanent for the scheduled jobs, add an `EnvironmentVariables` dict to
the LaunchAgent plists (or export the var in the LaunchAgent's environment). The
`--export-dir` flag independently controls where the human-readable snapshot is
mirrored, separate from the archive location.

> Packaging: `pyproject.toml` makes this `pip`/`uv`-installable and exposes a
> `claude-usage-tracker` console command (`pip install .` then
> `claude-usage-tracker check`). Installing is optional — `uv run usage.py` needs
> nothing.

## Scheduled jobs (LaunchAgents)

| Label | Schedule | Action |
|-------|----------|--------|
| `com.sklavit.claude-usage.scan` | daily 09:05 + on login | full scan + merge + `data/` snapshot → `scan.log` |
| `com.sklavit.claude-usage.account` | every 30 min + on login | sample active account → timeline (cheap) |

The frequent account sampler is what makes the per-account split accurate: it notices
login switches between the daily scans.

## Manual use

```bash
uv run ~/.claude-usage-archive/usage.py                      # scan + merge, then `check` view
uv run ~/.claude-usage-archive/usage.py scan                  # same as bare
uv run ~/.claude-usage-archive/usage.py check                 # % of subscription limit (no scan)
uv run ~/.claude-usage-archive/usage.py report                # token/cost archive, no scan
uv run ~/.claude-usage-archive/usage.py update                # sample account + live limit %
uv run ~/.claude-usage-archive/usage.py report --by-model     # per-model breakdown
uv run ~/.claude-usage-archive/usage.py scan --csv ~/usage.csv  # export CSV
uv run ~/.claude-usage-archive/usage.py --record-account      # sample account only
```

Actions (`scan`, `check`, `report`, `update`, `help`) are one word, no dashes; bare
invocation defaults to `scan` (collect everything, then print the `check` view — the
token/cost table lives under `report`). Options that take or toggle extra behavior
(`--by-model`, `--csv`, `--record-account`) keep dashes.

Scheduled LaunchAgents still run it via the stable system `/usr/bin/python3` (see
below); manual/interactive use goes through `uv run`. Either way it's stdlib-only —
no deps to resolve.

## Maintenance notes

- **Pricing** — edit the `PRICING` dict at the top of `usage.py`. Unknown models fall
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


---
Here are the main ways to inspect launchd jobs:

## List loaded agents

```bash
launchctl list                      # all loaded jobs
launchctl list | grep claude-usage  # just the usage tracker
```

Output is three columns: **PID** (a number if currently running, `-` if idle/waiting) · **Last exit status** (`0` = last run succeeded, nonzero = failed) · **Label**.

## Inspect one job in detail

```bash
launchctl print gui/$(id -u)/com.sklavit.claude-usage.scan
```

This is the modern, detailed view — shows state, run schedule, last exit reason, program arguments, paths, and run counts.

## Check what it actually did

For this tracker, the agents log to files:

```bash
cat ~/.claude-usage-archive/scan.log       # daily full-scan output
cat ~/.claude-usage-archive/account.log    # 30-min account sampler
```

## See the installed definitions

```bash
ls ~/Library/LaunchAgents/ | grep claude-usage
cat ~/Library/LaunchAgents/com.sklavit.claude-usage.scan.plist
```

## Force a run now (instead of waiting for the schedule)

```bash
launchctl kickstart -k gui/$(id -u)/com.sklavit.claude-usage.scan
```

## System-wide jobs

`launchctl list` (without sudo) shows your per-user agents. Daemons run in a different domain:

```bash
sudo launchctl list                 # system daemons
sudo launchctl print system/<label>
```

## Quick mental model

- `launchctl list` → "what's loaded and did it last succeed?"
- `launchctl print gui/$(id -u)/<label>` → "tell me everything about this one"
- the `.log` files → "what was the actual output?"

For your two tracker agents, the fastest health check is `launchctl list | grep claude-usage` — if the second column is `0` for both, they're running fine.
## Documentation

Deeper docs live in [`docs/`](docs/):

- [Architecture](docs/architecture.md) — the scan → merge → cost pipeline, cycle
  segmentation, and the daily burn rate.
- [Data model](docs/data-model.md) — the files the tracker maintains and their schemas.

See also [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE) © 2026 Sergii Nechuiviter
