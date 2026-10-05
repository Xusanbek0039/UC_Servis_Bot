from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Creates the user-friendly persistent main menu keyboard."""
    buttons = [
        [KeyboardButton(text="🎮 PUBG UC")],
        [KeyboardButton(text="💰 Balansim"), KeyboardButton(text="📦 Buyurtmalarim")],
        [KeyboardButton(text="💳 To‘lov qilish"), KeyboardButton(text="📞 Yordam")],
        [KeyboardButton(text="ℹ️ Biz haqimizda")],
    ]

    if is_admin:
        buttons.append([KeyboardButton(text="👑 Admin Panel")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Quyidagi bo'limlardan birini tanlang 👇",
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel operation keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )
