from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_menu_inline() -> InlineKeyboardMarkup:
    """Admin dashboard navigation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
                InlineKeyboardButton(text="📦 Buyurtmalar", callback_data="admin_orders"),
            ],
            [
                InlineKeyboardButton(text="💳 Kutilayotgan To'lovlar", callback_data="admin_pending_payments"),
                InlineKeyboardButton(text="🔴 Manual Orders", callback_data="admin_manual_orders"),
            ],
            [
                InlineKeyboardButton(text="🎮 UC Paketlar", callback_data="admin_products"),
                InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users"),
            ],
            [
                InlineKeyboardButton(text="🎟 Promo Kodlar", callback_data="admin_promos"),
                InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings"),
            ],
            [
                InlineKeyboardButton(text="📋 Audit Loglar", callback_data="admin_logs"),
                InlineKeyboardButton(text="🚪 Chiqish", callback_data="admin_close"),
            ],
        ]
    )


def admin_order_actions_inline(order_id: str) -> InlineKeyboardMarkup:
    """Action buttons for admin when viewing a specific order."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ UC Yuborildi", callback_data=f"admin_deliver:{order_id}"),
                InlineKeyboardButton(text="🔄 Qayta urinish", callback_data=f"admin_retry:{order_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_cancel:{order_id}"),
                InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_orders"),
            ],
        ]
    )


def admin_payment_review_inline(manual_payment_id: int) -> InlineKeyboardMarkup:
    """Approve/Reject buttons for manual receipt review."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"adm_appr_pay:{manual_payment_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"adm_rej_pay:{manual_payment_id}"),
            ]
        ]
    )
