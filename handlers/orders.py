from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from utils.helpers import format_order_summary, format_currency, get_status_emoji

router = Router()


@router.callback_query(F.data == "btn_my_orders")
async def user_orders_list(call: CallbackQuery):
    """Display user's recent orders."""
    orders = await db.get_user_orders(call.from_user.id, limit=8)

    if not orders:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="btn_cancel")]]
        )
        await call.message.edit_text("📦 Sizda hali hech qanday buyurtma mavjud emas.", reply_markup=kb)
        await call.answer()
        return

    text = "📦 <b>Sizning so'nggi buyurtmalaringiz:</b>\n\n"
    keyboard = []
    for o in orders:
        status_label = get_status_emoji(o["status"])
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{o['order_id']} | {o['product_name']} ({status_label})",
                    callback_data=f"ord_view:{o['order_id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="btn_cancel")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await call.answer()


@router.callback_query(F.data.startswith("ord_view:"))
async def view_order_detail(call: CallbackQuery):
    """View full details of an order."""
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)

    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    summary = format_order_summary(order)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Buyurtmalarga qaytish", callback_data="btn_my_orders")]]
    )
    await call.message.edit_text(summary, reply_markup=kb)
    await call.answer()
