"""Telegram bot — Tinder account checker with auto-pricing (English)."""

import logging
import re
import typing
import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from .tinder_client import TinderClient, LookupStatus

logger = logging.getLogger(__name__)

_HEADER = "[Tinder Query Result]"


def _format_age(reg_date):
    if not reg_date:
        return "-"
    delta = datetime.datetime.now(tz=datetime.timezone.utc) - reg_date
    sec = int(delta.total_seconds())
    days = sec // 86400
    hours = (sec % 86400) // 3600
    mins = (sec % 3600) // 60
    secs = sec % 60
    s = f"{days}d {hours}h {mins}m {secs}s"
    if days >= 30:
        s += "  [Full Moon]"
    return s


def _format_result(profile):
    reg_line = profile.reg_date.strftime("%Y-%m-%d %H:%M:%S") if profile.reg_date else "-"
    age_line = _format_age(profile.reg_date)

    lines = [
        _HEADER,
        f"high price @tinderbuyor",
        "",
        f"👤 Username: @{profile.username}",
        f"{'🟢' if 'Active' in profile.status_text else '🔴'} Status: {profile.status_text}",
        f"📸 Photos: {len(profile.photo_urls)}",
        f"✏️ Name: {profile.name}",
        f"🎂 Age: {profile.age}",
        f"📅 Registered: {reg_line}",
        f"⏳ Account Age: {age_line}",
        f"🔗 Profile: https://tinder.com/@{profile.username}",
    ]
    return "\n".join(lines)


def _format_error(username, detail=""):
    msg = f"Lookup failed: @{username}"
    if detail:
        msg += f"\n\n{detail}"
    return msg


def _extract_username(text):
    text = text.strip().lower()
    m = re.search(r'tinder\.com/@?([a-z0-9_]+)', text)
    if m:
        return m.group(1)
    if text.startswith("@"):
        return text[1:]
    m = re.search(r"tinder://u/([a-z0-9_]+)", text)
    if m:
        return m.group(1)
    if re.match(r"^[a-z0-9_]+$", text):
        return text
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi\U0001f44b Send a Tinder username and I'll look it up.\n\n"
        "Examples: <code>test</code>  <code>@test</code>  "
        "<code>tinder.com/@test</code>",
        parse_mode="HTML",
    )


async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    username = _extract_username(text)

    if not username:
        await update.message.reply_text("Could not recognize a Tinder username.")
        return
    if not re.match(r"^[a-z0-9_]+$", username) or len(username) > 50:
        await update.message.reply_text("Invalid username format.")
        return

    await update.message.reply_chat_action("typing")

    client = TinderClient()
    try:
        result = client.lookup(username)
    except Exception as e:
        logger.exception("Lookup crashed for %s", username)
        await update.message.reply_text(_format_error(username, str(e)))
        return

    if result.status != LookupStatus.FOUND:
        await update.message.reply_text(result.message or "Unknown error")
        return

    profile = result.profile
    caption = _format_result(profile)

    await update.message.reply_text(caption, parse_mode="HTML")


def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))
    return app
