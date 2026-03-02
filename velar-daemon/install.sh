#!/usr/bin/env bash
set -euo pipefail

DAEMON_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_PATH="$(which python3)"
HOME_DIR="$HOME"
PLIST_SRC="$DAEMON_DIR/launchd/com.velar.daemon.plist"
PLIST_DST="$HOME_DIR/Library/LaunchAgents/com.velar.daemon.plist"

echo "Installing VELAR daemon..."
echo "  Daemon dir: $DAEMON_DIR"
echo "  Python:     $PYTHON_PATH"
echo "  Plist dest: $PLIST_DST"

# Substitute placeholders
sed -e "s|__PYTHON_PATH__|$PYTHON_PATH|g" \
    -e "s|__DAEMON_DIR__|$DAEMON_DIR|g" \
    -e "s|__HOME__|$HOME_DIR|g" \
    "$PLIST_SRC" > "$PLIST_DST"

# Bootstrap the agent (launchd loads it at next login automatically;
# kickstart starts it immediately without requiring re-login)
launchctl bootout "gui/$(id -u)/com.velar.daemon" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl kickstart -k "gui/$(id -u)/com.velar.daemon"

echo "VELAR daemon installed and started."
echo "Logs: $HOME_DIR/Library/Logs/velar-daemon.log"
