from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from django.conf import settings


class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("db_user")
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        is_admin = False
        if user_id and user_id in getattr(settings, "ADMIN_IDS", []):
            is_admin = True
        elif user and user.is_admin:
            is_admin = True

        if not is_admin:
            if isinstance(event, Message):
                await event.answer("⛔️ Bu buyruq faqat bot administratorlari uchun ruxsat etilgan!")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔️ Ruxsat berilmagan amal!", show_alert=True)
            return None

        return await handler(event, data)
