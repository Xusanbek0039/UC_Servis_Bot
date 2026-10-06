"""Refresh USD and supplier prices; retain last good values on any outage."""
import asyncio
import html
import logging
from datetime import datetime

import httpx

import database as db
from config import (ADMIN_IDS, LIOGAMES_PRODUCT_MAP, LIOGAMES_PRICE_TIER,
                    LOW_BALANCE_THRESHOLD, USD_RATE_INTERVAL_HOURS, USD_RATE_URL)
from services.liogames import LioGamesService, LioGamesError
from services.pricing import calculate_price

logger = logging.getLogger("services.price_monitor")


def _find_variation_price(data, variation_id: str, tier: str):
    if isinstance(data, dict):
        vid = str(data.get("variation_id", data.get("id", "")))
        if vid == str(variation_id):
            available = data.get("available", data.get("is_available", True))
            if available is False:
                return None
            for key in (tier.lower(), tier, f"{tier.lower()}_price", f"price_{tier.lower()}", "price_usd", "price", "amount"):
                if data.get(key) is not None:
                    try:
                        raw_value = data[key]
                        if isinstance(raw_value, dict):
                            raw_value = raw_value.get("amount", raw_value.get("price", raw_value.get("value", 0)))
                        value = float(raw_value)
                        return value if value > 0 else None
                    except (TypeError, ValueError):
                        pass
            prices = data.get("prices")
            if isinstance(prices, dict):
                for key in (tier.lower(), tier, f"{tier.lower()}_price", f"price_{tier.lower()}"):
                    raw_value = prices.get(key)
                    if isinstance(raw_value, dict):
                        raw_value = raw_value.get("amount", raw_value.get("price", raw_value.get("value")))
                    try:
                        value = float(raw_value)
                        if value > 0:
                            return value
                    except (TypeError, ValueError):
                        pass
        for key, value in data.items():
            if str(key) == str(variation_id):
                if isinstance(value, (int, float, str)):
                    try:
                        found = float(value)
                    except (TypeError, ValueError):
                        found = None
                else:
                    found = _find_variation_price({"variation_id": key, **value} if isinstance(value, dict) else value, variation_id, tier)
                if found:
                    return found
            found = _find_variation_price(value, variation_id, tier)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_variation_price(value, variation_id, tier)
            if found:
                return found
    return None


async def update_usd_rate(bot=None) -> bool:
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(USD_RATE_URL)
            response.raise_for_status()
            data = response.json()
        if isinstance(data, list):
            usd_item = next((item for item in data if item.get("Ccy") == "USD"), {})
            rate = float(str(usd_item.get("Rate", "0")).replace(",", ""))
        else:
            rate = float((data.get("rates") or {}).get("UZS", 0))
        if not (1000 < rate < 100000):
            raise ValueError("USD/UZS rate is outside accepted range")
        await db.set_setting("usd_rate", str(rate))
        await db.set_setting("usd_rate_updated_at", datetime.utcnow().isoformat())
        await db.set_setting("usd_rate_alerted", "false")
        return True
    except Exception as exc:
        logger.warning("USD rate refresh failed (%s); retaining last known value", type(exc).__name__)
        if bot and await db.get_setting("usd_rate_alerted", "false") != "true":
            await _alert_admins(bot, "⚠️ USD kursini CBU'dan yangilab bo'lmadi. Oxirgi yaroqli kurs saqlanmoqda.")
            await db.set_setting("usd_rate_alerted", "true")
        return False


async def refresh_product_prices(bot=None) -> None:
    if await db.get_pricing_mode() == "MANUAL":
        return
    rate = float(await db.get_setting("usd_rate", "0") or 0)
    for product in await db.get_all_products():
        mapping = LIOGAMES_PRODUCT_MAP.get(str(product.get("uc_amount")), {})
        if not mapping or not mapping.get("product_id") or not mapping.get("variation_id"):
            await db.set_product_pricing(product["id"], auto_block_reason="SUPPLIER_UNAVAILABLE", supplier_error="LIOGAMES_VARIATION_MAPPING_MISSING")
            continue
        if rate <= 0:
            await db.set_product_pricing(product["id"], auto_block_reason="SUPPLIER_UNAVAILABLE", supplier_error="USD_RATE_MISSING")
            continue
        try:
            previous_reason = product.get("auto_block_reason", "")
            matrix = await LioGamesService.get_product_price(str(mapping["product_id"]))
            usd_cost = _find_variation_price(matrix, str(mapping["variation_id"]), LIOGAMES_PRICE_TIER)
            if not usd_cost:
                raise LioGamesError(f"PRICE_NOT_FOUND: product={mapping['product_id']} variation={mapping['variation_id']} tier={LIOGAMES_PRICE_TIER}")
            quote = calculate_price(usd_cost, rate, product.get("profit_percent", 0), product.get("max_price", 0))
            await db.set_product_pricing(
                product["id"], supplier_product_id=str(mapping["product_id"]),
                supplier_variation_id=str(mapping["variation_id"]), supplier_price_usd=usd_cost,
                cost_price=float(quote.cost_uzs), price=float(quote.sale_price), supplier_error="",
                auto_block_reason=quote.blocked_reason,
            )
            if quote.blocked_reason and quote.blocked_reason != previous_reason and bot:
                await _alert_admins(bot, f"🔴 {product['name']} narxi max_price'dan oshdi; paket vaqtincha bloklandi.")
        except Exception as exc:
            detail = str(exc) if isinstance(exc, LioGamesError) else type(exc).__name__
            safe_detail = detail[:180]
            logger.warning("Price refresh failed for product %s: %s", product.get("id"), safe_detail)
            if product.get("auto_block_reason") != "SUPPLIER_UNAVAILABLE" and bot:
                await _alert_admins(bot, f"⚠️ {product.get('name')} uchun LioGames narxi olinmadi; paket vaqtincha bloklandi. Sabab kodi: <code>{html.escape(safe_detail)}</code>")
            await db.set_product_pricing(product["id"], auto_block_reason="SUPPLIER_UNAVAILABLE", supplier_error=safe_detail)


async def _alert_admins(bot, message: str):
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, message)
        except Exception:
            logger.debug("Could not deliver operational alert to an admin")


async def monitor_supplier(bot) -> None:
    last_rate = 0.0
    last_prices = 0.0
    last_balance = 0.0
    while True:
        now = asyncio.get_running_loop().time()
        if now - last_rate >= USD_RATE_INTERVAL_HOURS * 3600:
            await update_usd_rate(bot)
            last_rate = now
        if now - last_prices >= 300:
            await refresh_product_prices(bot)
            last_prices = now
        if now - last_balance >= 300 and LioGamesService.configured():
            try:
                balance = await LioGamesService.get_balance()
                amount = float(balance.get("balance", balance.get("wallet_balance", 0)) or 0)
                if amount < LOW_BALANCE_THRESHOLD:
                    if await db.get_setting("supplier_low_balance_alerted", "false") != "true":
                        await _alert_admins(bot, f"⚠️ LioGames balans past: ${amount:.2f} (chegara ${LOW_BALANCE_THRESHOLD:.2f}).")
                        await db.set_setting("supplier_low_balance_alerted", "true")
                else:
                    await db.set_setting("supplier_low_balance_alerted", "false")
            except Exception as exc:
                logger.warning("LioGames balance check failed (%s)", type(exc).__name__)
            last_balance = now
        await asyncio.sleep(30)
