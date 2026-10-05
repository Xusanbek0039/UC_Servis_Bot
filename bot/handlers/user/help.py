from aiogram import Router, F
from aiogram.types import Message
from asgiref.sync import sync_to_async
from apps.settings.models import BotSettings

router = Router()


@router.message(F.text.in_(["📞 Yordam", "/help"]))
async def help_handler(message: Message):
    """Display customer support information."""
    settings_obj = await sync_to_async(BotSettings.load)()
    text = (
        f"📞 <b>Mijozlarni qo'llab-quvvatlash xizmati</b>\n\n"
        f"{settings_obj.help_text}\n\n"
        f"👤 <b>Operator (Admin):</b> {settings_obj.support_username}\n"
        f"📢 <b>Rasmiy kanalimiz:</b> {settings_obj.channel_username}\n\n"
        f"Ish vaqti: 24/7"
    )
    await message.answer(text)


@router.message(F.text.in_(["ℹ️ Biz haqimizda", "/about"]))
async def about_handler(message: Message):
    """Display information about the service."""
    settings_obj = await sync_to_async(BotSettings.load)()
    text = (
        f"ℹ️ <b>Biz haqimizda</b>\n\n"
        f"{settings_obj.about_text}\n\n"
        f"🛡 <b>Bizning afzalliklarimiz:</b>\n"
        f"• 100% rasmiy va xavfsiz to'lovlar\n"
        f"• Tezkor avtomatik yetkazib berish\n"
        f"• Har bir xarid uchun keshbek va bonuslar\n"
        f"• Malakali qo'llab-quvvatlash\n\n"
        f"Rasmiy kanal: {settings_obj.channel_username}"
    )
    await message.answer(text)
