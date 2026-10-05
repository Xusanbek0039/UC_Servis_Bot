from typing import List
from decimal import Decimal
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apps.products.models import Product


def cancel_inline(callback_data: str = "cancel_action") -> InlineKeyboardMarkup:
    """Returns a single cancel inline button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data=callback_data)]]
    )


def player_confirmation_inline() -> InlineKeyboardMarkup:
    """Confirmation buttons for PUBG player ID verification."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, davom etish", callback_data="confirm_player_yes"),
                InlineKeyboardButton(text="❌ Qayta kiritish", callback_data="confirm_player_no"),
            ],
            [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="cancel_action")],
        ]
    )


def products_inline(products: List[Product]) -> InlineKeyboardMarkup:
    """Dynamic list of active UC packages."""
    keyboard = []
    for p in products:
        price_str = f"{p.price:,.0f}".replace(",", " ")
        text = f"💎 {p.name} — {price_str} so'm"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"select_product:{p.id}")])

    keyboard.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def promo_prompt_inline() -> InlineKeyboardMarkup:
    """Prompt user whether they have a promo code or want to skip."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎟 Promo kod kiritish", callback_data="promo_enter"),
                InlineKeyboardButton(text="➡️ O'tkazib yuborish", callback_data="promo_skip"),
            ],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")],
        ]
    )


def payment_methods_inline(user_balance: Decimal, final_amount: Decimal) -> InlineKeyboardMarkup:
    """Payment methods selection keyboard."""
    buttons = [
        [InlineKeyboardButton(text="⚡️ TezCheck (Avtomatik to'lov)", callback_data="pay_method:TEZCHECK")],
        [InlineKeyboardButton(text="💳 Karta orqali qo'lda to'lov", callback_data="pay_method:MANUAL_CARD")],
    ]

    # Show balance option if user has sufficient funds
    if user_balance >= final_amount:
        bal_str = f"{user_balance:,.0f}".replace(",", " ")
        buttons.insert(
            0,
            [
                InlineKeyboardButton(
                    text=f"💰 Ichki balans orqali ({bal_str} UZS)", callback_data="pay_method:BALANCE"
                )
            ],
        )

    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tezcheck_pay_inline(payment_url: str, order_id: str) -> InlineKeyboardMarkup:
    """TezCheck checkout URL and verify buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lov sahifasiga o'tish", url=payment_url)],
            [InlineKeyboardButton(text="🔄 To'lovni tekshirish", callback_data=f"check_payment:{order_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_order:{order_id}")],
        ]
    )
