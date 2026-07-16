# Claude Code Usage & Subscription-Limit Tracker

A persistent, append-only archive of **Claude Code** token usage and estimated
(API-equivalent) cost — broken down **per ISO week × account × model** — plus a time
series of your **subscription-limit utilisation** (session / weekly / per-model), so
you can see how hard you lean on the plan over time.

Standard-library Python, no runtime dependencies. macOS LaunchAgents keep it sampling
in the background; the core script also runs fine one-off on Linux.

## Why this exists

Claude Code stores per-session transcripts under `~/.claude/projects/**/*.jsonl` and
**deletes them after `cleanupPeriodDays`** (default 30 days). Tools like `ccusage` and
CodexBar only read what is still on disk, so they can never show more than that
retention window.

This tracker reads the same transcripts but **snapshots the aggregates into its own
archive that is never pruned**, so usable history accumulates for as long as you keep
running it. Separately, the live subscription-limit % (which the provider stores *no*
history for) is sampled on a schedule so utilisation history accrues from first run.

## Requirements

- **Python 3.10+** — run via [`uv`](https://docs.astral.sh/uv/) (`uv run budget.py`) or
  any `python3`. No third-party packages.
- **Claude Code** installed, with transcripts under `~/.claude/`.
- The **`claude` CLI** — required only for live subscription-limit sampling; token/cost
  accounting works without it.
- **macOS** for the scheduled LaunchAgents (`install.sh`). The script itself is
  cross-platform for manual use.
- Optional: **CodexBar** (`brew install --cask steipete/tap/codexbar`) as a fallback
  limit-reading source.

## Install

```bash
git clone https://github.com/Sklavit/llm-subscription-utilisation-tracker.git
cd llm-subscription-utilisation-tracker
./install.sh
```

`install.sh` deploys `budget.py` to the runtime archive (`~/.claude-usage-archive/`),
generates + loads the two LaunchAgents, and runs an initial backfill. Re-run it any
time after editing `budget.py`.

Prefer no background jobs? Skip the installer and just run the script manually (below).

## Manual use

Run from the cloned repo:

```bash
uv run budget.py                       # scan + merge, then the `check` view
uv run budget.py scan                  # same as bare
uv run budget.py check                 # % of subscription limit (no scan)
uv run budget.py report                # token/cost archive, no scan
uv run budget.py report --by-model     # per-model breakdown
uv run budget.py update                # sample account + live limit %
uv run budget.py scan --csv usage.csv  # export CSV
uv run budget.py --record-limits       # sample the live limit % now
```

Actions (`scan`, `check`, `report`, `update`, `help`) are one word, no dashes; bare
invocation defaults to `scan` (collect everything, then print the `check` view — the
token/cost table lives under `report`). Options that take or toggle extra behaviour
(`--by-model`, `--csv`, `--export-dir`, `--record-limits`) keep dashes. `python3
budget.py ...` works identically if you don't use `uv`.

The scheduled LaunchAgents run the deployed copy via the stable system
`/usr/bin/python3` (survives Homebrew upgrades); it's stdlib-only either way.

## Configuration

Data locations default to the paths below and can be overridden with environment
variables — no source edit needed:

| Variable | Overrides | Default |
|---|---|---|
| `CLAUDE_USAGE_ARCHIVE` | where the durable archive + limit series live | `~/.claude-usage-archive` |
| `CLAUDE_PROJECTS_DIR` | where Claude Code transcripts are read from | `~/.claude/projects` |

```bash
# Keep the archive in a synced folder instead of the home dir:
CLAUDE_USAGE_ARCHIVE=~/Sync/claude-usage uv run budget.py
```

For the scheduled jobs, LaunchAgents don't inherit your shell environment — add an
`EnvironmentVariables` dict to the plists to make an override permanent. The
`--export-dir` flag independently controls where a human-readable snapshot is
mirrored, separate from the archive location.

`pyproject.toml` also makes the tool `pip`/`uv`-installable with a
`claude-usage-tracker` console command (`pip install .` → `claude-usage-tracker
check`). Installing is optional — `uv run budget.py` needs nothing.

## What it produces

State lives in the archive directory (default `~/.claude-usage-archive/`):

| File | Purpose |
|---|---|
| `weekly.json` | the durable archive — per week × account × model token sums. **Never shrinks.** |
| `account_timeline.json` | timestamped record of which account was active; drives the per-account split |
| `limit_samples.jsonl` | append-only time series of live subscription-limit readings |
| `scan.log` / `account.log` | output of the scheduled LaunchAgents |

The scan can also mirror a human-readable snapshot to any directory via
`--export-dir` (the installer points it at this repo's `data/`, which is git-ignored
because the snapshots embed account emails/UUIDs):

| File | Contents |
|---|---|
| `report.txt` | per-week × account × model token/cost table with a `Generated:` stamp |
| `usage.txt` | the subscription-limit report (per cycle, per account) + daily burn |
| `weekly.csv` | `weekly.json` flattened to one row per week × account × model |
| `weekly.json` / `account_timeline.json` / `limit_samples.jsonl` | machine-readable copies |

See [docs/data-model.md](docs/data-model.md) for the schemas.

## Subscription-limit tracking (`check`)

The provider publishes **no fixed limit number** and stores **no history** of your
utilisation — the live % only exists behind the authenticated endpoint (what Claude
Code's `/usage` shows). So it can't be reconstructed from tokens or backfilled.
Instead the scheduler **samples the live % every 30 minutes** into
`limit_samples.jsonl`, and history accrues going forward.

Sampling sources, in order:

1. **Claude Code itself** (primary): `claude auth status --json` for the account
   identity + `claude -p '/usage'` for the live limits (session, weekly, and the
   per-model weekly bucket). Both read the same credential store, so the
   (account, reading) pair cannot diverge. Samples carry `"src": "claude-cli"`.
2. **CodexBar CLI** (fallback, `"src": "codexbar"`): its `--source oauth` path may
   serve a *cached* account after a login switch, so those readings are attributed by
   their **weekly reset anchor** (each account's weekly window advances in exact 7-day
   steps, so the reset time mod 7 days is a per-account fingerprint) rather than by
   trusting the logged-in email.

Failed sampling attempts are recorded too, with an `err` field, so gaps in the series
are explainable rather than silent.

`check` reports, per account, the **peak % of the weekly limit** reached in each
weekly cycle, a **daily burn** view (share of the weekly limit spent per day, ×7, so
100% is the break-even pace), and the latest live session (5-hour) and weekly
readings. Cycles are split on resets **detected in the readings**, not on the reported
reset time — the provider moves the weekly window on its own schedule, so a fall of ≥3
points (or to zero) is treated as a reset. See
[docs/architecture.md](docs/architecture.md) for the details.

## How it works

1. **Source** — parses every `~/.claude/projects/**/*.jsonl`, taking each assistant
   message's `usage` block (input / output / cache-read / cache-write tokens, model,
   timestamp). Messages are de-duplicated by API `message.id`.
2. **Weeks** — each message is bucketed into its ISO week (`YYYY-Www`, Monday-based).
3. **Accounts** — transcripts contain **no account identity**. The only source is
   `~/.claude.json → oauthAccount`, the *currently* logged-in account, so each run
   records the active account into `account_timeline.json` and messages are attributed
   by timestamp.
   - ⚠️ All history *before the first run* collapses onto whatever account is active on
     that first run — past usage genuinely cannot be split.
   - Switches *after* setup are captured (the account sampler runs every 30 min).
4. **Merge** — fresh aggregates are **max-merged** per `(week, account, model)` cell.
   While a week is still in the logs the value grows; once the logs age out the last
   recorded value is frozen. History is monotonic and never lost.
5. **Cost** — estimated from a price table (`PRICING` dict in `budget.py`). On a
   subscription this is an **API-equivalent** figure: what the usage *would* cost at
   API list prices — a proxy for how hard you lean on the plan, not a real bill.

## Scheduled jobs (LaunchAgents)

| Label | Schedule | Action |
|---|---|---|
| `com.<user>.claude-usage.scan` | daily 09:05 + on login | full scan + merge + snapshot export → `scan.log` |
| `com.<user>.claude-usage.account` | every 30 min + on login | sample active account + live limit % → `account.log` |

The frequent sampler is what keeps the per-account split accurate: it notices login
switches between the daily scans. For inspecting and debugging the agents, see
[docs/launchd.md](docs/launchd.md).

## Maintenance

- **Pricing** — edit the `PRICING` dict at the top of `budget.py`. Unknown models fall
  back to the `sonnet` tier and are flagged in the output.
- **Back up `weekly.json`** — it's the irreplaceable part. The script can rebuild
  recent weeks from logs, but weeks that have aged out only exist there.
- **Editing the script** — edit `budget.py` in the repo (source of truth), then re-run
  `./install.sh` to redeploy it to the archive directory.
- **Retention** — set `~/.claude/settings.json → "cleanupPeriodDays": 365` to keep raw
  logs for a year, giving the archive more to draw from.

## Uninstall

```bash
./uninstall.sh          # unload + remove the LaunchAgents
./uninstall.sh --purge  # also delete the archive directory (DESTROYS history)
```

## Documentation

- [Architecture](docs/architecture.md) — the scan → merge → cost pipeline, cycle
  segmentation, and the daily burn rate.
- [Data model](docs/data-model.md) — the files the tracker maintains and their schemas.
- [launchd](docs/launchd.md) — inspecting and debugging the scheduled jobs.

See also [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE) © 2026 Sergii Nechuiviter
