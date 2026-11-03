#!/bin/bash
LABEL="com.cardio-digest.popup"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$HOME/Library/Application Support/CardioDigest"
echo "Digest popup removed."
