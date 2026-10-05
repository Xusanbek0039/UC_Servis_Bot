from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from apps.orders.models import Order
from apps.orders.services import OrderService
from bot.keyboards.admin import admin_order_actions_inline

router = Router()


@router.callback_query(F.data.in_(["admin_orders", "admin_manual_orders"]))
async def list_admin_orders(call: CallbackQuery):
    """List orders for admin."""
    only_manual = call.data == "admin_manual_orders"

    def get_orders():
        qs = Order.objects.select_related("product", "user").order_by("-created_at")
        if only_manual:
            qs = qs.filter(status__in=[Order.Status.MANUAL_REVIEW, Order.Status.PROCESSING])
        return list(qs[:10])

    orders = await sync_to_async(get_orders)()

    title = "🔴 <b>Kutilayotgan Manual Buyurtmalar:</b>\n\n" if only_manual else "📦 <b>Oxirgi Buyurtmalar:</b>\n\n"

    if not orders:
        text = title + "<i>Hozircha hech qanday buyurtma mavjud emas.</i>"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")]]
        )
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
        return

    text = title
    keyboard = []
    for o in orders:
        keyboard.append(
            [InlineKeyboardButton(text=f"📦 {o.order_id} ({o.product.name} | {o.status})", callback_data=f"adm_ord_view:{o.order_id}")]
        )

    keyboard.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await call.answer()


@router.callback_query(F.data.startswith("adm_ord_view:"))
async def view_admin_order(call: CallbackQuery):
    """View detailed information of an order for admin with action buttons."""
    order_id = call.data.split(":")[1]

    def get_order():
        return Order.objects.select_related("user", "product").filter(order_id=order_id).first()

    order = await sync_to_async(get_order)()

    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    text = (
        f"<b>Order:</b>\n<code>{order.order_id}</code>\n\n"
        f"<b>User:</b>\n{order.user.display_name} (ID: <code>{order.user.telegram_id}</code>)\n\n"
        f"<b>Player ID:</b>\n<code>{order.player_id}</code>\n\n"
        f"<b>Nickname:</b>\n<b>{order.player_nickname or '—'}</b>\n\n"
        f"<b>Product:</b>\n{order.product.name}\n\n"
        f"<b>Price:</b>\n{order.final_amount:,.0f} UZS\n\n"
        f"<b>Payment:</b>\n{order.payment_method}\n\n"
        f"<b>Status:</b>\n<b>{order.status}</b>\n\n"
        f"<b>Delivery:</b>\n{order.provider} (Retries: {order.retry_count})\n"
    )

    if order.error_message:
        text += f"\n⚠️ <b>Xatolik:</b> <code>{order.error_message}</code>\n"

    await call.message.edit_text(text, reply_markup=admin_order_actions_inline(order.order_id))
    await call.answer()


@router.callback_query(F.data.startswith("admin_deliver:"))
async def admin_deliver_order(call: CallbackQuery, db_user):
    """Admin clicks UC Delivered."""
    order_id = call.data.split(":")[1]
    success, msg = await sync_to_async(OrderService.manual_deliver)(
        order_id=order_id,
        admin_identifier=db_user.display_name,
    )

    if success:
        await call.answer("✅ Buyurtma yetkazildi deb belgilandi!", show_alert=True)
        await view_admin_order(call)
    else:
        await call.answer(f"Xatolik: {msg}", show_alert=True)


@router.callback_query(F.data.startswith("admin_retry:"))
async def admin_retry_order(call: CallbackQuery):
    """Admin triggers retry delivery."""
    order_id = call.data.split(":")[1]
    await call.answer("🔄 Yetkazish qayta ishga tushirildi...")
    await sync_to_async(OrderService.execute_topup_delivery)(order_id)
    await view_admin_order(call)


@router.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel_order(call: CallbackQuery, db_user):
    """Admin cancels order."""
    order_id = call.data.split(":")[1]
    success, msg = await sync_to_async(OrderService.cancel_order)(
        order_id=order_id,
        reason="Admin panel orqali bekor qilindi",
        admin_identifier=db_user.display_name,
        refund=True,
    )
    if success:
        await call.answer("❌ Buyurtma bekor qilindi va mablag' qaytarildi.", show_alert=True)
        await view_admin_order(call)
    else:
        await call.answer(f"Xatolik: {msg}", show_alert=True)
