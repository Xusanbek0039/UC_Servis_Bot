"""Periodic admin reminders for paid orders that have not been fulfilled yet.

Every ADMIN_REMINDER_INTERVAL seconds (default 180 = 3 min) admins receive a reminder
for each paid order still waiting for delivery. Reminders stop as soon as the admin
presses "✅ Bajarildi" (adm_deliver_ord) or the supplier completes the order.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import ADMIN_IDS, ADMIN_REMINDER_INTERVAL
from utils.helpers import format_currency

logger = logging.getLogger("services.order_reminder")

CHECK_EVERY_SECONDS = 30


def reminder_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Bajarildi (UC yuborildi)", callback_data=f"adm_deliver_ord:{order_id}")],
        [InlineKeyboardButton(text="🔎 Buyurtmani ko'rish", callback_data=f"adm_view_ord:{order_id}")],
    ])


def _elapsed_text(order: dict) -> str:
    created = order.get("created_at")
    if not isinstance(created, datetime):
        return ""
    minutes = int((datetime.now() - created.replace(tzinfo=None)).total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} daqiqa"
    return f"{minutes // 60} soat {minutes % 60} daqiqa"


def _reminder_text(order: dict) -> str:
    count = int(order.get("admin_reminder_count", 0)) + 1
    elapsed = _elapsed_text(order)
    status_note = "❌ Supplier xatosi — qo'lda yetkazing" if order.get("delivery_status") == "FAILED" else "⏳ Qo'lda yetkazish kutilmoqda"
    return (
        f"⏰ <b>ESLATMA #{count}: BUYURTMA HALI BAJARILMADI!</b>\n\n"
        f"📦 Order: <code>{order['order_id']}</code>\n"
        f"🆔 Player ID: <code>{order.get('player_id', '-')}</code>\n"
        f"💎 Paket: {order.get('product_name', '-')}\n"
        f"💰 Summa: {format_currency(order.get('price', 0))}\n"
        f"{status_note}\n"
        + (f"🕒 To'lovdan beri: <b>{elapsed}</b>\n" if elapsed else "")
        + "\n👉 Iltimos, buyurtmani bajaring va pastdagi <b>«✅ Bajarildi»</b> tugmasini bosing. "
        "Tasdiqlamaguningizcha har " + f"{max(1, ADMIN_REMINDER_INTERVAL // 60)} daqiqada eslatib turaman."
    )


async def delete_reminder_messages(bot: Bot, order_id: str, keep: Optional[tuple] = None) -> None:
    """Remove previously sent reminder messages for the order (keeps chats clean)."""
    for item in await db.pop_admin_reminder_messages(order_id):
        if keep and (item.get("chat_id"), item.get("message_id")) == keep:
            continue
        try:
            await bot.delete_message(chat_id=item["chat_id"], message_id=item["message_id"])
        except Exception:
            pass


async def send_reminder(bot: Bot, order: dict) -> None:
    order_id = order["order_id"]
    await delete_reminder_messages(bot, order_id)
    text = _reminder_text(order)
    kb = reminder_keyboard(order_id)
    sent = []
    for admin_id in ADMIN_IDS:
        try:
            msg = await bot.send_message(chat_id=admin_id, text=text, reply_markup=kb, parse_mode="HTML")
            sent.append({"chat_id": admin_id, "message_id": msg.message_id})
        except Exception:
            logger.warning("Unable to send order reminder to admin %s", admin_id)
    await db.set_admin_reminder_messages(order_id, sent)


async def admin_order_reminder_loop(bot: Bot) -> None:
    logger.info("Admin order reminder loop started (interval=%ss)", ADMIN_REMINDER_INTERVAL)
    while True:
        try:
            for order in await db.get_orders_due_for_admin_reminder(ADMIN_REMINDER_INTERVAL):
                try:
                    await send_reminder(bot, order)
                except Exception:
                    logger.exception("Failed to send reminder for %s", order.get("order_id"))
        except Exception:
            logger.exception("Admin reminder cycle failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
