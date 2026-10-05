from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from apps.users.services import UserService
from apps.settings.models import BotSettings
from bot.keyboards.reply import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject, state: FSMContext, db_user):
    """Handle /start command with deep link referral tracking."""
    await state.clear()
    args = command.args

    if args and args.startswith("ref_"):
        ref_id_str = args.replace("ref_", "")
        if ref_id_str.isdigit() and int(ref_id_str) != message.from_user.id:
            await sync_to_async(UserService.get_or_create_user)(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                referrer_telegram_id=int(ref_id_str),
            )

    greeting = (
        f"Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
        f"🎮 <b>PUBG MOBILE UC RASMIY DO'KONI</b>ga xush kelibsiz!\n\n"
        f"Bu yerda siz o'z PUBG Mobile akkauntingiz uchun tezkor, ishonchli va eng hamyonbop narxlarda "
        f"UC xarid qilishingiz mumkin.\n\n"
        f"Boshlash uchun quyidagi tugmalardan birini tanlang 👇"
    )

    await message.answer(
        greeting,
        reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
    )
