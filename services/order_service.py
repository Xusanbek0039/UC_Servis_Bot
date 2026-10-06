import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

import database as db
from config import ADMIN_IDS, LIOGAMES_AUTO_DELIVERY, LIOGAMES_STOP_ON_LOW_BALANCE, LOW_BALANCE_THRESHOLD
from keyboards.user import order_success_keyboard
from services.liogames import LioGamesService, LioGamesError
from services.proof_channel import ProofChannelService
from utils.helpers import format_currency, DIVIDER, SUB_DIVIDER
from emojis import E

logger = logging.getLogger("services.order")


class OrderService:
    @staticmethod
    async def notify_user(bot: Bot, telegram_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception:
            logger.warning("Unable to notify user id=%s", telegram_id)

    @staticmethod
    async def notify_admins(bot: Bot, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=f"🔔 <b>[ADMIN XABARNOMASI]</b>\n\n{text}", reply_markup=reply_markup, parse_mode="HTML")
            except Exception:
                logger.warning("Unable to deliver admin alert")

    @classmethod
    async def handle_payment_success(cls, bot: Bot, order_id: str, provider_tx_id: str = "") -> bool:
        """Settle payment once, then either enqueue manual fulfillment or call supplier safely."""
        order = await db.get_order(order_id)
        if not order:
            logger.error("Payment references unknown order %s", order_id)
            return False
        if order.get("payment_status") in ("REFUNDED", "EXPIRED") or order.get("status") in ("CANCELLED", "EXPIRED", "REFUNDED"):
            await db.update_payment_status(order_id, "LATE_PAYMENT_REVIEW", provider_tx_id)
            await cls.notify_admins(bot, f"⚠️ Kechikkan yoki qaytarilgan to'lov delivery'ga yuborilmadi. Order <code>{order_id}</code>.")
            return False
        if order.get("payment_status") != "SUCCESS":
            if not await db.mark_order_payment_success(order_id, provider_tx_id):
                order = await db.get_order(order_id)
                if not order or order.get("payment_status") != "SUCCESS":
                    return False
        await db.update_payment_status(order_id, "SUCCESS", provider_tx_id)

        delivery_state = order.get("delivery_status", "NOT_STARTED")
        if delivery_state == "COMPLETED":
            return True
        # Existing PROCESSING delivery is polled/reconciled, never submitted again.
        if delivery_state == "PROCESSING":
            return True
        if not await db.claim_delivery(order_id):
            return True

        mode = (await db.get_setting("delivery_mode", "MANUAL")).upper()
        if mode != "AUTO" or not LIOGAMES_AUTO_DELIVERY:
            await db.set_delivery_status(order_id, "PROCESSING")
            await db.update_order_status(order_id, "PAID")
            await cls.notify_admins(bot, cls._admin_order_text(order))
            await cls.notify_user(
                bot, order["user_id"],
                f"{DIVIDER}\n✅ <b>TO'LOV QABUL QILINDI</b>\n{DIVIDER}\n\n"
                f"📦 Buyurtma: <code>{order_id}</code>\n💎 Paket: {order.get('product_name')}\n"
                f"⏳ To'lov tasdiqlandi. Yetkazib berish holati yangilanganda xabar beramiz.",
                order_success_keyboard(),
            )
            return True

        try:
            if LIOGAMES_STOP_ON_LOW_BALANCE:
                balance_data = await LioGamesService.get_balance()
                wallet = float(balance_data.get("balance", balance_data.get("wallet_balance", 0)) or 0)
                if wallet < LOW_BALANCE_THRESHOLD:
                    await db.set_delivery_status(order_id, "FAILED", supplier_status="LOW_BALANCE", last_supplier_error="Supplier wallet below threshold")
                    await db.update_order_status(order_id, "MANUAL_REVIEW")
                    await cls.notify_admins(bot, f"⚠️ LioGames balansi ${wallet:.2f}; order <code>{order_id}</code> avtomatik yuborilmadi. Balansni to'ldiring yoki qo'lda yetkazing.")
                    await cls.notify_user(bot, order["user_id"], f"⚠️ To'lovingiz qabul qilindi, ammo supplier balansidagi vaqtinchalik muammo sabab buyurtma operator tekshiruviga yuborildi. Order: <code>{order_id}</code>.")
                    return False
            await db.mark_supplier_submission_started(order_id)
            # LioGames' client_ref is our immutable order_id. create_order does not blindly retry.
            result = await LioGamesService.create_order(
                order_id=order_id,
                product_id=order.get("supplier_product_id", ""),
                variation_id=order.get("supplier_variation_id", ""),
                player_id=order["player_id"],
            )
            nested = result.get("order") if isinstance(result.get("order"), dict) else result
            supplier_id = str(nested.get("order_id") or nested.get("id") or "")
            status = str(nested.get("status") or "PENDING").upper()
            await db.store_supplier_order(order_id, supplier_id, status, result)
            applied = await cls.apply_supplier_status(bot, order_id, result)
            if applied == "PROCESSING":
                await cls.notify_user(bot, order["user_id"], f"✅ To'lov qabul qilindi. UC supplier orqali yetkazilmoqda. Order: <code>{order_id}</code>. Yakunlangach xabar beramiz.")
            return status not in ("FAILED", "REJECTED", "CANCELLED")
        except LioGamesError as exc:
            if exc.retryable:
                # Ambiguous supplier result: leave PROCESSING for reference-based recovery.
                await db.set_delivery_status(order_id, "PROCESSING", supplier_submitted=True, supplier_status="UNKNOWN_RESULT", last_supplier_error=str(exc)[:250])
                await cls.notify_admins(bot, f"⚠️ LioGames natijasi noaniq; takroriy order yuborilmadi. <code>{order_id}</code>. Holatni qayta tekshiring.")
            else:
                await db.set_delivery_status(order_id, "FAILED", supplier_status="FAILED", last_supplier_error=str(exc)[:250])
                await db.update_order_status(order_id, "MANUAL_REVIEW")
                await cls.notify_admins(bot, f"❌ LioGames order xatosi: <code>{order_id}</code>. {str(exc)[:250]}")
                await cls.notify_user(bot, order["user_id"], f"⚠️ To'lov qabul qilindi, ammo yetkazishda muammo bor. Operator buyurtmangizni tekshirmoqda. Order: <code>{order_id}</code>.")
            return False

    @staticmethod
    def _admin_order_text(order: dict) -> str:
        return (
            f"🚨 <b>TO'LANGAN BUYURTMA — QO'LDA YETKAZISH</b>\n\n"
            f"📦 Order: <code>{order['order_id']}</code>\n"
            f"👤 User ID: <code>{order['user_id']}</code>\n"
            f"🆔 Player ID: <code>{order['player_id']}</code>\n"
            f"💎 Paket: {order.get('product_name')}\n💰 Summa: {format_currency(order.get('price', 0))}"
        )

    @classmethod
    async def apply_supplier_status(cls, bot: Bot, order_id: str, data: dict) -> str:
        existing_order = await db.get_order(order_id)
        nested = data.get("order") if isinstance(data.get("order"), dict) else data
        status = str(nested.get("status") or nested.get("order_status") or "UNKNOWN").upper()
        supplier_id = str(nested.get("order_id") or nested.get("id") or "")
        await db.store_supplier_order(order_id, supplier_id, status, data)
        if status in ("COMPLETED", "SUCCESS", "DONE"):
            updated = await db.complete_delivery_once(order_id, supplier_status=status, delivered_at=__import__("datetime").datetime.utcnow())
            if updated:
                order = await db.get_order(order_id)
                await ProofChannelService.send_or_update_proof(bot, order_id, "COMPLETED")
                if order:
                    await cls._notify_completed(bot, order)
            return "COMPLETED"
        if status in ("FAILED", "REJECTED", "CANCELLED", "ERROR"):
            await db.set_delivery_status(order_id, "FAILED", supplier_status=status)
            await db.update_order_status(order_id, "MANUAL_REVIEW")
            await cls.notify_admins(bot, f"❌ Supplier delivery failed. <code>{order_id}</code> status=<b>{status}</b>; operator tekshirishi kerak.")
            if existing_order:
                await cls.notify_user(bot, existing_order["user_id"], f"⚠️ Supplier buyurtmani yakunlay olmadi. Operator tekshiryapti. Order: <code>{order_id}</code>.")
            return "FAILED"
        if status in ("PENDING", "PROCESSING", "IN_PROGRESS", "QUEUED"):
            await db.set_delivery_status(order_id, "PROCESSING", supplier_status=status)
            await db.update_order_status(order_id, "PROCESSING")
            return "PROCESSING"
        await db.set_delivery_status(order_id, "PROCESSING", supplier_status="UNKNOWN")
        if not existing_order or existing_order.get("supplier_status") != "UNKNOWN":
            await cls.notify_admins(bot, f"⚠️ LioGames noma'lum status qaytardi. <code>{order_id}</code>; status qiymatini tekshiring.")
        return "UNKNOWN"

    @classmethod
    async def _notify_completed(cls, bot: Bot, order: dict):
        message = (
            f"{DIVIDER}\n✨ <b>BUYURTMA MUVAFFAQIYATLI BAJARILDI</b>\n{DIVIDER}\n\n"
            f"🎮 PUBG MOBILE\n💎 <b>{order.get('product_name')}</b>\n"
            f"🆔 Player ID: <code>{order.get('player_id')}</code>\n"
            f"📦 Order: <code>{order.get('order_id')}</code>\n{SUB_DIVIDER}\n"
            f"✅ Supplier UC yetkazilganini tasdiqladi. Rahmat!"
        )
        await cls.notify_user(bot, order["user_id"], message, order_success_keyboard())

    @classmethod
    async def mark_manual_delivered(cls, bot: Bot, order_id: str) -> bool:
        order = await db.get_order(order_id)
        if not order or order.get("payment_status") != "SUCCESS" or order.get("delivery_status") not in ("PROCESSING", "FAILED"):
            return False
        if not await db.complete_delivery_once(order_id, supplier_status="MANUAL_CONFIRMED", delivered_at=__import__("datetime").datetime.utcnow()):
            return False
        order = await db.get_order(order_id)
        await ProofChannelService.send_or_update_proof(bot, order_id=order_id, new_proof_status="COMPLETED")
        await cls._notify_completed(bot, order)
        return True
