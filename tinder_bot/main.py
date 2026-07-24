"""Entry point: runs the Tinder checking Telegram bot."""

import sys
import os
import logging

# Add this line to send a "here's how to get a token" hint
_HELP = """
You need a Telegram Bot Token from @BotFather.

Usage:
  export TINDER_BOT_TOKEN="123456:ABC-DEF..."
  python3 -m tinder_bot.main

Or provide it as an argument:
  python3 -m tinder_bot.main 123456:ABC-DEF...
"""


def main():
    token = os.environ.get("TINDER_BOT_TOKEN")

    if not token and len(sys.argv) > 1:
        token = sys.argv[1]

    if not token:
        print(_HELP.strip())
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from .tg_bot import build_app

    app = build_app(token)
    print("Bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
