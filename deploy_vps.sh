#!/bin/bash
# One-click deploy script for VPS - run this after SSH into your server
set -e

echo "=== Installing Tinder Checker Bot ==="

# 1. Install Python if needed
if ! command -v python3 &> /dev/null; then
    apt-get update -y && apt-get install -y python3 python3-pip
fi

# 2. Clone repo
cd /opt
git clone https://github.com/scooter7777/TinderCheckerBot.git
cd TinderCheckerBot

# 3. Install dependencies
pip3 install -r requirements.txt

# 4. Set up as a systemd service (auto-start on boot, auto-restart)
cat > /etc/systemd/system/tinderbot.service << 'SERVICEEOF'
[Unit]
Description=Tinder Account Checker Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/TinderCheckerBot
Environment="TINDER_BOT_TOKEN=YOUR_TOKEN_HERE"
ExecStart=/usr/bin/python3 -m tinder_bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Set your token:"
echo "     nano /etc/systemd/system/tinderbot.service"
echo "     (replace YOUR_TOKEN_HERE with your bot token)"
echo ""
echo "  2. Start the bot:"
echo "     systemctl daemon-reload"
echo "     systemctl enable --now tinderbot"
echo ""
echo "  3. Check status:"
echo "     systemctl status tinderbot"
echo "     journalctl -u tinderbot -f"
