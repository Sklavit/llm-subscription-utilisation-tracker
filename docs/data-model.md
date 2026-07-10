# Data model

All state lives under the runtime archive `~/.claude-usage-archive/` (override with
the `CLAUDE_USAGE_ARCHIVE` env var). A read-only snapshot of the human-facing files
is mirrored into this repo's `data/` via `--export-dir` — but that directory is
**git-ignored** because these files embed account emails and UUIDs.

> The authoritative, must-never-shrink archive is
> `~/.claude-usage-archive/weekly.json`. The `data/` copy is for reading and backup.

## `weekly.json` — the persistent token/cost archive

Nested `week → account → model → cell`. Each cell holds token counts and activity for
that `(week, account, model)`:

```json
{
  "2026-W28": {
    "you@example.com": {
      "claude-opus-4-8": {
        "in": 82163,          // input tokens
        "out": 213333,        // output tokens
        "cache_read": 24206684,
        "cache_5m": 108554,   // 5-minute cache writes
        "cache_1h": 1239487,  // 1-hour cache writes
        "messages": 264,
        "sessions": 6
      }
    }
  }
}
```

Cells are **max-merged** on each scan, so values are monotonic non-decreasing.

## `limit_samples.jsonl` — live subscription-limit time series

One JSON object per line, appended on each sample. Fields:

| Field | Meaning |
|---|---|
| `t` | ISO-8601 timestamp of the sample |
| `iso_week` | ISO week the sample falls in |
| `email` | account the reading is attributed to |
| `src` | reading source (`claude-cli`, `codexbar`, …) |
| `plan` | subscription plan string (e.g. `Claude Pro`) |
| `session_pct` / `session_resets` | 5-hour session usage % and its reset time |
| `weekly_pct` / `weekly_resets` | weekly usage % and the *reported* reset time |
| `model_week` | model the weekly per-model cap applies to |
| `model_weekly_pct` / `model_weekly_resets` | per-model weekly usage % and reset time |

Failed readings are recorded too (with an `err` field) so gaps in the series are
explainable rather than silently missing.

## `account_timeline.json` — account-activity timeline

A list of observations of which account was logged in, used to attribute transcript
messages to an account by timestamp:

```json
[
  {
    "accountUuid": "…",
    "email": "you@example.com",
    "observed_at": 1782739658.11,   // when this account was first seen active
    "last_seen": 1782739809.94      // most recent time still active
  }
]
```

## Exported human-readable views (`data/`, git-ignored)

| File | Contents |
|---|---|
| `report.txt` | per-week × account × model token/cost table with a `Generated:` stamp |
| `usage.txt` | the subscription-limit report (per cycle, per account) + daily burn |
| `weekly.csv` | `weekly.json` flattened to CSV |
