#!/usr/bin/env bash
# Remove the Claude Code usage tracker LaunchAgents.
#   ./uninstall.sh           # unload + remove agents, KEEP the archive/history
#   ./uninstall.sh --purge   # also delete ~/.claude-usage-archive (DESTROYS history)
set -euo pipefail

AGENTS_DIR="$HOME/Library/LaunchAgents"
ARCHIVE_DIR="$HOME/.claude-usage-archive"
UID_NUM="$(id -u)"
SCAN_LABEL="com.sklavit.claude-usage.scan"
ACCT_LABEL="com.sklavit.claude-usage.account"

for L in "$SCAN_LABEL" "$ACCT_LABEL"; do
    echo "==> Unloading $L"
    launchctl bootout "gui/$UID_NUM/$L" 2>/dev/null || true
    rm -f "$AGENTS_DIR/$L.plist"
done

if [[ "${1:-}" == "--purge" ]]; then
    echo "==> Purging $ARCHIVE_DIR (history will be lost)"
    rm -rf "$ARCHIVE_DIR"
else
    echo "==> Kept $ARCHIVE_DIR (history preserved). Use --purge to remove it."
fi

echo "Done."
