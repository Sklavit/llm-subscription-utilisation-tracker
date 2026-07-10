# Inspecting the scheduled jobs (launchd)

The scheduler is two per-user macOS LaunchAgents installed by `install.sh`:

| Label | Schedule | Action |
|---|---|---|
| `com.<user>.claude-usage.scan` | daily + on login | full scan + merge + snapshot export |
| `com.<user>.claude-usage.account` | every 30 min + on login | sample the active account (cheap) |

The frequent account sampler is what keeps the per-account split accurate — it
notices login switches between the daily scans.

## List loaded agents

```bash
launchctl list                      # all loaded jobs
launchctl list | grep claude-usage  # just this tracker
```

Output is three columns: **PID** (a number if running, `-` if idle) · **last exit
status** (`0` = last run succeeded, nonzero = failed) · **label**. The fastest health
check is `launchctl list | grep claude-usage` — if the second column is `0` for both,
they're fine.

## Inspect one job in detail

```bash
launchctl print gui/$(id -u)/com.<user>.claude-usage.scan
```

The modern, detailed view — state, schedule, last exit reason, program arguments,
paths, and run counts.

## Check what it actually did

The agents log to files under the archive directory:

```bash
cat "${CLAUDE_USAGE_ARCHIVE:-$HOME/.claude-usage-archive}/scan.log"     # daily full-scan output
cat "${CLAUDE_USAGE_ARCHIVE:-$HOME/.claude-usage-archive}/account.log"  # 30-min account sampler
```

## See the installed definitions

```bash
ls ~/Library/LaunchAgents/ | grep claude-usage
cat ~/Library/LaunchAgents/com.<user>.claude-usage.scan.plist
```

## Force a run now

```bash
launchctl kickstart -k gui/$(id -u)/com.<user>.claude-usage.scan
```

## Mental model

- `launchctl list` → "what's loaded and did it last succeed?"
- `launchctl print gui/$(id -u)/<label>` → "tell me everything about this one"
- the `.log` files → "what was the actual output?"
