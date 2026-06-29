# CLAUDE.md — claude-usage-tracker

Instructions for Claude when working in this folder.

## What this is

A self-contained automation that maintains a **persistent weekly archive of Claude
Code usage** (tokens + estimated API-equivalent cost), split per account. Read
`README.md` first for the full design.

## Source of truth vs. deployed copy

- **This folder is the source of truth.** Edit `track.py` and the plists *here*.
- The *running* copy lives at `~/.claude-usage-archive/track.py`, and the *active*
  LaunchAgents live at `~/Library/LaunchAgents/com.sklavit.claude-usage.*.plist`.
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
   dependencies.

## Common tasks

- **Change pricing:** edit the `PRICING` dict at the top of `track.py`, then `./install.sh`.
- **Add a real Fable 5 price:** currently falls back to the `sonnet` tier (flagged in
  output). Use the `claude-api` skill / reference to get correct list prices before
  hardcoding.
- **Change schedule:** edit the plist templates in `install.sh` (they're generated
  there), then re-run it.
- **Inspect data:** `/usr/bin/python3 ~/.claude-usage-archive/track.py --report`.

## When asked about "why is old usage missing"

The root cause is `cleanupPeriodDays` (Claude Code deletes transcripts after N days,
default 30). This archive is the mitigation. See `skills/claude-usage/SKILL.md`.

## Safety

- Never delete or overwrite `~/.claude-usage-archive/weekly.json` without explicit
  user confirmation — it's irreplaceable history.
- This automation only **reads** `~/.claude/projects` and `~/.claude.json`. It must
  never modify Claude Code's own files.
