from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import format_currency
from emojis import E


def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Symmetric, modern main navigation inline keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text=f"{E('uc', True)} UC SOTIB OLISH", callback_data="btn_buy_uc")
        ],
        [
            InlineKeyboardButton(text=f"{E('order', True)} Buyurtmalarim", callback_data="btn_my_orders"),
            InlineKeyboardButton(text=f"{E('balance', True)} Balansim", callback_data="btn_my_balance"),
        ],
        [
            InlineKeyboardButton(text=f"{E('profile', True)} Profil", callback_data="btn_profile"),
            InlineKeyboardButton(text=f"{E('support', True)} Yordam", callback_data="btn_help"),
        ],
    ]

    if is_admin:
        buttons.append([
            InlineKeyboardButton(text=f"{E('settings', True)} ADMIN PANEL", callback_data="btn_admin_menu")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard(callback_data: str = "btn_cancel") -> InlineKeyboardMarkup:
    """Single cancel inline button with clean red badge."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('cross', True)} Bekor qilish", callback_data=callback_data)]
        ]
    )


def nav_back_home_keyboard(back_callback: str = "btn_cancel") -> InlineKeyboardMarkup:
    """Standard back and home navigation pair."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{E('back', True)} Orqaga", callback_data=back_callback),
                InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home"),
            ]
        ]
    )


def player_confirm_keyboard() -> InlineKeyboardMarkup:
    """Player ID & Nickname confirmation card keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('check', True)} Tasdiqlash va davom etish", callback_data="confirm_player_id")],
            [InlineKeyboardButton(text=f"{E('refresh', True)} ID'ni o'zgartirish", callback_data="btn_buy_uc")],
            [InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home")],
        ]
    )


def products_keyboard(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Dynamic list of active UC packages styled as premium store cards.
    Popular and top packages are badged.
    """
    buttons = []
    for p in products:
        uc = p.get("uc_amount", 0)
        price_str = format_currency(p.get("price", 0))

        # Add visual badges to prominent tiers
        if uc == 660:
            badge = f"{E('fire', True)} "
            suffix = " (Popular)"
        elif uc == 1800:
            badge = f"{E('star', True)} "
            suffix = " (Top)"
        elif uc >= 8100:
            badge = f"{E('lightning', True)} "
            suffix = " (VIP)"
        else:
            badge = f"{E('uc', True)} "
            suffix = ""

        text = f"{badge}{p['name']} — {price_str}{suffix}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"buy_prod:{p['id']}")])

    buttons.append([
        InlineKeyboardButton(text=f"{E('refresh', True)} ID'ni o'zgartirish", callback_data="btn_buy_uc"),
        InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_methods_keyboard(user_balance: float, order_price: float) -> InlineKeyboardMarkup:
    """Payment methods selection with badges."""
    buttons = [
        [InlineKeyboardButton(text=f"{E('lightning', True)} Onlayn to'lov (Avtomatik)", callback_data="pay_method:TEZCHECK")],
        [InlineKeyboardButton(text=f"{E('visa', True)} Visa", callback_data="pay_method:VISA"), InlineKeyboardButton(text=f"{E('humo', True)} Humo", callback_data="pay_method:HUMO")],
        [InlineKeyboardButton(text=f"{E('mastercard', True)} Mastercard", callback_data="pay_method:MASTERCARD"), InlineKeyboardButton(text=f"{E('uzcard', True)} Uzcard", callback_data="pay_method:UZCARD")],
        [InlineKeyboardButton(text=f"{E('click', True)} Click", callback_data="pay_method:CLICK"), InlineKeyboardButton(text=f"{E('payme', True)} Payme", callback_data="pay_method:PAYME"), InlineKeyboardButton(text=f"{E('paynet', True)} Paynet", callback_data="pay_method:PAYNET")],
    ]

    if user_balance >= order_price:
        bal_str = format_currency(user_balance)
        buttons.insert(0, [
            InlineKeyboardButton(text=f"{E('balance', True)} Balansdan to'lash ({bal_str})", callback_data="pay_method:BALANCE")
        ])

    buttons.append([
        InlineKeyboardButton(text=f"{E('back', True)} Paketlarga qaytish", callback_data="back_to_products"),
        InlineKeyboardButton(text=f"{E('cross', True)} Bekor qilish", callback_data="btn_cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tezcheck_pay_keyboard(pay_url: str, order_id: str) -> InlineKeyboardMarkup:
    """TezCheck payment checkout link, status check, and fallback."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('lightning', True)} To'lovni davom ettirish", url=pay_url)],
            [InlineKeyboardButton(text=f"{E('refresh', True)} To'lovni tekshirish", callback_data=f"chk_pay:{order_id}")],
            [
                InlineKeyboardButton(text=f"{E('card', True)} Boshqa usul", callback_data=f"change_method:{order_id}"),
                InlineKeyboardButton(text=f"{E('cross', True)} Bekor qilish", callback_data=f"cancel_ord:{order_id}"),
            ],
        ]
    )


def balance_topup_keyboard(pay_url: str, topup_id: str) -> InlineKeyboardMarkup:
    """Checkout link and in-bot status refresh for a balance top-up."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('lightning', True)} To‘lov qilish", url=pay_url)],
            [InlineKeyboardButton(text=f"{E('refresh', True)} To‘lovni tekshirish", callback_data=f"check_topup:{topup_id}")],
            [InlineKeyboardButton(text=f"{E('back', True)} Balansga qaytish", callback_data="btn_my_balance")],
        ]
    )


def order_success_keyboard() -> InlineKeyboardMarkup:
    """Completion confirmation buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('uc', True)} Yana UC xarid qilish", callback_data="btn_buy_uc")],
            [
                InlineKeyboardButton(text=f"{E('order', True)} Buyurtmalarim", callback_data="btn_my_orders"),
                InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home"),
            ],
        ]
    )


def profile_keyboard() -> InlineKeyboardMarkup:
    """User profile actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{E('order', True)} Buyurtmalarim", callback_data="btn_my_orders"),
                InlineKeyboardButton(text=f"{E('balance', True)} Balansim", callback_data="btn_my_balance"),
            ],
            [InlineKeyboardButton(text=f"{E('uc', True)} UC sotib olish", callback_data="btn_buy_uc")],
            [InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home")],
        ]
    )


def balance_keyboard() -> InlineKeyboardMarkup:
    """Balance page actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{E('card', True)} Balansni to'ldirish", callback_data="btn_topup_balance"),
                InlineKeyboardButton(text=f"{E('uc', True)} UC sotib olish", callback_data="btn_buy_uc"),
            ],
            [InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home")],
        ]
    )


def support_keyboard(support_username: str = "") -> InlineKeyboardMarkup:
    """Support contact button."""
    clean_username = support_username.replace("@", "").strip() or "support"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('support', True)} Operator bilan bog'lanish", url=f"https://t.me/{clean_username}")],
            [InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home")],
        ]
    )


def user_order_detail_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Actions on viewing specific user order."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('refresh', True)} Holatni yangilash", callback_data=f"user_view_ord:{order_id}")],
            [
                InlineKeyboardButton(text=f"{E('back', True)} Buyurtmalar ro'yxati", callback_data="btn_my_orders"),
                InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home"),
            ],
        ]
    )
