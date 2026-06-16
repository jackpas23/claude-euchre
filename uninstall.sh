#!/usr/bin/env bash
# claude-euchre uninstaller — restores your previous statusline and removes
# the launcher. Your settings.json backup is at settings.json.euchre-bak.
set -euo pipefail

BIN_DIR="${EUCHRE_BIN_DIR:-$HOME/.local/bin}"
EU_DIR="$HOME/.claude/euchre"
SETTINGS="$HOME/.claude/settings.json"
LAUNCHER="$BIN_DIR/euchre"

if [ -f "$LAUNCHER" ]; then
  python3 "$LAUNCHER" __uninstall_statusline "$SETTINGS" "$EU_DIR" || true
fi

rm -f "$BIN_DIR/euc" "$LAUNCHER"
rm -f "$EU_DIR/state.json" "$EU_DIR/state.tmp"
echo "✓ removed launcher and game state."
echo "  (kept $EU_DIR/prev_statusline.json and settings.json.euchre-bak just in case)"
