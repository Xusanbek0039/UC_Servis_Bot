import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
import database as db

# Handlers
from handlers.start import router as start_router
from handlers.shop import router as shop_router
from handlers.payment import router as payment_router
from handlers.orders import router as orders_router
from handlers.profile import router as profile_router
from handlers.admin import router as admin_router
from services.payment_monitor import poll_pending_tezcheck_payments
from services.payment_monitor import poll_supplier_orders
from services.price_monitor import monitor_supplier, update_usd_rate, refresh_product_prices

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


async def main():
    logger.info("Initializing PUBG UC Top-Up Bot (MongoDB + Aiogram 3.x)...")

    # 1. Initialize MongoDB collections and indexes
    await db.init_db()

    # 2. Check Bot Token
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN aniqlanmadi! Iltimos, '.env' fayliga BOT_TOKEN kiriting.")
        return

    # 3. Create Bot and Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Register Routers
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(shop_router)
    dp.include_router(payment_router)
    dp.include_router(orders_router)
    dp.include_router(profile_router)

    # 5. Connect to Telegram API
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        bot_info = await bot.get_me()
        logger.info(f"Bot connected successfully as @{bot_info.username} (ID: {bot_info.id})")
        # Initialize live pricing before accepting product selections. On outage, prices freeze/block safely.
        await update_usd_rate()
        await refresh_product_prices(bot)
        background_tasks = [
            asyncio.create_task(poll_pending_tezcheck_payments(bot)),
            asyncio.create_task(poll_supplier_orders(bot)),
            asyncio.create_task(monitor_supplier(bot)),
        ]
        logger.info("Bot is ready and listening for events (Polling mode)...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Telegram API ulanishida xatolik: {e}")
    finally:
        for task in locals().get("background_tasks", []):
            task.cancel()
        for task in locals().get("background_tasks", []):
            try:
                await task
            except asyncio.CancelledError:
                pass
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
