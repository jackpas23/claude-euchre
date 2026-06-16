#!/usr/bin/env bash
# claude-euchre installer — drops the launcher on PATH and wires the
# Claude Code statusline (non-destructively, with passthrough to any
# statusline you already have).
set -euo pipefail

# Resolve the repo dir whether run locally or via curl | bash.
if [ -n "${BASH_SOURCE:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  REPO_DIR=""
fi

BIN_DIR="${EUCHRE_BIN_DIR:-$HOME/.local/bin}"
EU_DIR="$HOME/.claude/euchre"
SETTINGS="$HOME/.claude/settings.json"
LAUNCHER="$BIN_DIR/euchre"

mkdir -p "$BIN_DIR" "$EU_DIR"

# Get euchre.py: prefer the local checkout, else fetch from GitHub.
if [ -n "$REPO_DIR" ] && [ -f "$REPO_DIR/euchre.py" ]; then
  install -m 0755 "$REPO_DIR/euchre.py" "$LAUNCHER"
else
  RAW="https://raw.githubusercontent.com/jackpas23/claude-euchre/main/euchre.py"
  echo "• downloading euchre.py from $RAW"
  curl -fsSL "$RAW" -o "$LAUNCHER"
  chmod 0755 "$LAUNCHER"
fi
ln -sf "$LAUNCHER" "$BIN_DIR/euc"
echo "✓ installed: $LAUNCHER  (+ 'euc' alias)"

# Wire the statusline (Python does the safe JSON edit + backup).
python3 "$LAUNCHER" __install_statusline "$SETTINGS" "$EU_DIR" "$LAUNCHER"

# PATH sanity check.
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "⚠  $BIN_DIR is not on your PATH — add this to your shell rc:";
     echo "     export PATH=\"$BIN_DIR:\$PATH\"";;
esac

cat <<EOF

✓ claude-euchre installed.

  In Claude Code, the board now lives in your statusline (below the prompt).
  Play with in-session bash commands:

      !euc new      deal a hand
      !euc 2        play card #2
      !euc          show the full table
      !euc help     rules + commands

  Deal your first hand now:  !euc new
  (If the statusline doesn't update, press Enter or restart Claude Code.)
EOF
