import asyncio
import logging
from aiogram import Bot

import database as db
import mailtm
from config import POLL_INTERVAL

logger = logging.getLogger(__name__)


async def poll_mailboxes(bot: Bot):
    """Continuously poll all active mailboxes and forward new emails."""
    while True:
        try:
            mailboxes = await db.get_all_active_mailboxes()
            for mb in mailboxes:
                try:
                    await check_mailbox(bot, mb)
                except Exception as exc:
                    logger.exception("Error checking mailbox %s: %s", mb["address"], exc)
        except Exception as exc:
            logger.exception("Error fetching mailboxes: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)


async def check_mailbox(bot: Bot, mb):
    messages = await mailtm.get_messages(mb["token"])
    for msg in messages:
        msg_id = msg.get("id", "")
        if not msg_id:
            continue

        if await db.message_exists(msg_id):
            continue

        from_info = msg.get("from", {})
        from_addr = from_info.get("address", "unknown")
        from_name = from_info.get("name", "")
        subject   = msg.get("subject", "(без темы)")
        intro     = msg.get("intro", "")

        # Save to DB before sending (avoid duplicate on retry)
        await db.save_message(
            mailbox_id = mb["id"],
            message_id = msg_id,
            from_addr  = from_addr,
            subject    = subject,
            intro      = intro,
        )

        # Fetch full body
        body = await mailtm.get_message_body(mb["token"], msg_id)

        # Build Telegram message
        sender_str = f"{from_name} &lt;{from_addr}&gt;" if from_name else f"&lt;{from_addr}&gt;"
        text = (
            f"📩 <b>Новое письмо!</b>\n"
            f"📧 Ящик: <code>{mb['address']}</code>\n\n"
            f"👤 От: {sender_str}\n"
            f"📌 Тема: <b>{_esc(subject)}</b>\n"
        )

        if body:
            # Trim to avoid hitting Telegram 4096 char limit
            max_body = 3000
            trimmed = body[:max_body]
            if len(body) > max_body:
                trimmed += "\n… <i>(текст обрезан)</i>"
            text += f"\n{_esc(trimmed)}"
        elif intro:
            text += f"\n{_esc(intro)}"

        try:
            await bot.send_message(mb["tg_id"], text, parse_mode="HTML")
            logger.info("Forwarded message %s → tg:%s", msg_id, mb["tg_id"])
        except Exception as exc:
            logger.error("Cannot send to tg:%s – %s", mb["tg_id"], exc)


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def start_scheduler(bot: Bot):
    asyncio.create_task(poll_mailboxes(bot))
    logger.info("Mail poller started (interval=%ds)", POLL_INTERVAL)
