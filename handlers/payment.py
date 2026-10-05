import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states.order import OrderStates
from keyboards.user import tezcheck_pay_keyboard, cancel_keyboard, main_menu_keyboard
from config import ADMIN_IDS
import database as db
from services.tezcheck import TezCheckService
from services.order_service import OrderService
from utils.helpers import format_currency

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

    # Update payment method on order
    async with await db.get_connection() as conn:
        await conn.execute("UPDATE orders SET payment_method = ? WHERE order_id = ?", (method, order_id))
        await conn.commit()

    # 1. Internal Balance Payment
    if method == "BALANCE":
        user = await db.get_user(call.from_user.id)
        if not user or user["balance"] < price:
            await call.answer("Balansingizda yetarli mablag' mavjud emas!", show_alert=True)
            return

        # Deduct balance
        await db.update_user_balance(call.from_user.id, -price)
        await db.create_payment(order_id=order_id, amount=price, payment_method="BALANCE", payment_id="BAL")
        await OrderService.handle_payment_success(bot, order_id=order_id, provider_tx_id="BALANCE_TX")

        await state.clear()
        await call.message.delete()
        is_admin = call.from_user.id in ADMIN_IDS
        await call.message.answer(
            f"🎉 <b>To'lov balansingizdan muvaffaqiyatli yechildi!</b>\n\n"
            f"📦 Buyurtma: <code>{order_id}</code>\n"
            f"UC qisqa vaqt ichida o'yindagi hisobingizga yetkaziladi.",
            reply_markup=main_menu_keyboard(is_admin=is_admin),
        )
        await call.answer()
        return

    # 2. TezCheck Payment
    if method == "TEZCHECK":
        wait_msg = await call.message.edit_text("⏳ <i>TezCheck to'lov havolasi yaratilmoqda...</i>")
        success, pay_url, err = await TezCheckService.create_payment_bill(
            order_id=order_id,
            amount=price,
            description=f"PUBG UC: {order['product_name']} ({order_id})",
        )

        if not success:
            await wait_msg.edit_text(
                f"⚠️ To'lov tizimida vaqtinchalik muammo: {err}\nIltimos, karta orqali to'lang.",
                reply_markup=cancel_keyboard(),
            )
            await call.answer()
            return

        await db.create_payment(order_id=order_id, amount=price, payment_method="TEZCHECK")

        text = (
            f"⚡ <b>TezCheck orqali to'lov</b>\n\n"
            f"📦 Buyurtma: <code>{order_id}</code>\n"
            f"💎 Paket: {order['product_name']}\n"
            f"💰 To'lov summasi: <b>{format_currency(price)}</b>\n\n"
            f"To'lovni amalga oshirish uchun quyidagi tugmani bosing 👇"
        )
        await wait_msg.edit_text(text, reply_markup=tezcheck_pay_keyboard(pay_url, order_id))
        await call.answer()
        return

    # 3. Manual Card Payment
    if method == "MANUAL_CARD":
        card_num = await db.get_setting("card_number", "8600 0000 0000 1234")
        card_owner = await db.get_setting("card_owner", "PUBG OPERATOR")
        bank_name = await db.get_setting("bank_name", "Kapitalbank")

        await db.create_payment(order_id=order_id, amount=price, payment_method="MANUAL_CARD")
        await state.set_state(OrderStates.WAITING_SCREENSHOT)

        text = (
            f"💳 <b>Karta orqali to'lov</b>\n\n"
            f"Karta raqami:\n<code>{card_num}</code>\n"
            f"Egasi: <b>{card_owner}</b>\n"
            f"Bank: <b>{bank_name}</b>\n\n"
            f"📦 Buyurtma: <code>{order_id}</code>\n"
            f"💰 To'lov summasi: <b>{format_currency(price)}</b>\n\n"
            f"❗️ <b>To'lovni amalga oshiring va chek/skrinshotni shu yerga rasm holida yuboring.</b>"
        )
        await call.message.delete()
        await call.message.answer(text, reply_markup=cancel_keyboard())
        await call.answer()


@router.message(OrderStates.WAITING_SCREENSHOT, F.photo | F.document)
async def process_screenshot(message: Message, state: FSMContext, bot: Bot):
    """Receive receipt screenshot."""
    data = await state.get_data()
    order_id = data.get("order_id")

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
                InlineKeyboardButton(text="✅ To‘lovni tasdiqlash", callback_data=f"adm_appr_ord:{order_id}"),
                InlineKeyboardButton(text="❌ To‘lovni rad etish", callback_data=f"adm_rej_ord:{order_id}"),
            ]
        ]
    )

    caption = (
        f"🟡 <b>YANGI TO'LOV CHEKI (SKRINSHOT)!</b>\n\n"
        f"📦 <b>Order:</b> <code>{order_id}</code>\n"
        f"👤 <b>User:</b> @{message.from_user.username or '—'} (ID: <code>{message.from_user.id}</code>)\n"
        f"🎮 <b>Player ID:</b> <code>{order['player_id']}</code>\n"
        f"💎 <b>Paket:</b> {order['product_name']}\n"
        f"💰 <b>Summa:</b> {format_currency(order['price'])}\n\n"
        f"<i>Chekni tekshiring va tasdiqlang yoki rad eting.</i>"
    )

    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(chat_id=admin_id, photo=file_id, caption=caption, reply_markup=admin_kb)
            else:
                await bot.send_document(chat_id=admin_id, document=file_id, caption=caption, reply_markup=admin_kb)
        except Exception as e:
            logger.error(f"Failed to forward check to admin {admin_id}: {e}")

    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer(
        "⏳ <b>To‘lovingiz admin tomonidan tekshirilmoqda.</b>\n\n"
        "Tez orada chekingiz tasdiqlanadi va UC akkauntingizga yuboriladi.",
        reply_markup=main_menu_keyboard(is_admin=is_admin),
    )


@router.callback_query(F.data.startswith("chk_pay:"))
async def check_order_payment(call: CallbackQuery):
    """User clicks verify payment."""
    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order["status"] in ("PAID", "PROCESSING", "COMPLETED"):
        await call.message.delete()
        is_admin = call.from_user.id in ADMIN_IDS
        await call.message.answer(
            f"✅ <b>To'lov muvaffaqiyatli qabul qilingan!</b>\nStatus: <b>{order['status']}</b>",
            reply_markup=main_menu_keyboard(is_admin=is_admin),
        )
    else:
        await call.answer("To'lov hali amalga oshirilmagan.", show_alert=True)


@router.callback_query(F.data.startswith("cancel_ord:"))
async def cancel_order_handler(call: CallbackQuery, state: FSMContext):
    """Cancel order from checkout."""
    order_id = call.data.split(":")[1]
    await db.update_order_status(order_id, "CANCELLED")
    await state.clear()
    is_admin = call.from_user.id in ADMIN_IDS
    await call.message.edit_text("❌ Buyurtma bekor qilindi.")
    await call.message.answer("Asosiy menyudasiz 👇", reply_markup=main_menu_keyboard(is_admin=is_admin))
    await call.answer()
