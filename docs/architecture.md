# Architecture

The tracker is a single stdlib Python script (`usage.py`) plus two macOS
LaunchAgents that run it on a schedule. It has two largely independent jobs:

1. **Token/cost accounting** — how much you used, from Claude Code's transcripts.
2. **Subscription-limit tracking** — how close to the plan's caps you are, from the
   Claude CLI's `/usage` readout.

## 1. Token/cost pipeline

```
~/.claude/projects/**/*.jsonl                 (Claude Code transcripts)
        │  parse each assistant message's usage block
        ▼
per-message: {model, tokens in/out/cache, timestamp, message.id}
        │  de-duplicate by message.id
        ▼
bucket into ISO week (YYYY-Www, Monday-based)
        │  attribute to the account active at that timestamp
        ▼
aggregate per (week, account, model) cell
        │  MAX-merge into the persistent archive
        ▼
~/.claude-usage-archive/weekly.json           (append-only, never pruned)
```

Key properties:

- **Retention-proof.** Claude Code deletes transcripts after `cleanupPeriodDays`
  (default 30). The archive snapshots aggregates before they age out, so history
  accumulates for as long as the scanner keeps running.
- **Monotonic merge.** Each cell is max-merged: while a week is still in the logs its
  value grows; once the logs age out the last value is frozen. History never shrinks.
- **Account attribution.** Transcripts carry no account identity. The only signal is
  `~/.claude.json → oauthAccount`, which is the *currently* logged-in account, so each
  run records the active account into the timeline and messages are attributed by
  timestamp. Consequence: **all history before the first run collapses onto whichever
  account is active on that first run** — it genuinely cannot be split after the fact.
- **Cost is API-equivalent.** Estimated from a price table in `usage.py`. On a
  subscription this is *what the usage would cost at API list prices* — a proxy for how
  hard you lean on the plan, not a real bill.

## 2. Subscription-limit pipeline

Every sample runs `claude -p /usage` and records the session %, weekly %, and
per-model weekly %, each with the provider's reported reset time, into
`limit_samples.jsonl` (a time series). From that series two views are derived.

### Cycle segmentation on *detected* resets

The reported `weekly_resets` timestamp cannot be trusted to delimit weekly cycles:
the provider restarts the weekly window on its own schedule, and the archive holds
windows that were zeroed mid-cycle with the reported reset time unchanged.

Instead, cycles are split on resets **inferred from the readings**. A weekly reading
only ever accrues within its window, so a *fall* means the window restarted — but a
small dip is noise (one account drifted 14% → 12% across four days on an unchanged
window), so a drop counts as a reset only if it is **≥3 points or lands on zero**.

### Daily burn rate

For each local day, the tracker sums the *positive* deltas in weekly utilisation and
multiplies by 7:

```
daily_burn% = (Σ positive Δ weekly% within the day) × 7
```

100% means the day spent exactly one seventh of the weekly budget — dead on pace;
above 100% is overspending. Summing deltas (rather than `today's peak − yesterday's
peak`) is what makes a mid-day reset produce the correct positive figure instead of a
large negative one. The average is taken over the **calendar days spanned**, not only
the days that happened to be sampled; the current day is excluded as partial.

## Scheduling

`install.sh` deploys `usage.py` to `~/.claude-usage-archive/` and installs two
LaunchAgents:

- **scan** (daily) — full transcript scan + merge, and a `--export-dir` snapshot of
  the human-readable outputs.
- **account** (every 30 min) — samples the active account and a live limit reading, so
  account switches and limit changes are captured between full scans.

The deployed copy under `~/.claude-usage-archive/` is the **runtime**; this repository
is the **source of truth**. `install.sh` copies the source over the runtime.
