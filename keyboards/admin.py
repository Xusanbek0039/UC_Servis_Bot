from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import format_currency
from emojis import E


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin dashboard navigation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{E('order', True)} Buyurtmalar", callback_data="adm_orders_menu"),
                InlineKeyboardButton(text=f"{E('payment', True)} To'lovlar", callback_data="adm_payments_menu"),
            ],
            [
                InlineKeyboardButton(text=f"{E('uc', True)} UC paketlar", callback_data="adm_products_menu"),
                InlineKeyboardButton(text=f"{E('users', True)} Foydalanuvchilar", callback_data="adm_users_menu"),
            ],
            [
                InlineKeyboardButton(text=f"{E('stats', True)} Statistika", callback_data="adm_stats"),
                InlineKeyboardButton(text=f"{E('settings', True)} Sozlamalar", callback_data="adm_settings_menu"),
            ],
            [InlineKeyboardButton(text="👑 Narxlar boshqaruvi", callback_data="adm_products_menu")],
            [InlineKeyboardButton(text="🔴/🟢 Global savdo", callback_data="adm_toggle_global_sales")],
            [
                InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="adm_exit"),
            ],
        ]
    )


def admin_orders_filter_keyboard() -> InlineKeyboardMarkup:
    """Filter orders by operational status."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟡 Kutilayotgan to'lovlar", callback_data="adm_ord_flt:WAITING_PAYMENT")],
            [InlineKeyboardButton(text="🔵 Jarayonda (Paid/Proc)", callback_data="adm_ord_flt:PAID")],
            [InlineKeyboardButton(text="🟢 Bajarilgan (Completed)", callback_data="adm_ord_flt:COMPLETED")],
            [InlineKeyboardButton(text="🔴 Bekor qilingan (Cancelled)", callback_data="adm_ord_flt:CANCELLED")],
            [InlineKeyboardButton(text="📋 Barcha oxirgi buyurtmalar", callback_data="adm_ord_flt:ALL")],
            [InlineKeyboardButton(text=f"{E('back', True)} Admin panel", callback_data="btn_admin_menu")],
        ]
    )


def admin_order_detail_keyboard(order: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Action buttons for admin to inspect and process orders."""
    status = order.get("status", "")
    order_id = order.get("order_id", "")
    buttons = []

    if status == "WAITING_PAYMENT":
        buttons.append([
            InlineKeyboardButton(text=f"{E('check', True)} To'lovni tasdiqlash", callback_data=f"adm_appr_ord:{order_id}"),
            InlineKeyboardButton(text=f"{E('cross', True)} Rad etish", callback_data=f"adm_rej_ord:{order_id}"),
        ])
    elif status in ("PAID", "PROCESSING", "MANUAL_REVIEW"):
        buttons.append([
            InlineKeyboardButton(text=f"{E('game', True)} UC yuborildi (Tugallash)", callback_data=f"adm_deliver_ord:{order_id}"),
            InlineKeyboardButton(text=f"{E('cross', True)} Bekor qilish", callback_data=f"adm_rej_ord:{order_id}"),
        ])

    # Proof Channel control button
    if order.get("proof_sent"):
        buttons.append([
            InlineKeyboardButton(text=f"{E('refresh', True)} Isbot postini yangilash", callback_data=f"adm_proof_upd:{order_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text=f"{E('proof', True)} Isbot kanaliga yuborish", callback_data=f"adm_proof_send:{order_id}")
        ])

    buttons.append([InlineKeyboardButton(text=f"{E('back', True)} Buyurtmalarga qaytish", callback_data="adm_orders_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_products_management_keyboard(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List products with add and back buttons."""
    buttons = []
    for p in products:
        icon = "🟢" if p.get("is_active") == 1 else "🔴"
        price_str = format_currency(p.get("price", 0))
        text = f"{icon} {p.get('name')} — {price_str}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"adm_prod_view:{p.get('id')}")])

    buttons.append([InlineKeyboardButton(text=f"{E('star', True)} Yangi paket qo'shish", callback_data="adm_add_product")])
    buttons.append([InlineKeyboardButton(text=f"{E('refresh', True)} LioGames narxlarini yangilash", callback_data="adm_supplier_refresh")])
    buttons.append([InlineKeyboardButton(text=f"{E('back', True)} Admin panel", callback_data="btn_admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_single_product_keyboard(product_id: int, is_active: int) -> InlineKeyboardMarkup:
    """Controls for a single product."""
    status_toggle_text = "🔴 Deaktiv qilish" if is_active == 1 else "🟢 Faollashtirish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{E('edit', True)} Narxni o'zgartirish", callback_data=f"adm_prod_chg_price:{product_id}"),
                InlineKeyboardButton(text=status_toggle_text, callback_data=f"adm_prod_toggle:{product_id}"),
            ],
            [InlineKeyboardButton(text="📈 Foizni o'zgartirish", callback_data=f"adm_profit:{product_id}"), InlineKeyboardButton(text="💰 Max narx", callback_data=f"adm_max_price:{product_id}")],
            [InlineKeyboardButton(text="⛔ Manual blok / 🟢 Ochish", callback_data=f"adm_manual_block:{product_id}")],
            [
                InlineKeyboardButton(text=f"{E('cross', True)} Paketni o'chirish", callback_data=f"adm_prod_del:{product_id}"),
                InlineKeyboardButton(text=f"{E('back', True)} Paketlar ro'yxatiga", callback_data="adm_products_menu"),
            ],
        ]
    )


def admin_settings_keyboard() -> InlineKeyboardMarkup:
    """Settings modification buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('card', True)} Karta raqamini o'zgartirish", callback_data="adm_set_card_num")],
            [InlineKeyboardButton(text=f"{E('profile', True)} Karta egasini o'zgartirish", callback_data="adm_set_card_owner")],
            [InlineKeyboardButton(text="🏦 Bank nomini o'zgartirish", callback_data="adm_set_bank_name")],
            [InlineKeyboardButton(text=f"{E('support', True)} Support username sozlash", callback_data="adm_set_support")],
            [InlineKeyboardButton(text=f"{E('proof', True)} Isbot kanal havolasini sozlash", callback_data="adm_set_proof_channel")],
            [InlineKeyboardButton(text=f"{E('refresh', True)} Yetkazish rejimini almashtirish", callback_data="adm_toggle_delivery")],
            [InlineKeyboardButton(text=f"{E('back', True)} Admin panel", callback_data="btn_admin_menu")],
        ]
    )
