#!/bin/bash
# Back up or restore the files that make up the Arc-style Firefox setup.
#   ./backup.sh                  save a dated copy into ./backups
#   ./backup.sh restore <folder> put a saved copy back (quit Firefox first)
# Set PROFILE to use a different profile folder.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${PROFILE:-$(ls -d "$HOME/Library/Application Support/Firefox/Profiles/"*.default-release | head -1)}"
FILES=(user.js customKeys.json chrome/userChrome.css)
# The folder saver lives next to the Profiles folder, not inside the profile.
SAVER="$PROFILE/arc-restore-session.py"
[ -e "$SAVER" ] || SAVER="$PROFILE/../../arc-restore-session.py"
if [ "${1:-}" = "restore" ]; then
  SRC="${2:?Give the backup folder to restore from.}"
  if pgrep -f "Firefox.app/Contents/MacOS/firefox" >/dev/null; then
    echo "Firefox is running. Quit it with Cmd+Q, then run this again."; exit 1
  fi
  for f in "${FILES[@]}"; do
    [ -e "$SRC/$f" ] && { mkdir -p "$PROFILE/$(dirname "$f")"; cp "$SRC/$f" "$PROFILE/$f"; }
  done
  [ -e "$SRC/arc-restore-session.py" ] && cp "$SRC/arc-restore-session.py" "$SAVER"
  echo "Restored from $SRC"
else
  DEST="$HERE/backups/$(date +%Y%m%d-%H%M%S)"
  for f in "${FILES[@]}"; do
    [ -e "$PROFILE/$f" ] && { mkdir -p "$DEST/$(dirname "$f")"; cp "$PROFILE/$f" "$DEST/$f"; }
  done
  [ -e "$SAVER" ] && cp "$SAVER" "$DEST/arc-restore-session.py"
  echo "Saved to $DEST"
fi
