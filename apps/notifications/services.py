import logging
from typing import Optional, List
from django.conf import settings
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from apps.users.models import TelegramUser
from .models import NotificationLog

logger = logging.getLogger("apps.notifications")


class NotificationService:
    @staticmethod
    def _get_bot() -> Optional[Bot]:
        token = getattr(settings, "BOT_TOKEN", "")
        if token and token != "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ":
            return Bot(token=token)
        return None

    @classmethod
    async def send_message(
        cls,
        telegram_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        notification_type: str = NotificationLog.NotificationType.ORDER_STATUS,
        user: Optional[TelegramUser] = None,
    ) -> bool:
        """Send Telegram message and persist log."""
        bot = cls._get_bot()
        is_sent = False
        error_msg = ""

        if bot:
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                )
                is_sent = True
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to send telegram message to {telegram_id}: {e}")
            finally:
                await bot.session.close()
        else:
            logger.info(f"[DEV MOCK SEND] To: {telegram_id}\n{text}")
            is_sent = True

        NotificationLog.objects.create(
            user=user,
            telegram_id=telegram_id,
            notification_type=notification_type,
            text=text,
            is_sent=is_sent,
            error_message=error_msg,
        )
        return is_sent

    @classmethod
    async def notify_order_status_change(cls, order) -> bool:
        """Sends comprehensive order status notification to user."""
        status_emojis = {
            "PENDING": "⏳ Kutilmoqda",
            "WAITING_PAYMENT": "💳 To'lov kutilmoqda",
            "PAID": "💰 To'lov qabul qilindi",
            "PROCESSING": "⚙️ Buyurtma ishlanmoqda",
            "DELIVERING": "🚀 UC yuborilmoqda",
            "COMPLETED": "✅ Buyurtma muvaffaqiyatli yetkazildi!",
            "FAILED": "❌ Buyurtmada xatolik yuz berdi",
            "CANCELLED": "🚫 Buyurtma bekor qilindi",
            "REFUNDED": "🔄 To'lov qaytarildi (Refund)",
            "MANUAL_REVIEW": "🟡 Admin tekshiruvida",
        }

        status_text = status_emojis.get(order.status, order.status)

        text = (
            f"📦 <b>Buyurtma holati yangilandi!</b>\n\n"
            f"📦 <b>Buyurtma:</b> <code>{order.order_id}</code>\n"
            f"🎮 <b>O'yin:</b> PUBG Mobile\n"
            f"🆔 <b>Player ID:</b> <code>{order.player_id}</code>\n"
            f"👤 <b>Nickname:</b> {order.player_nickname or '—'}\n"
            f"💎 <b>Paket:</b> {order.product.name}\n"
            f"💰 <b>To'langan summa:</b> {order.final_amount:,.0f} UZS\n"
            f"💳 <b>To'lov turi:</b> {order.payment_method}\n"
            f"📊 <b>Status:</b> <b>{status_text}</b>\n"
        )

        if order.status == "COMPLETED":
            text += "\n🎉 <i>Xaridingiz uchun rahmat! UC profilingizga muvaffaqiyatli qo'shildi.</i>"
        elif order.status == "FAILED":
            text += f"\n⚠️ <i>Xatolik sababi: {order.error_message or 'Texnik nosozlik'}</i>\nIltimos, yordam uchun adminga murojaat qiling."
        elif order.status == "MANUAL_REVIEW":
            text += "\n⏳ <i>Buyurtmangiz admin tomonidan qo'lda ko'rib chiqilmoqda. Tez orada UC yuboriladi!</i>"

        return await cls.send_message(
            telegram_id=order.user.telegram_id,
            text=text,
            user=order.user,
            notification_type=NotificationLog.NotificationType.ORDER_STATUS,
        )

    @classmethod
    async def notify_admins(cls, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
        """Send notification to all bot administrators."""
        admin_ids = getattr(settings, "ADMIN_IDS", [])
        for admin_id in admin_ids:
            await cls.send_message(
                telegram_id=admin_id,
                text=f"🔔 <b>[ADMIN OGOHLANTIRISHI]</b>\n\n{text}",
                reply_markup=reply_markup,
                notification_type=NotificationLog.NotificationType.ADMIN_ALERT,
            )
