from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from django.conf import settings
from apps.users.services import UserService
from apps.settings.models import BotSettings


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        telegram_user = None
        if isinstance(event, Message):
            telegram_user = event.from_user
        elif isinstance(event, CallbackQuery):
            telegram_user = event.from_user

        if not telegram_user:
            return await handler(event, data)

        # Check admin ID list
        is_admin_id = telegram_user.id in getattr(settings, "ADMIN_IDS", [])

        # Sync user in Django DB (synchronous ORM in thread or direct call)
        from asgiref.sync import sync_to_async

        user, created = await sync_to_async(UserService.get_or_create_user)(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        if is_admin_id and not user.is_admin:
            user.is_admin = True
            await sync_to_async(user.save)(update_fields=["is_admin"])

        # Check banned
        if user.is_banned:
            if isinstance(event, Message):
                await event.answer("🚫 Sizning hisobingiz bloklangan. Administratorga murojaat qiling.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Sizning hisobingiz bloklangan.", show_alert=True)
            return None

        # Check Maintenance mode
        bot_settings = await sync_to_async(BotSettings.load)()
        if bot_settings.maintenance_mode and not user.is_admin:
            msg = "🔧 <b>Botda texnik ta'mirlash ishlari olib borilmoqda!</b>\nTez orada xizmatimiz qayta tiklanadi."
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer("🔧 Botda texnik ta'mirlash ishlari bormoqda.", show_alert=True)
            return None

        data["db_user"] = user
        data["bot_settings"] = bot_settings
        return await handler(event, data)
