from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from utils.helpers import format_user_order_card, get_status_badge, DIVIDER
from keyboards.user import user_order_detail_keyboard, nav_back_home_keyboard
from emojis import E

router = Router()


@router.callback_query(F.data == "btn_my_orders")
async def user_orders_list(call: CallbackQuery):
    """Display user's recent orders with modern card list."""
    orders = await db.get_user_orders(call.from_user.id, limit=8)

    if not orders:
        text = (
            f"{DIVIDER}\n"
            f"   {E('order')} <b>MENING BUYURTMALARIM</b>\n"
            f"{DIVIDER}\n\n"
            f"Sizda hali hech qanday buyurtma mavjud emas.\n\n"
            f"O'yindagi hisobingizga bir zumda UC yuklash uchun quyidagi tugmani bosing 👇"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"{E('uc', True)} UC sotib olish", callback_data="btn_buy_uc")],
                [InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home")],
            ]
        )
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
        return

    text = (
        f"{DIVIDER}\n"
        f"   {E('order')} <b>SO'NGGI BUYURTMALARIM</b>\n"
        f"{DIVIDER}\n\n"
        f"Batafsil ma'lumot olish uchun buyurtmani tanlang 👇"
    )
    keyboard = []
    for o in orders:
        status_label = get_status_badge(o.get("status", ""))
        prod_name = o.get("product_name") or "UC"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{o['order_id']} • {prod_name} ({status_label})",
                callback_data=f"user_view_ord:{o['order_id']}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text=f"{E('uc', True)} Yangi buyurtma", callback_data="btn_buy_uc"),
        InlineKeyboardButton(text=f"{E('home', True)} Asosiy menyu", callback_data="btn_home"),
    ])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await call.answer()


@router.callback_query(F.data.startswith("user_view_ord:"))
async def view_order_detail(call: CallbackQuery):
    """View full user-facing card of an order."""
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)

    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    card = format_user_order_card(order)
    await call.message.edit_text(card, reply_markup=user_order_detail_keyboard(order_id))
    await call.answer()
