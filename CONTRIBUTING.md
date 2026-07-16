# Contributing

Thanks for your interest. This is a small, personal-scale tool; contributions and
issues are welcome but kept simple.

## Ground rules

- **Standard library only.** `budget.py` deliberately has no third-party dependencies
  so it runs anywhere with a modern Python and needs no virtualenv. Please keep it
  that way unless there's a compelling reason.
- **Python 3.10+.**
- The archive is **append-only and monotonic** — aggregates are max-merged per
  `(week, account, model)` cell so history never shrinks. Any change to the merge or
  scan logic must preserve that invariant.

## Running locally

```bash
# One-shot report from the current archive (no install required):
uv run budget.py            # scan + merge, then the summary view
uv run budget.py check      # % of subscription limit consumed
uv run budget.py report     # token/cost archive
```

`uv run` is convenient but optional; `python3 budget.py ...` works identically.

## Data & privacy

The `data/` directory holds generated snapshots (`weekly.json`,
`limit_samples.jsonl`, `account_timeline.json`, …) that embed **account emails and
UUIDs**. It is git-ignored on purpose — never commit its contents. The authoritative
runtime archive lives outside the repo at `~/.claude-usage-archive/`.

## Style

- Match the existing style in `budget.py`: small module-level functions, docstrings
  that explain *why*, comments reserved for non-obvious reasoning.
- Keep the CLI subcommands and their output stable; they are consumed by the
  scheduled LaunchAgents and the `claude-usage` skill.

## Commits

- Write descriptive commit messages explaining the reasoning, not just the change.
- Note user-facing changes in `CHANGELOG.md` under `[Unreleased]`.
