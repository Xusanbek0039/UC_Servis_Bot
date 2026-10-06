import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from html import escape as quote
from states.order import OrderStates
from keyboards.user import (
    tezcheck_pay_keyboard,
    cancel_keyboard,
    main_menu_keyboard,
    order_success_keyboard,
    payment_methods_keyboard,
    nav_back_home_keyboard,
)
from config import ADMIN_IDS
import database as db
from services.tezcheck import TezCheckService
from services.payment_monitor import check_tezcheck_payment
from services.order_service import OrderService
from utils.helpers import format_currency, DIVIDER, SUB_DIVIDER, format_order_summary
from emojis import E

router = Router()
logger = logging.getLogger("handlers.payment")


@router.callback_query(OrderStates.WAITING_PAYMENT_METHOD, F.data.startswith("pay_method:"))
async def process_payment_method(call: CallbackQuery, state: FSMContext, bot: Bot):
    """User selects payment method."""
    method = call.data.split(":")[1]
    data = await state.get_data()
    order_id = data.get("order_id")
    price = data.get("price", 0.0)

    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        await state.clear()
        return
    if order.get("user_id") != call.from_user.id or order.get("payment_status", "PENDING") != "PENDING" or order.get("status") != "WAITING_PAYMENT":
        await call.answer("Bu buyurtma to'lov uchun yaroqsiz yoki sizga tegishli emas.", show_alert=True)
        return

    # Update payment method on order
    await db.update_order_payment_method(order_id, method)

    # 1. Internal Balance Payment
    if method == "BALANCE":
        user = await db.get_user(call.from_user.id)
        if not user or user.get("balance", 0.0) < price:
            await call.answer("Balansingizda yetarli mablag' mavjud emas!", show_alert=True)
            return

        if not await db.debit_balance_for_order(order_id, call.from_user.id, float(price)):
            await call.answer("Balans yetarli emas yoki buyurtma allaqachon to'langan.", show_alert=True)
            return
        await db.create_payment(order_id=order_id, amount=price, payment_method="BALANCE", payment_id=f"balance:{order_id}")
        await OrderService.handle_payment_success(bot, order_id=order_id, provider_tx_id="BALANCE_TX")

        await state.clear()
        text = (
            f"{DIVIDER}\n"
            f"   {E('success')} <b>TO'LOV MUVAFFAQIYATLI</b>\n"
            f"{DIVIDER}\n\n"
            f"{E('balance')} <b>Mablag' balansingizdan yechildi!</b>\n\n"
            f"📦 <b>Buyurtma kodi:</b> <code>{order_id}</code>\n"
            f"{E('uc')} <b>Paket:</b> {order['product_name']}\n"
            f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
            f"{SUB_DIVIDER}\n"
            f"{E('lightning')} <i>UC qisqa vaqt ichida o'yindagi hisobingizga yuklanadi.</i>"
        )
        await call.message.edit_text(text, reply_markup=order_success_keyboard())
        await call.answer()
        return

    # 2. TezCheck Payment
    if method == "TEZCHECK":
        wait_msg = await call.message.edit_text(f"{E('clock')} <i>Onlayn to'lov havolasi yaratilmoqda...</i>")
        success, pay_url, bill_id, err = await TezCheckService.create_payment_bill(
            order_id=order_id,
            amount=price,
            description=f"PUBG UC: {order['product_name']} ({order_id})",
        )

        if not success:
            await wait_msg.edit_text(
                f"{DIVIDER}\n"
                f"{E('error')} <b>To'lov tizimida vaqtinchalik muammo yuz berdi.</b>\n\n"
                f"Sabab: {quote(err)}\n"
                f"Iltimos, karta orqali to'lov qiling.\n"
                f"{DIVIDER}",
                reply_markup=nav_back_home_keyboard("back_to_products"),
            )
            await call.answer()
            return

        await db.create_payment(
            order_id=order_id,
            amount=price,
            payment_method="TEZCHECK",
            bill_id=bill_id,
            amount_minor=int(round(float(price) * 100)),
        )

        text = (
            f"{DIVIDER}\n"
            f"   {E('lightning')} <b>ONLAYN TO'LOV (AVTOMATIK)</b>\n"
            f"{DIVIDER}\n\n"
            f"📦 <b>Buyurtma:</b> <code>{order_id}</code>\n"
            f"{E('uc')} <b>Paket:</b> <b>{order['product_name']}</b>\n"
            f"{E('balance')} <b>To'lov summasi:</b> <b>{format_currency(price)}</b>\n"
            f"{SUB_DIVIDER}\n"
            f"{E('verified')} <i>To'lov xavfsiz onlayn to'lov tizimi orqali qabul qilinadi. To'lov qilingach, bot avtomatik tasdiqlaydi.</i>\n\n"
            f"To'lovni davom ettirish uchun quyidagi tugmani bosing 👇"
        )
        await wait_msg.edit_text(text, reply_markup=tezcheck_pay_keyboard(pay_url, order_id))
        await call.answer()
        return

    # 3. Manual Card Payment
    if method == "MANUAL_CARD":
        card_num = await db.get_setting("card_number", "8600 0000 0000 1234")
        card_owner = await db.get_setting("card_owner", "PUBG OPERATOR")
        bank_name = await db.get_setting("bank_name", "Kapitalbank")

        await db.create_payment(order_id=order_id, amount=price, payment_method="MANUAL_CARD", payment_id=f"manual:{order_id}")
        await state.set_state(OrderStates.WAITING_SCREENSHOT)

        text = (
            f"{DIVIDER}\n"
            f"   {E('card')} <b>KARTA ORQALI TO'LOV</b>\n"
            f"{DIVIDER}\n\n"
            f"{E('balance')} <b>To'lov summasi:</b>\n"
            f"👉 <b>{format_currency(price)}</b>\n\n"
            f"{E('card')} <b>Karta raqami:</b>\n"
            f"<code>{card_num}</code> <i>(nusxalash uchun ustiga bosing)</i>\n\n"
            f"{E('profile')} <b>Karta egasi:</b> <b>{card_owner}</b>\n"
            f"🏦 <b>Bank:</b> {bank_name}\n"
            f"📦 <b>Buyurtma kodi:</b> <code>{order_id}</code>\n"
            f"{SUB_DIVIDER}\n"
            f"<b>Qadamlar:</b>\n"
            f"1️⃣ Yuqoridagi kartaga to'lov qiling.\n"
            f"2️⃣ To'lov chekini (skrinshot) shu yerga yuboring.\n"
            f"3️⃣ Operator tekshirib, darhol UC yuklaydi.\n"
            f"{SUB_DIVIDER}\n\n"
            f"📎 <b>Iltimos, chek skrinshotini rasm holatida yuboring:</b>"
        )
        await call.message.edit_text(text, reply_markup=cancel_keyboard())
        await call.answer()


@router.message(OrderStates.WAITING_SCREENSHOT, F.photo | F.document)
async def process_screenshot(message: Message, state: FSMContext, bot: Bot):
    """Receive receipt screenshot."""
    data = await state.get_data()
    order_id = data.get("order_id")
    order = await db.get_order(order_id) if order_id else None
    if not order or order.get("user_id") != message.from_user.id or order.get("payment_status") != "PENDING":
        await state.clear()
        await message.answer("Ushbu buyurtma uchun chek qabul qilinmaydi. Yangidan buyurtma bering.")
        return

    file_id = ""
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id

    await db.attach_order_screenshot(order_id=order_id, file_id=file_id)
    order = await db.get_order(order_id)

    # Notify Admins with screenshot
    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{E('check', True)} To'lovni tasdiqlash", callback_data=f"adm_appr_ord:{order_id}"),
                InlineKeyboardButton(text=f"{E('cross', True)} Rad etish", callback_data=f"adm_rej_ord:{order_id}"),
            ]
        ]
    )

    caption = (
        f"🟡 <b>YANGI TO'LOV CHEKI (SKRINSHOT)!</b>\n\n"
        f"📦 <b>Order:</b> <code>{order_id}</code>\n"
        f"👤 <b>Foydalanuvchi:</b> @{order.get('username')} (ID: <code>{order['user_id']}</code>)\n"
        f"🆔 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
        f"{E('uc')} <b>Paket:</b> {order['product_name']}\n"
        f"💰 <b>Narx:</b> {format_currency(order['price'])}\n"
        f"{E('uc')} <b>Mijozning jami xaridi:</b> <b>{order.get('user_total_uc', 0):,} UC</b>\n\n"
        f"To'lovni tasdiqlaysizmi?"
    )

    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(chat_id=admin_id, photo=file_id, caption=caption, reply_markup=admin_kb)
            elif message.document:
                await bot.send_document(chat_id=admin_id, document=file_id, caption=caption, reply_markup=admin_kb)
        except Exception as e:
            logger.error(f"Failed to forward receipt to admin {admin_id}: {e}")

    await state.clear()
    reply_text = (
        f"{DIVIDER}\n"
        f"   {E('success')} <b>CHEK QABUL QILINDI</b>\n"
        f"{DIVIDER}\n\n"
        f"📦 <b>Buyurtma kodi:</b> <code>{order_id}</code>\n"
        f"{E('uc')} <b>Paket:</b> {order['product_name']}\n"
        f"{E('balance')} <b>Summa:</b> {format_currency(order['price'])}\n"
        f"{SUB_DIVIDER}\n"
        f"{E('clock')} <i>To'lov cheki operator tekshiruviga yuborildi.\n"
        f"Odatda bir necha daqiqa ichida tekshirilib, UC o'yindagi profilingizga yetkaziladi.</i>"
    )
    await message.answer(reply_text, reply_markup=order_success_keyboard())


@router.callback_query(F.data.startswith("chk_pay:"))
async def check_payment_manual(call: CallbackQuery, bot: Bot):
    """User manually requests payment check for TezCheck."""
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)

    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return
    if order.get("user_id") != call.from_user.id:
        await call.answer("Bu buyurtma sizga tegishli emas.", show_alert=True)
        return

    if order["status"] in ("PAID", "PROCESSING", "COMPLETED"):
        await call.answer("✅ To'lov tasdiqlangan va UC yetkazilmoqda!", show_alert=True)
        await call.message.edit_text(
            f"{DIVIDER}\n"
            f"   {E('success')} <b>TO'LOV TASDIQLANGAN</b>\n"
            f"{DIVIDER}\n\n"
            f"📦 <b>Buyurtma:</b> <code>{order_id}</code>\n"
            f"{E('uc')} <b>Paket:</b> {order['product_name']}\n\n"
            f"{E('lightning')} <i>Buyurtmangiz bajarilmoqda.</i>",
            reply_markup=order_success_keyboard(),
        )
    else:
        payment = await db.get_payment_by_order(order_id)
        if payment and payment.get("payment_method") == "TEZCHECK":
            result = await check_tezcheck_payment(bot, payment, notify_user=False)
            if result == "paid":
                await call.answer("✅ To‘lov tasdiqlandi!", show_alert=True)
                return
            if result == "error":
                await call.answer("To‘lov holatini tekshirib bo‘lmadi. Keyinroq urinib ko‘ring.", show_alert=True)
                return
            if result == "mismatch":
                await call.answer("To‘lov summasi mos kelmadi. Operatorga murojaat qiling.", show_alert=True)
                return
        await call.answer("⏳ To'lov hali tasdiqlanmadi. To‘lovdan keyin yana tekshiring.", show_alert=True)


@router.callback_query(F.data.startswith("change_method:"))
async def change_payment_method(call: CallbackQuery, state: FSMContext):
    """User changes payment method for existing order."""
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return
    if order.get("user_id") != call.from_user.id or order.get("payment_status") != "PENDING":
        await call.answer("Bu buyurtma to'lovga yaroqli emas yoki sizga tegishli emas.", show_alert=True)
        return

    await state.update_data(order_id=order_id, product_id=order["product_id"], price=order["price"])
    await state.set_state(OrderStates.WAITING_PAYMENT_METHOD)

    user = await db.get_user(call.from_user.id)
    user_balance = user["balance"] if user else 0.0

    summary_text = (
        f"{DIVIDER}\n"
        f"   {E('order')} <b>TO'LOV USULINI O'ZGARTIRISH</b>\n"
        f"{DIVIDER}\n\n"
        f"📦 <b>Buyurtma:</b> <code>{order_id}</code>\n"
        f"{E('uc')} <b>Paket:</b> <b>{order['product_name']}</b>\n"
        f"{E('balance')} <b>To'lov summasi:</b> <b>{format_currency(order['price'])}</b>\n"
        f"{SUB_DIVIDER}\n\n"
        f"Yangi to'lov usulini tanlang 👇"
    )
    await call.message.edit_text(
        summary_text,
        reply_markup=payment_methods_keyboard(user_balance=user_balance, order_price=order["price"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("cancel_ord:"))
async def cancel_specific_order(call: CallbackQuery, state: FSMContext):
    """Cancel order and return to main menu."""
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order or order.get("user_id") != call.from_user.id or order.get("payment_status") != "PENDING":
        await call.answer("To'langan buyurtmani bekor qilib bo'lmaydi.", show_alert=True)
        return
    await db.transition_order(order_id, ["WAITING_PAYMENT"], "CANCELLED", payment_status="FAILED")
    await state.clear()
    await call.answer("❌ Buyurtma bekor qilindi.", show_alert=True)

    is_admin = call.from_user.id in ADMIN_IDS
    await call.message.edit_text(
        f"{DIVIDER}\n"
        f"{E('cross')} <b>Buyurtma #{order_id} bekor qilindi.</b>\n"
        f"{DIVIDER}",
        reply_markup=main_menu_keyboard(is_admin=is_admin),
    )
