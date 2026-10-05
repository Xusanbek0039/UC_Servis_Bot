from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from apps.orders.models import Order

router = Router()


@router.message(F.text.in_(["📦 Buyurtmalarim", "/orders"]))
async def orders_list_handler(message: Message, db_user):
    """List recent orders of the user."""
    orders = await sync_to_async(list)(
        Order.objects.filter(user=db_user).order_by("-created_at")[:10]
    )

    if not orders:
        await message.answer(
            "📦 Sizda hali hech qanday buyurtma mavjud emas.\n"
            "UC xarid qilish uchun <b>🎮 PUBG UC</b> tugmasini bosing!"
        )
        return

    status_emojis = {
        "PENDING": "⏳",
        "WAITING_PAYMENT": "💳",
        "PAID": "💰",
        "PROCESSING": "⚙️",
        "DELIVERING": "🚀",
        "COMPLETED": "✅",
        "FAILED": "❌",
        "CANCELLED": "🚫",
        "REFUNDED": "🔄",
        "MANUAL_REVIEW": "🟡",
    }

    text = "📦 <b>Sizning so'nggi buyurtmalaringiz:</b>\n\n"
    keyboard = []

    for ord_item in orders:
        emo = status_emojis.get(ord_item.status, "ℹ️")
        dt_str = ord_item.created_at.strftime("%d.%m %H:%M")
        text += (
            f"{emo} <b>{ord_item.order_id}</b> — {ord_item.product.name}\n"
            f"   Narx: {ord_item.final_amount:,.0f} UZS | Status: <b>{ord_item.status}</b> ({dt_str})\n\n"
        )
        keyboard.append(
            [InlineKeyboardButton(text=f"🔍 {ord_item.order_id} tafsilotlari", callback_data=f"order_view:{ord_item.order_id}")]
        )

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("order_view:"))
async def order_detail_handler(call: CallbackQuery):
    """View details of a specific order."""
    order_id = call.data.split(":")[1]
    order = await sync_to_async(Order.objects.filter(order_id=order_id).select_related("product").first)()

    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    detail_text = (
        f"📦 <b>Buyurtma ma'lumotlari</b>\n\n"
        f"📦 <b>Buyurtma raqami:</b> <code>{order.order_id}</code>\n"
        f"🎮 <b>O'yin:</b> PUBG Mobile\n"
        f"🆔 <b>Player ID:</b> <code>{order.player_id}</code>\n"
        f"👤 <b>Nickname:</b> {order.player_nickname or '—'}\n"
        f"💎 <b>Paket:</b> {order.product.name} ({order.product.uc_amount} UC)\n"
        f"💰 <b>Summa:</b> {order.final_amount:,.0f} UZS\n"
        f"💳 <b>To'lov usuli:</b> {order.payment_method}\n"
        f"📊 <b>Status:</b> <b>{order.status}</b>\n"
        f"📅 <b>Sana:</b> {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    if order.provider_order_id:
        detail_text += f"🆔 <b>Provider TX ID:</b> <code>{order.provider_order_id}</code>\n"

    if order.error_message:
        detail_text += f"⚠️ <b>Izoh:</b> {order.error_message}\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Buyurtmalarga qaytish", callback_data="back_to_orders")]]
    )
    await call.message.edit_text(detail_text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "back_to_orders")
async def back_to_orders_callback(call: CallbackQuery, db_user):
    """Go back to user's orders list."""
    await call.message.delete()
    await orders_list_handler(call.message, db_user)
    await call.answer()
