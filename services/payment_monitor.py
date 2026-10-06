import asyncio
import json
import logging
from typing import Any, Dict

from aiogram import Bot

import database as db
from services.order_service import OrderService
from services.tezcheck import TezCheckService
from utils.helpers import format_currency
from services.liogames import LioGamesService, LioGamesError
from config import LIOGAMES_STATUS_INTERVAL, LIOGAMES_AUTO_DELIVERY

logger = logging.getLogger("services.payment_monitor")


async def check_tezcheck_payment(bot: Bot, payment: Dict[str, Any], notify_user: bool = True) -> str:
    """Check one pending bill and settle it only for a matching live payment."""
    reference = payment.get("order_id", "")
    bill_id = payment.get("bill_id", "")
    if not reference or not bill_id:
        return "invalid"

    ok, result, error = await TezCheckService.get_bill(bill_id)
    if not ok:
        logger.warning("Payment status check failed for %s: %s", reference, error)
        return "error"

    bill = result.get("bill") or {}
    provider_payment = result.get("payment") or {}
    paid_amount = int(provider_payment.get("amount_minor", 0) or 0)
    expected_amount = int(payment.get("amount_minor", round(float(payment.get("amount", 0)) * 100)))

    # Test payments must never credit a wallet or trigger UC delivery.
    live_payment = (
        bill.get("livemode") is True
        or bill.get("environment") == "live"
        or provider_payment.get("livemode") is True
        or provider_payment.get("environment") == "live"
    )
    if bill.get("paid") is not True or provider_payment.get("state") != "succeeded" or not live_payment:
        if str(provider_payment.get("state", "")).lower() in ("refunded", "refund", "chargeback"):
            await db.update_payment_status(reference, "REFUNDED", json.dumps(result, ensure_ascii=False))
            await db.get_db().orders.update_one({"order_id": reference, "delivery_status": "NOT_STARTED"}, {"$set": {"payment_status": "REFUNDED", "status": "REFUNDED"}})
            return "refunded"
        return "pending"
    if paid_amount != expected_amount or bill.get("currency", "UZS") != "UZS":
        logger.error(
            "Paid bill does not match expected amount/currency: ref=%s expected=%s got=%s currency=%s",
            reference, expected_amount, paid_amount, bill.get("currency"),
        )
        return "mismatch"

    raw_data = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if payment.get("status") == "EXPIRED":
        await db.update_payment_status(reference, "LATE_PAYMENT_REVIEW", raw_data)
        for admin_id in __import__("config").ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"⚠️ Muddati o'tgan TezCheck hisobiga kech to'lov tushdi; avtomatik balans/order berilmadi: {reference}")
            except Exception:
                pass
        return "late_payment"
    if payment.get("payment_type") == "BALANCE_TOPUP":
        credited = await db.credit_topup_if_pending(reference, raw_data)
        if not credited:
            return "already_processed"
        telegram_id = credited.get("telegram_id")
        amount = float(credited.get("amount", 0))
        if notify_user:
            try:
                await bot.send_message(
                    telegram_id,
                    f"✅ <b>Balans to‘ldirildi!</b>\n\n{format_currency(amount)} hisobingizga qo‘shildi.",
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception("Could not notify user about top-up %s", reference)
        return "paid"

    order = await db.get_order(reference)
    if order and (order.get("payment_status") == "EXPIRED" or order.get("status") in ("EXPIRED", "CANCELLED", "REFUNDED")):
        await db.update_payment_status(reference, "LATE_PAYMENT_REVIEW", raw_data)
        for admin_id in __import__("config").ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"⚠️ Muddati o'tgan buyurtmaga kech to'lov tushdi, avtomatik yetkazilmadi: {reference}")
            except Exception:
                pass
        return "late_payment"
    if not await db.mark_payment_paid_if_pending(reference, raw_data, str(provider_payment.get("id", ""))):
        if payment.get("status") == "SUCCESS":
            await OrderService.handle_payment_success(bot, order_id=reference, provider_tx_id=str(provider_payment.get("id", "")))
        return "already_processed"
    await OrderService.handle_payment_success(bot, order_id=reference, provider_tx_id=str((result.get("payment") or {}).get("id", "")))
    return "paid"


async def poll_supplier_orders(bot: Bot) -> None:
    """Recover unresolved supplier work after restart without resubmitting orders."""
    while True:
        try:
            await db.expire_unpaid_orders()
            if LIOGAMES_AUTO_DELIVERY and LioGamesService.configured():
                for order in await db.get_recoverable_supplier_orders():
                    try:
                        result = await LioGamesService.get_order_status(
                            supplier_order_id=order.get("supplier_order_id", ""),
                            client_ref=order["order_id"],
                        )
                        await OrderService.apply_supplier_status(bot, order["order_id"], result)
                    except LioGamesError as exc:
                        logger.warning("Supplier status poll failed for %s (%s)", order.get("order_id"), type(exc).__name__)
        except Exception:
            logger.exception("Supplier recovery cycle failed")
        await asyncio.sleep(LIOGAMES_STATUS_INTERVAL)


async def poll_pending_tezcheck_payments(bot: Bot) -> None:
    """Background poller used by the bot process; Render webhook is not needed."""
    while True:
        try:
            pending = await db.get_pending_tezcheck_payments()
            for payment in pending:
                try:
                    await check_tezcheck_payment(bot, payment)
                except Exception:
                    logger.exception("Unhandled error while checking payment %s", payment.get("order_id"))
        except Exception:
            logger.exception("Could not load pending TezCheck payments")
        await asyncio.sleep(15)
