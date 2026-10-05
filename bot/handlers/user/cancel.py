from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.keyboards.reply import main_menu_keyboard

router = Router()


@router.message(F.text == "❌ Bekor qilish")
async def cancel_message_handler(message: Message, state: FSMContext, db_user):
    """Handle text cancel button at any state."""
    await state.clear()
    await message.answer(
        "❌ Amal bekor qilindi. Asosiy menyudasiz.",
        reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
    )


@router.callback_query(F.data == "cancel_action")
async def cancel_callback_handler(call: CallbackQuery, state: FSMContext, db_user):
    """Handle inline cancel button at any state."""
    await state.clear()
    await call.message.delete()
    await call.message.answer(
        "❌ Amal bekor qilindi.",
        reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
    )
    await call.answer()
