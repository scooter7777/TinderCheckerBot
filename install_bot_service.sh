#!/bin/bash
# Install Tinder bot as a macOS launchd service (starts on boot, auto-restart)

PLIST_SRC="$HOME/Documents/New project/com.tinder.bot.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.tinder.bot.plist"

# Check if token is set
if [ -z "$TINDER_BOT_TOKEN" ]; then
    echo "Please set your bot token first:"
    echo "  export TINDER_BOT_TOKEN=\"your_token_here\""
    echo "Then re-run this script."
    exit 1
fi

# Replace token in plist
sed "s/YOUR_TOKEN_HERE/$TINDER_BOT_TOKEN/" "$PLIST_SRC" > "$PLIST_DST"

# Load the service
launchctl load "$PLIST_DST"

echo "Bot service installed! It will:"
echo "  - Start automatically on login"
echo "  - Stay running 24/7"
echo "  - Restart if it crashes"
echo ""
echo "To stop:  launchctl unload $PLIST_DST"
echo "To check: launchctl list | grep com.tinder.bot"
echo "Logs:     $HOME/Documents/New project/tinder_bot.log"
