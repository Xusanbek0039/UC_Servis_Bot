from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from apps.payments.models import ManualPayment
from apps.payments.services import PaymentService
from bot.keyboards.admin import admin_payment_review_inline

router = Router()


@router.callback_query(F.data == "admin_pending_payments")
async def list_pending_manual_payments(call: CallbackQuery):
    """List pending checks/screenshots awaiting review."""
    pending_checks = await sync_to_async(list)(
        ManualPayment.objects.filter(status=ManualPayment.ManualStatus.PENDING)
        .select_related("payment", "payment__order", "payment__user")
        .order_by("-created_at")[:10]
    )

    if not pending_checks:
        text = "💳 <b>Kutilayotgan to'lov cheklari mavjud emas!</b>"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")]]
        )
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
        return

    text = "💳 <b>Tasdiqlash kutilayotgan cheklar ro'yxati:</b>\n\n"
    keyboard = []
    for chk in pending_checks:
        amt = chk.payment.amount
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"Chek #{chk.id} — {amt:,.0f} UZS ({chk.payment.user.display_name})",
                    callback_data=f"adm_chk_view:{chk.id}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await call.answer()


@router.callback_query(F.data.startswith("adm_chk_view:"))
async def view_check_detail(call: CallbackQuery):
    """View receipt check details with approve/reject buttons."""
    check_id = int(call.data.split(":")[1])
    chk = await sync_to_async(
        ManualPayment.objects.filter(id=check_id)
        .select_related("payment", "payment__order", "payment__user", "payment__order__product")
        .first
    )()

    if not chk:
        await call.answer("Chek topilmadi!", show_alert=True)
        return

    order = chk.payment.order
    user = chk.payment.user

    text = (
        f"🟡 <b>TO'LOV CHEKI #{chk.id}</b>\n\n"
        f"📦 <b>Buyurtma:</b> <code>{order.order_id if order else '—'}</code>\n"
        f"👤 <b>Foydalanuvchi:</b> {user.display_name} (ID: <code>{user.telegram_id}</code>)\n"
        f"💰 <b>Summa:</b> <b>{chk.payment.amount:,.0f} UZS</b>\n"
        f"💳 <b>Karta:</b> {chk.card_number} ({chk.card_owner})\n"
        f"🎮 <b>Player:</b> {order.player_nickname if order else ''} (ID: <code>{order.player_id if order else ''}</code>)\n"
        f"💎 <b>Paket:</b> {order.product.name if order else '—'}\n"
        f"📅 <b>Yuborilgan vaqt:</b> {chk.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    # If telegram file_id is available, send the photo
    if chk.telegram_file_id:
        await call.message.delete()
        await call.message.answer_photo(
            photo=chk.telegram_file_id,
            caption=text,
            reply_markup=admin_payment_review_inline(chk.id),
        )
    else:
        await call.message.edit_text(text, reply_markup=admin_payment_review_inline(chk.id))

    await call.answer()


@router.callback_query(F.data.startswith("adm_appr_pay:"))
async def approve_payment(call: CallbackQuery, db_user):
    """Admin approves payment check."""
    check_id = int(call.data.split(":")[1])
    success, msg = await sync_to_async(PaymentService.admin_approve_manual_payment)(
        manual_payment_id=check_id,
        admin_identifier=db_user.display_name,
    )
    if success:
        await call.answer("✅ To'lov tasdiqlandi!", show_alert=True)
        await call.message.delete()
        await list_pending_manual_payments(call)
    else:
        await call.answer(f"Xatolik: {msg}", show_alert=True)


@router.callback_query(F.data.startswith("adm_rej_pay:"))
async def reject_payment(call: CallbackQuery, db_user):
    """Admin rejects payment check."""
    check_id = int(call.data.split(":")[1])
    success, msg = await sync_to_async(PaymentService.admin_reject_manual_payment)(
        manual_payment_id=check_id,
        admin_identifier=db_user.display_name,
        reason="Chek tasdiqlanmadi yoki noto'g'ri to'lov",
    )
    if success:
        await call.answer("❌ To'lov rad etildi.", show_alert=True)
        await call.message.delete()
        await list_pending_manual_payments(call)
    else:
        await call.answer(f"Xatolik: {msg}", show_alert=True)
