#!/bin/bash
# Installs the Friday 4 pm digest popup on macOS.
#   usage:  bash install.sh https://<username>.github.io/<repo>/
# Re-run any time to change the URL or time. Remove with uninstall.sh.
set -euo pipefail

URL="${1:-}"
if [[ -z "$URL" ]]; then
  echo "Usage: bash install.sh https://<username>.github.io/<repo>/"; exit 1
fi
WEEKDAY="${DIGEST_WEEKDAY:-5}"   # 0=Sun … 5=Fri
HOUR="${DIGEST_HOUR:-16}"
MINUTE="${DIGEST_MINUTE:-0}"

LABEL="com.cardio-digest.popup"
APPDIR="$HOME/Library/Application Support/CardioDigest"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$APPDIR" "$HOME/Library/LaunchAgents"

cat > "$APPDIR/open_digest.sh" <<EOF
#!/bin/bash
URL="$URL"
STAMP="\$(date +%s)"
osascript -e 'display notification "Your weekly cardiopulmonary literature digest is ready" with title "Literature digest" sound name "Glass"' >/dev/null 2>&1 || true
for APP in "Google Chrome" "Microsoft Edge" "Brave Browser" "Chromium"; do
  if open -Ra "\$APP" 2>/dev/null; then
    # --app opens a chromeless popup-style window
    open -na "\$APP" --args --app="\${URL}?t=\${STAMP}" --window-size=640,900 --window-position=60,60
    exit 0
  fi
done
open "\${URL}?t=\${STAMP}"     # Safari fallback
EOF
chmod +x "$APPDIR/open_digest.sh"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$APPDIR/open_digest.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>$WEEKDAY</integer>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>StandardErrorPath</key><string>$APPDIR/popup.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed. The digest will pop up every Friday at $(printf '%02d:%02d' "$HOUR" "$MINUTE")."
echo "If the Mac is asleep at that time it appears when it wakes."
echo "Test now with:  bash \"$APPDIR/open_digest.sh\""
