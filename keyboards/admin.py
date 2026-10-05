from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import format_currency


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin dashboard navigation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 Buyurtmalar", callback_data="adm_orders_menu"),
                InlineKeyboardButton(text="💳 To‘lovlar", callback_data="adm_payments_menu"),
            ],
            [
                InlineKeyboardButton(text="🎮 UC paketlar", callback_data="adm_products_menu"),
                InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm_users_menu"),
            ],
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats"),
                InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="adm_settings_menu"),
            ],
            [
                InlineKeyboardButton(text="🚪 Asosiy menyu", callback_data="adm_exit"),
            ],
        ]
    )


def admin_orders_filter_keyboard() -> InlineKeyboardMarkup:
    """Filter orders by operational status."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟡 Kutilayotgan to'lovlar", callback_data="adm_ord_flt:WAITING_PAYMENT")],
            [InlineKeyboardButton(text="🔵 Jarayonda (Paid/Proc)", callback_data="adm_ord_flt:PAID")],
            [InlineKeyboardButton(text="🟢 Tugallangan (Completed)", callback_data="adm_ord_flt:COMPLETED")],
            [InlineKeyboardButton(text="🔴 Bekor qilingan (Cancelled)", callback_data="adm_ord_flt:CANCELLED")],
            [InlineKeyboardButton(text="📋 Barcha oxirgi buyurtmalar", callback_data="adm_ord_flt:ALL")],
            [InlineKeyboardButton(text="🔙 Admin menyu", callback_data="btn_admin_menu")],
        ]
    )


def admin_order_detail_keyboard(order: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Actions on specific order."""
    status = order.get("status", "")
    order_id = order.get("order_id", "")
    buttons = []

    if status == "WAITING_PAYMENT":
        buttons.append([
            InlineKeyboardButton(text="✅ To‘lovni tasdiqlash", callback_data=f"adm_appr_ord:{order_id}"),
            InlineKeyboardButton(text="❌ To‘lovni rad etish", callback_data=f"adm_rej_ord:{order_id}"),
        ])
    elif status in ("PAID", "PROCESSING", "MANUAL_REVIEW"):
        buttons.append([
            InlineKeyboardButton(text="🎮 UC yuborildi (Completed)", callback_data=f"adm_deliver_ord:{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm_rej_ord:{order_id}"),
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Buyurtmalarga qaytish", callback_data="adm_orders_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_products_management_keyboard(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List products with add and back buttons."""
    buttons = []
    for p in products:
        icon = "🟢" if p.get("is_active") == 1 else "🔴"
        text = f"{icon} {p.get('name')} — {format_currency(p.get('price', 0))}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"adm_prod_view:{p.get('id')}")])

    buttons.append([InlineKeyboardButton(text="➕ Yangi paket qo'shish", callback_data="adm_add_product")])
    buttons.append([InlineKeyboardButton(text="🔙 Admin menyu", callback_data="btn_admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_single_product_keyboard(product_id: int, is_active: int) -> InlineKeyboardMarkup:
    """Controls for a single product."""
    status_toggle_text = "🔴 Deaktiv qilish" if is_active == 1 else "🟢 Faollashtirish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Narxni o'zgartirish", callback_data=f"adm_prod_chg_price:{product_id}"),
                InlineKeyboardButton(text=status_toggle_text, callback_data=f"adm_prod_toggle:{product_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Paketni o'chirish", callback_data=f"adm_prod_del:{product_id}"),
                InlineKeyboardButton(text="🔙 Paketlar ro'yxatiga", callback_data="adm_products_menu"),
            ],
        ]
    )


def admin_settings_keyboard() -> InlineKeyboardMarkup:
    """Settings modification buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Karta raqamini o'zgartirish", callback_data="adm_set_card_num")],
            [InlineKeyboardButton(text="👤 Karta egasini o'zgartirish", callback_data="adm_set_card_owner")],
            [InlineKeyboardButton(text="🏦 Bank nomini o'zgartirish", callback_data="adm_set_bank_name")],
            [InlineKeyboardButton(text="📞 Support username'ni o'zgartirish", callback_data="adm_set_support")],
            [InlineKeyboardButton(text="🔧 Delivery mode (AUTO/MANUAL) almashtirish", callback_data="adm_set_delivery_mode")],
            [InlineKeyboardButton(text="🔙 Admin menyu", callback_data="btn_admin_menu")],
        ]
    )
