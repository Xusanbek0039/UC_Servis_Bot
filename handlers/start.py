from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS
import database as db
from keyboards.user import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""

    # Register or update user in SQLite
    await db.get_or_create_user(telegram_id=user_id, username=username, first_name=first_name)

    is_admin = user_id in ADMIN_IDS

    text = (
        f"Assalomu alaykum, <b>{first_name}</b>!\n\n"
        f"🎮 <b>PUBG MOBILE UC DO'KONI</b>ga xush kelibsiz!\n\n"
        f"Kerakli bo'limni tanlang 👇"
    )

    await message.answer(text, reply_markup=main_menu_keyboard(is_admin=is_admin))


@router.callback_query(F.data == "btn_cancel")
async def cancel_callback(call: CallbackQuery, state: FSMContext):
    """Cancel current operation and return to main menu."""
    await state.clear()
    is_admin = call.from_user.id in ADMIN_IDS
    await call.message.delete()
    await call.message.answer("❌ Amal bekor qilindi.", reply_markup=main_menu_keyboard(is_admin=is_admin))
    await call.answer()


@router.callback_query(F.data == "adm_exit")
async def exit_admin_menu(call: CallbackQuery, state: FSMContext):
    """Return to user main menu."""
    await state.clear()
    is_admin = call.from_user.id in ADMIN_IDS
    await call.message.delete()
    await call.message.answer("Asosiy menyudasiz 👇", reply_markup=main_menu_keyboard(is_admin=is_admin))
    await call.answer()
