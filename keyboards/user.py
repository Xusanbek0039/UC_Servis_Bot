from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import format_currency


def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """User main navigation inline keyboard."""
    buttons = [
        [InlineKeyboardButton(text="🎮 UC sotib olish", callback_data="btn_buy_uc")],
        [
            InlineKeyboardButton(text="📦 Buyurtmalarim", callback_data="btn_my_orders"),
            InlineKeyboardButton(text="💰 Balansim", callback_data="btn_my_balance"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Yordam", callback_data="btn_help"),
            InlineKeyboardButton(text="📞 Admin", callback_data="btn_support"),
        ],
    ]

    if is_admin:
        buttons.append([InlineKeyboardButton(text="👑 Admin Boshqaruv", callback_data="btn_admin_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard(callback_data: str = "btn_cancel") -> InlineKeyboardMarkup:
    """Single cancel inline button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data=callback_data)]]
    )


def products_keyboard(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Dynamic list of active UC packages."""
    buttons = []
    for p in products:
        text = f"💎 {p['name']} — {format_currency(p['price'])}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"buy_prod:{p['id']}")])

    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="btn_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_methods_keyboard(user_balance: float, order_price: float) -> InlineKeyboardMarkup:
    """Payment methods keyboard."""
    buttons = [
        [InlineKeyboardButton(text="⚡ TezCheck (Avtomatik)", callback_data="pay_method:TEZCHECK")],
        [InlineKeyboardButton(text="💳 Karta orqali (Qo'lda)", callback_data="pay_method:MANUAL_CARD")],
    ]

    if user_balance >= order_price:
        bal_str = format_currency(user_balance)
        buttons.insert(0, [InlineKeyboardButton(text=f"💰 Balansdan to'lash ({bal_str})", callback_data="pay_method:BALANCE")])

    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="btn_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tezcheck_pay_keyboard(pay_url: str, order_id: str) -> InlineKeyboardMarkup:
    """TezCheck payment checkout link and verify button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov sahifasiga o'tish", url=pay_url)],
            [InlineKeyboardButton(text="🔄 To'lovni tekshirish", callback_data=f"chk_pay:{order_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_ord:{order_id}")],
        ]
    )
