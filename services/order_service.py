import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from config import ADMIN_IDS
import database as db
from .midasbuy import MidasbuyService
from utils.helpers import format_currency, DIVIDER, SUB_DIVIDER
from keyboards.user import order_success_keyboard
from emojis import E

logger = logging.getLogger("services.order")


class OrderService:
    @staticmethod
    async def notify_user(bot: Bot, telegram_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
        """Sends message to user safely."""
        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to notify user {telegram_id}: {e}")

    @staticmethod
    async def notify_admins(bot: Bot, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
        """Broadcasts alert to all bot admins."""
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 <b>[ADMIN XABARNOMASI]</b>\n\n{text}",
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    @classmethod
    async def handle_payment_success(cls, bot: Bot, order_id: str, provider_tx_id: str = "") -> bool:
        """
        Processes successful payment:
        1. Checks idempotency (if already completed or paid, skip duplicate)
        2. Routes to AUTO delivery or MANUAL review based on settings
        """
        order = await db.get_order(order_id)
        if not order:
            logger.error(f"Order not found for payment success: {order_id}")
            return False

        if order["status"] in ("PAID", "PROCESSING", "COMPLETED"):
            logger.info(f"Idempotency: Order {order_id} is already in state {order['status']}. Skipping duplicate.")
            return True

        # Update payment record
        await db.update_payment_status(order_id=order_id, status="PAID", raw_data=provider_tx_id)

        delivery_mode = await db.get_setting("delivery_mode", "MANUAL")
        logger.info(f"Processing delivery for order {order_id} (Mode: {delivery_mode})")

        if delivery_mode == "AUTO":
            # Automated delivery via Midasbuy
            await db.update_order_status(order_id, "PROCESSING")
            success, tx_id, err_msg = await MidasbuyService.deliver_uc(
                order_id=order["order_id"],
                player_id=order["player_id"],
                uc_amount=order["uc_amount"],
            )
            if success:
                await db.update_order_status(order_id, "COMPLETED")
                user_msg = (
                    f"{DIVIDER}\n"
                    f"   {E('success')} <b>BUYURTMA BAJARILDI</b>\n"
                    f"{DIVIDER}\n\n"
                    f"{E('uc')} <b>UC muvaffaqiyatli hisobingizga yuklandi!</b>\n\n"
                    f"{E('game')} <b>O'yin:</b> PUBG Mobile\n"
                    f"{E('uc')} <b>Paket:</b> <b>{order['product_name']}</b>\n"
                    f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
                    f"📦 <b>Buyurtma kodi:</b> <code>{order['order_id']}</code>\n"
                    f"{SUB_DIVIDER}\n"
                    f"<i>Rahmat! Bizning xizmatimizdan foydalanganingiz uchun minnatdormiz.</i>\n\n"
                    f"Yana UC kerak bo'lsa, xizmatingizdamiz!"
                )
                await cls.notify_user(bot, order["user_id"], user_msg, reply_markup=order_success_keyboard())
                return True
            else:
                await db.update_order_status(order_id, "MANUAL_REVIEW")
                admin_alert = (
                    f"{DIVIDER}\n"
                    f"{E('error')} <b>AUTO YETKAZISHDA XATOLIK!</b>\n"
                    f"{DIVIDER}\n\n"
                    f"📦 <b>Order:</b> <code>{order['order_id']}</code>\n"
                    f"⚠️ <b>Sabab:</b> {err_msg}\n"
                    f"Holat: <code>MANUAL_REVIEW</code> ga o'tkazildi. Iltimos, qo'lda yetkazing."
                )
                await cls.notify_admins(bot, admin_alert)
                return False
        else:
            # Manual delivery mode
            await db.update_order_status(order_id, "PAID")
            admin_alert = (
                f"{DIVIDER}\n"
                f"🚨 <b>YANGI TO'LANGAN BUYURTMA (QO'LDA YETKAZISH KERAK)!</b>\n"
                f"{DIVIDER}\n\n"
                f"📦 <b>Order:</b> <code>{order['order_id']}</code>\n"
                f"{E('profile')} <b>Mijoz:</b> {order.get('username') or order.get('first_name')} (ID: <code>{order['user_id']}</code>)\n"
                f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
                f"{E('uc')} <b>Paket:</b> {order['product_name']}\n"
                f"{E('balance')} <b>Summa:</b> {format_currency(order['price'])}\n\n"
                f"<i>PUBG hisobiga UC yuboring va botdan 'UC yuborildi' tugmasini bosing.</i>"
            )
            await cls.notify_admins(bot, admin_alert)

            user_msg = (
                f"{DIVIDER}\n"
                f"   {E('success')} <b>TO'LOV QABUL QILINDI</b>\n"
                f"{DIVIDER}\n\n"
                f"📦 <b>Buyurtma kodi:</b> <code>{order['order_id']}</code>\n"
                f"{E('uc')} <b>Paket:</b> {order['product_name']}\n"
                f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
                f"{SUB_DIVIDER}\n"
                f"{E('clock')} <i>UC operator tomonidan qisqa vaqt (1-5 daqiqa) ichida o'yindagi hisobingizga yuklanadi!</i>"
            )
            await cls.notify_user(bot, order["user_id"], user_msg, reply_markup=order_success_keyboard())
            return True

    @classmethod
    async def mark_manual_delivered(cls, bot: Bot, order_id: str) -> bool:
        """Admin marks order completed."""
        order = await db.get_order(order_id)
        if not order:
            return False

        await db.update_order_status(order_id, "COMPLETED")
        user_msg = (
            f"{DIVIDER}\n"
            f"   {E('success')} <b>BUYURTMA BAJARILDI</b>\n"
            f"{DIVIDER}\n\n"
            f"{E('uc')} <b>UC muvaffaqiyatli hisobingizga yuklandi!</b>\n\n"
            f"{E('game')} <b>O'yin:</b> PUBG Mobile\n"
            f"{E('uc')} <b>Paket:</b> <b>{order['product_name']}</b>\n"
            f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
            f"📦 <b>Buyurtma:</b> <code>{order['order_id']}</code>\n"
            f"{SUB_DIVIDER}\n"
            f"<i>Rahmat! Bizning xizmatimizdan foydalanganingiz uchun minnatdormiz.</i>\n\n"
            f"Yana UC kerak bo'lsa, xizmatingizdamiz!"
        )
        await cls.notify_user(bot, order["user_id"], user_msg, reply_markup=order_success_keyboard())
        return True
