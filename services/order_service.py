import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from config import ADMIN_IDS
import database as db
from .midasbuy import MidasbuyService
from utils.helpers import format_currency

logger = logging.getLogger("services.order")


class OrderService:
    @staticmethod
    async def notify_user(bot: Bot, telegram_id: int, text: str):
        """Sends message to user safely."""
        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
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
        1. Checks idempotency (if already completed or paid, ignore)
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
                    f"✅ <b>Buyurtmangiz muvaffaqiyatli bajarildi!</b>\n\n"
                    f"📦 <b>Buyurtma:</b> <code>{order['order_id']}</code>\n"
                    f"🎮 <b>UC miqdori:</b> {order['uc_amount']} UC\n"
                    f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n\n"
                    f"Rahmat! Yana xarid qilish uchun /start ni bosing."
                )
                await cls.notify_user(bot, order["user_id"], user_msg)
                return True
            else:
                await db.update_order_status(order_id, "MANUAL_REVIEW")
                admin_alert = (
                    f"⚠️ <b>AUTO YETKAZISHDA XATOLIK!</b>\n"
                    f"Order: <code>{order['order_id']}</code>\n"
                    f"Sabab: {err_msg}\n"
                    f"Status: MANUAL_REVIEW ga o'tkazildi. Iltimos, qo'lda yetkazing."
                )
                await cls.notify_admins(bot, admin_alert)
                return False
        else:
            # Manual delivery mode
            await db.update_order_status(order_id, "PAID")
            admin_alert = (
                f"🚨 <b>YANGI TO'LANGAN BUYURTMA (QO'LDA YETKAZISH KERAK)!</b>\n\n"
                f"📦 <b>Order:</b> <code>{order['order_id']}</code>\n"
                f"👤 <b>Foydalanuvchi:</b> {order.get('username') or order.get('first_name')} (ID: <code>{order['user_id']}</code>)\n"
                f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
                f"💎 <b>Paket:</b> {order['product_name']}\n"
                f"💰 <b>Narx:</b> {format_currency(order['price'])}\n\n"
                f"<i>PUBG hisobiga UC yuboring va botdagi buyurtmalar bo'limidan 'UC yuborildi' tugmasini bosing.</i>"
            )
            await cls.notify_admins(bot, admin_alert)

            user_msg = (
                f"💰 <b>To'lovingiz qabul qilindi!</b>\n\n"
                f"📦 <b>Buyurtma:</b> <code>{order['order_id']}</code>\n"
                f"💎 <b>Paket:</b> {order['product_name']}\n"
                f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n\n"
                f"⏳ UC operator tomonidan qisqa vaqt ichida o'yindagi hisobingizga yuboriladi!"
            )
            await cls.notify_user(bot, order["user_id"], user_msg)
            return True

    @classmethod
    async def mark_manual_delivered(cls, bot: Bot, order_id: str) -> bool:
        """Admin marks order completed."""
        order = await db.get_order(order_id)
        if not order:
            return False

        await db.update_order_status(order_id, "COMPLETED")
        user_msg = (
            f"✅ <b>Buyurtmangiz muvaffaqiyatli bajarildi!</b>\n\n"
            f"📦 <b>Buyurtma:</b> <code>{order['order_id']}</code>\n"
            f"🎮 <b>UC:</b> {order['product_name']}\n"
            f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n\n"
            f"Rahmat! Bizning xizmatimizdan foydalanganingiz uchun minnatdormiz."
        )
        await cls.notify_user(bot, order["user_id"], user_msg)
        return True
