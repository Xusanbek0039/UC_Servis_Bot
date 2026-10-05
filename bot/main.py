import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure root directory is on PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from aiogram import Dispatcher
from bot.loader import bot, dp
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.user_middleware import UserMiddleware
from bot.middlewares.admin_middleware import AdminMiddleware

# User Handlers
from bot.handlers.user.cancel import router as cancel_router
from bot.handlers.user.start import router as start_router
from bot.handlers.user.buy_uc import router as buy_uc_router
from bot.handlers.user.balance import router as balance_router
from bot.handlers.user.orders import router as orders_router
from bot.handlers.user.help import router as help_router

# Admin Handlers
from bot.handlers.admin.main import router as admin_main_router
from bot.handlers.admin.orders import router as admin_orders_router
from bot.handlers.admin.payments import router as admin_payments_router
from bot.handlers.admin.products import router as admin_products_router
from bot.handlers.admin.users import router as admin_users_router

# Initial product seeding
from apps.products.services import ProductService

logger = logging.getLogger("bot")


def register_middlewares(dp: Dispatcher):
    """Register all global middlewares."""
    dp.message.outer_middleware(ThrottlingMiddleware(rate_limit=0.5))
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())

    # Protect admin routers
    admin_middleware = AdminMiddleware()
    admin_main_router.message.middleware(admin_middleware)
    admin_main_router.callback_query.middleware(admin_middleware)
    admin_orders_router.callback_query.middleware(admin_middleware)
    admin_payments_router.callback_query.middleware(admin_middleware)
    admin_products_router.callback_query.middleware(admin_middleware)
    admin_users_router.callback_query.middleware(admin_middleware)


def register_routers(dp: Dispatcher):
    """Register all routers in priority order."""
    # Cancel router must be first so cancellation works in any state
    dp.include_router(cancel_router)

    # Admin routers
    dp.include_router(admin_main_router)
    dp.include_router(admin_orders_router)
    dp.include_router(admin_payments_router)
    dp.include_router(admin_products_router)
    dp.include_router(admin_users_router)

    # User routers
    dp.include_router(start_router)
    dp.include_router(buy_uc_router)
    dp.include_router(balance_router)
    dp.include_router(orders_router)
    dp.include_router(help_router)


async def main():
    """Main Telegram bot runner function."""
    from asgiref.sync import sync_to_async
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting PUBG UC Top-Up Telegram Bot...")

    # Seed default UC products if empty (wrapped in sync_to_async)
    await sync_to_async(ProductService.seed_default_products)()

    register_middlewares(dp)
    register_routers(dp)

    # Connect and start polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        bot_info = await bot.get_me()
        logger.info(f"Bot connected successfully as @{bot_info.username} (ID: {bot_info.id})")
        logger.info("Bot is ready and listening for events (Polling mode)...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(
            f"Telegram API ga ulanishda xatolik: {e}\n"
            f"Iltimos, '.env' faylidagi BOT_TOKEN to'g'ri kiritilganligini tekshiring!"
        )


if __name__ == "__main__":
    try:
        # Pre-seed synchronously before starting event loop
        ProductService.seed_default_products()
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
