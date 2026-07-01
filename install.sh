#!/usr/bin/env bash
# Install the Claude Code weekly usage tracker: deploy script, generate + load
# LaunchAgents, run an initial backfill. Re-run any time after editing usage.py.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_DIR="$HOME/.claude-usage-archive"
AGENTS_DIR="$HOME/Library/LaunchAgents"
EXPORT_DIR="$HERE/data"   # collected stats are mirrored here (inside this notes folder)
PY="/usr/bin/python3"   # system python (survives Homebrew upgrades); script is stdlib-only
UID_NUM="$(id -u)"

SCAN_LABEL="com.sklavit.claude-usage.scan"
ACCT_LABEL="com.sklavit.claude-usage.account"

echo "==> Deploying usage.py to $ARCHIVE_DIR"
mkdir -p "$ARCHIVE_DIR"
rm -f "$ARCHIVE_DIR/track.py"
cp "$HERE/usage.py" "$ARCHIVE_DIR/usage.py"

echo "==> Writing LaunchAgent plists to $AGENTS_DIR"
mkdir -p "$AGENTS_DIR"

cat > "$AGENTS_DIR/$SCAN_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$SCAN_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$ARCHIVE_DIR/usage.py</string>
        <string>--export-dir</string>
        <string>$EXPORT_DIR</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>5</integer>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key><string>$ARCHIVE_DIR/scan.log</string>
    <key>StandardErrorPath</key><string>$ARCHIVE_DIR/scan.log</string>
</dict>
</plist>
PLIST

cat > "$AGENTS_DIR/$ACCT_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$ACCT_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$ARCHIVE_DIR/usage.py</string>
        <string>--record-limits</string>
    </array>
    <key>StartInterval</key><integer>1800</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key><string>$ARCHIVE_DIR/account.log</string>
    <key>StandardErrorPath</key><string>$ARCHIVE_DIR/account.log</string>
</dict>
</plist>
PLIST

echo "==> (Re)loading LaunchAgents"
for L in "$SCAN_LABEL" "$ACCT_LABEL"; do
    launchctl bootout "gui/$UID_NUM/$L" 2>/dev/null || true
    launchctl bootstrap "gui/$UID_NUM" "$AGENTS_DIR/$L.plist"
done

echo "==> Keep a copy of the plists in the repo for reference"
cp "$AGENTS_DIR/$SCAN_LABEL.plist" "$HERE/launchagents/" 2>/dev/null || true
cp "$AGENTS_DIR/$ACCT_LABEL.plist" "$HERE/launchagents/" 2>/dev/null || true

echo "==> Initial backfill + stats snapshot to $EXPORT_DIR"
"$PY" "$ARCHIVE_DIR/usage.py" --export-dir "$EXPORT_DIR"

echo
echo "Done. Loaded agents:"
launchctl list | grep claude-usage || true
