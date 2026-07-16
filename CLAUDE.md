# CLAUDE.md — claude-usage-tracker

Instructions for Claude when working in this folder.

## What this is

A self-contained automation that maintains a **persistent weekly archive of Claude
Code usage** (tokens + estimated API-equivalent cost), split per account. Read
`README.md` first for the full design.

## Source of truth vs. deployed copy

- **This folder is the source of truth.** Edit `budget.py` and the plists *here*.
- The *running* copy lives at `~/.claude-usage-archive/budget.py`, and the *active*
  LaunchAgents live at `~/Library/LaunchAgents/com.sklavit.claude-usage.*.plist`.
- A read-only snapshot of the stats is mirrored into `data/` here by the daily agent
  (`--export-dir`). `data/` is for backup/reading; the authoritative archive that must
  never shrink is `~/.claude-usage-archive/weekly.json`. Don't treat `data/weekly.json`
  as the source — it's a copy.
- After any edit, run `./install.sh` to redeploy. Never hand-edit the deployed copy
  as the primary change — it gets overwritten on the next install.

## Critical invariants — do not break these

1. **`weekly.json` must only grow.** The merge is `max()` per
   `(week, account, model, metric)` cell so weeks that have aged out of the logs stay
   frozen. Never replace it with a plain overwrite of a fresh scan — that would erase
   history once the source logs are deleted.
2. **De-dup by `message.id`.** Transcripts can repeat lines (resume/fork). Counting a
   message twice inflates usage. Keep the `seen_msg_ids` guard.
3. **Account attribution is timestamp-based and best-effort.** Transcripts carry no
   account field; the only signal is `~/.claude.json → oauthAccount`. Do not claim the
   per-account split is exact for history before tracking began — it isn't, and the
   README says so. Don't invent a fake account field.
4. **Stable interpreter.** The LaunchAgents call `/usr/bin/python3` on purpose (system
   Python survives Homebrew upgrades). The script must stay **stdlib-only** — no pip
   dependencies. Manual/interactive invocation uses `uv run` instead (see below); that's
   a convenience layer on top of the same stdlib-only script, not a dependency on uv
   for the scheduled jobs.

## The `check` view (% of subscription limit)

When the user asks for **"usage"**, run:
`uv run ~/.claude-usage-archive/budget.py check` — it shows % of the weekly
limit consumed per weekly cycle per account.

- True "% of limit" **cannot** be computed from tokens: Anthropic publishes no fixed
  limit and stores no history. The only source is the live claude.ai endpoint.
- **Primary source is Claude Code itself**: `claude auth status --json` (identity) +
  `claude -p '/usage'` (limits, incl. the per-model weekly bucket). Same credential
  store → the (account, reading) pair cannot diverge. Never try to read OAuth tokens
  or hit the endpoint directly — go through the `claude` CLI.
- **CodexBar is fallback only** (`--source oauth`). It may serve a *cached* account
  after a login switch, so fallback readings are attributed by their weekly reset
  anchor (reset time mod 7 days — a stable per-account fingerprint, `_anchor_key`),
  not by trusting the logged-in email. Historically mislabelled samples were
  retro-fixed this way on 2026-07-03 (marked `attr: anchor-retrofix`, original email
  kept in `email_orig`; backup at `limit_samples.jsonl.bak-20260703`).
- The 30-min agent samples it (`--record-limits`) into the append-only
  `~/.claude-usage-archive/limit_samples.jsonl`. It only accrues going forward; it
  cannot be backfilled. Don't claim historical % before sampling began. Failed
  attempts are recorded with an `err` field — never silently.
- Each account is only captured while it's the logged-in one; the other account's
  numbers stay frozen at their last reading until you switch back.

## Common tasks

- **Change pricing:** edit the `PRICING` dict at the top of `budget.py`, then `./install.sh`.
- **Add a real Fable 5 price:** currently falls back to the `sonnet` tier (flagged in
  output). Use the `claude-api` skill / reference to get correct list prices before
  hardcoding.
- **Change schedule:** edit the plist templates in `install.sh` (they're generated
  there), then re-run it.
- **Inspect data:** `uv run ~/.claude-usage-archive/budget.py report`.

## When asked about "why is old usage missing"

The root cause is `cleanupPeriodDays` (Claude Code deletes transcripts after N days,
default 30). This archive is the mitigation. See `skills/claude-usage/SKILL.md`.

## Safety

- Never delete or overwrite `~/.claude-usage-archive/weekly.json` without explicit
  user confirmation — it's irreplaceable history.
- This automation only **reads** `~/.claude/projects` and `~/.claude.json`. It must
  never modify Claude Code's own files.
