from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS
import database as db
from keyboards.user import main_menu_keyboard
from utils.helpers import DIVIDER
from emojis import E

router = Router()


def get_welcome_text(first_name: str) -> str:
    """Generates premium gaming welcome message."""
    return (
        f"{DIVIDER}\n"
        f"   {E('uc')} <b>PUBG MOBILE UC STORE</b>\n"
        f"{DIVIDER}\n\n"
        f"Assalomu alaykum, <b>{first_name}</b>!\n\n"
        f"{E('game')} <b>Rasmiy va tezkor PUBG Mobile UC xarid qilish xizmati.</b>\n\n"
        f"{E('lightning')} <b>Tezkor yetkazib berish</b> — 1-5 daqiqa\n"
        f"{E('payment')} <b>Xavfsiz to'lov</b> — TezCheck & Karta\n"
        f"{E('verified')} <b>Kafolatlangan xizmat</b> — 100% ishonchli\n\n"
        f"Kerakli bo'limni tanlang 👇"
    )


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Foydalanuvchi"

    # Register or update user in MongoDB
    await db.get_or_create_user(telegram_id=user_id, username=username, first_name=first_name)

    is_admin = user_id in ADMIN_IDS
    await message.answer(get_welcome_text(first_name), reply_markup=main_menu_keyboard(is_admin=is_admin))


@router.callback_query(F.data.in_({"btn_cancel", "btn_home", "adm_exit"}))
async def return_to_main_menu(call: CallbackQuery, state: FSMContext):
    """Cancel operation or return to main menu from any sub-state."""
    await state.clear()
    is_admin = call.from_user.id in ADMIN_IDS
    first_name = call.from_user.first_name or "Foydalanuvchi"

    try:
        await call.message.edit_text(get_welcome_text(first_name), reply_markup=main_menu_keyboard(is_admin=is_admin))
    except Exception:
        await call.message.delete()
        await call.message.answer(get_welcome_text(first_name), reply_markup=main_menu_keyboard(is_admin=is_admin))

    await call.answer()
