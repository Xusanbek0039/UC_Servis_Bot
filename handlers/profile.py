from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.html import quote
from uuid import uuid4
import database as db
from utils.helpers import format_currency, DIVIDER, SUB_DIVIDER
from keyboards.user import profile_keyboard, balance_keyboard, support_keyboard, nav_back_home_keyboard, balance_topup_keyboard
from emojis import E
from states.order import TopUpStates
from services.tezcheck import TezCheckService
from services.payment_monitor import check_tezcheck_payment

router = Router()


@router.callback_query(F.data == "btn_profile")
async def user_profile(call: CallbackQuery):
    """Display user profile with stats and purchase history."""
    telegram_id = call.from_user.id
    user = await db.get_user(telegram_id)
    balance = user.get("balance", 0.0) if user else 0.0
    username_str = f"@{call.from_user.username}" if call.from_user.username else "Mavjud emas"
    first_name = call.from_user.first_name or "Foydalanuvchi"

    # Get user order stats
    orders = await db.get_user_orders(telegram_id, limit=100)
    orders_count = len(orders)
    total_uc = sum(o.get("uc_amount", 0) for o in orders if o.get("status") == "COMPLETED")

    text = (
        f"{DIVIDER}\n"
        f"   {E('profile')} <b>FOYDALANUVCHI PROFILI</b>\n"
        f"{DIVIDER}\n\n"
        f"{E('profile')} <b>Ism:</b> {first_name}\n"
        f"🏷 <b>Username:</b> {username_str}\n"
        f"🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
        f"{SUB_DIVIDER}\n"
        f"{E('balance')} <b>Hisob balansi:</b> <b>{format_currency(balance)}</b>\n"
        f"{E('order')} <b>Jami buyurtmalar:</b> <b>{orders_count} ta</b>\n"
        f"{E('uc')} <b>Xarid qilingan UC:</b> <b>{total_uc:,} UC</b>\n"
        f"{DIVIDER}"
    )

    await call.message.edit_text(text, reply_markup=profile_keyboard())
    await call.answer()


@router.callback_query(F.data == "btn_my_balance")
async def user_balance(call: CallbackQuery):
    """Display user's account balance with topup option."""
    user = await db.get_user(call.from_user.id)
    balance = user.get("balance", 0.0) if user else 0.0

    text = (
        f"{DIVIDER}\n"
        f"   {E('balance')} <b>HISOB BALANSI</b>\n"
        f"{DIVIDER}\n\n"
        f"Hozirgi balansingiz:\n"
        f"👉 <b>{format_currency(balance)}</b>\n\n"
        f"{SUB_DIVIDER}\n"
        f"{E('bulb')} <i>Balansingizdagi mablag' orqali istalgan UC paketini to'g'ridan-to'g'ri bir zumda xarid qilishingiz mumkin.</i>"
    )

    await call.message.edit_text(text, reply_markup=balance_keyboard())
    await call.answer()


@router.callback_query(F.data == "btn_topup_balance")
async def user_topup_balance(call: CallbackQuery, state: FSMContext):
    """Ask for an amount, then create a one-time TezCheck bill."""
    await state.set_state(TopUpStates.WAITING_AMOUNT)
    text = (
        f"{DIVIDER}\n"
        f"   {E('balance')} <b>BALANSNI AVTOMATIK TO‘LDIRISH</b>\n"
        f"{DIVIDER}\n\n"
        "Qancha pul qo‘shmoqchisiz? Summani so‘mda yuboring.\n"
        "Masalan: <code>10000</code>\n\n"
        "Eng kam to‘ldirish: <b>1 000 so‘m</b>. To‘lov tasdiqlangach mablag‘ balansingizga avtomatik tushadi."
    )
    await call.message.edit_text(text, reply_markup=nav_back_home_keyboard())
    await call.answer()


@router.message(TopUpStates.WAITING_AMOUNT)
async def create_balance_topup(message: Message, state: FSMContext):
    raw_amount = (message.text or "").strip().replace(" ", "").replace(",", "").replace("_", "")
    if not raw_amount.isdigit():
        await message.answer("Summani faqat raqam bilan yuboring. Masalan: <code>10000</code>")
        return
    amount = int(raw_amount)
    if amount < 1000:
        await message.answer("Eng kam to‘ldirish 1 000 so‘m. Boshqa summani kiriting:")
        return

    topup_id = f"TOPUP-{message.from_user.id}-{uuid4().hex[:12]}"
    success, pay_url, bill_id, error = await TezCheckService.create_payment_bill(
        order_id=topup_id,
        amount=amount,
        description=f"Balansni to‘ldirish {format_currency(amount)}",
    )
    if not success:
        await message.answer(
            f"{DIVIDER}\n⚠️ <b>To‘lov havolasi yaratilmadi</b>\n\n{quote(error)}\n{DIVIDER}",
            reply_markup=balance_keyboard(),
        )
        await state.clear()
        return

    amount_minor = amount * 100
    await db.create_payment(
        order_id=topup_id,
        amount=amount,
        payment_method="TEZCHECK",
        bill_id=bill_id,
        amount_minor=amount_minor,
        payment_type="BALANCE_TOPUP",
        telegram_id=message.from_user.id,
    )
    await state.clear()
    await message.answer(
        f"{DIVIDER}\n⚡ <b>BALANSNI TO‘LDIRISH</b>\n{DIVIDER}\n\n"
        f"To‘lov summasi: <b>{format_currency(amount)}</b>\n"
        "To‘lovni amalga oshiring. Tasdiqlangach pul avtomatik balansga qo‘shiladi.",
        reply_markup=balance_topup_keyboard(pay_url, topup_id),
    )


@router.callback_query(F.data.startswith("check_topup:"))
async def check_balance_topup(call: CallbackQuery):
    topup_id = call.data.split(":", 1)[1]
    payment = await db.get_payment_by_order(topup_id)
    if not payment or payment.get("payment_type") != "BALANCE_TOPUP" or payment.get("telegram_id") != call.from_user.id:
        await call.answer("To‘lov topilmadi.", show_alert=True)
        return
    if payment.get("status") == "PAID":
        await call.answer("To‘lov oldin tasdiqlangan.", show_alert=True)
        return

    result = await check_tezcheck_payment(call.bot, payment, notify_user=False)
    if result == "paid":
        user = await db.get_user(call.from_user.id)
        balance = user.get("balance", 0) if user else 0
        await call.message.edit_text(
            f"✅ <b>To‘lov tasdiqlandi!</b>\n\n"
            f"{format_currency(payment.get('amount', 0))} balansingizga qo‘shildi.\n"
            f"Joriy balans: <b>{format_currency(balance)}</b>",
            reply_markup=balance_keyboard(),
        )
        await call.answer()
    elif result == "mismatch":
        await call.answer("To‘lov summasi mos kelmadi. Operatorga murojaat qiling.", show_alert=True)
    elif result == "error":
        await call.answer("To‘lov holatini hozir tekshirib bo‘lmadi. Keyinroq urinib ko‘ring.", show_alert=True)
    elif result == "already_processed":
        await call.answer("To‘lov tasdiqlangan va balansga qo‘shilgan.", show_alert=True)
    else:
        await call.answer("To‘lov hali tasdiqlanmadi. Birozdan keyin qayta tekshiring.", show_alert=True)


@router.callback_query(F.data == "btn_help")
async def user_help(call: CallbackQuery):
    """Display comprehensive instructions."""
    support_username = await db.get_setting("support_username", "@PubgUcSupport")

    text = (
        f"{DIVIDER}\n"
        f"   {E('support')} <b>QO'LLANMA VA YO'RIQNOMA</b>\n"
        f"{DIVIDER}\n\n"
        f"<b>Qanday qilib UC sotib olinadi?</b>\n\n"
        f"1️⃣ <b>{E('uc', True)} UC sotib olish</b> tugmasini bosing.\n"
        f"2️⃣ PUBG Mobile Player ID raqamingizni yuboring.\n"
        f"3️⃣ O'zingizga kerakli UC paketini tanlang.\n"
        f"4️⃣ To'lov usulini tanlang (<b>Onlayn to'lov</b> yoki <b>Karta</b> orqali).\n"
        f"5️⃣ To'lov muvaffaqiyatli yakunlangach, UC o'yindagi akkauntingizga yetkaziladi!\n\n"
        f"{SUB_DIVIDER}\n"
        f"{E('clock')} <b>Yetkazish vaqti:</b> 1-5 daqiqa\n"
        f"{E('verified')} <b>Kafolat:</b> 100% rasmiy va xavfsiz"
    )

    await call.message.edit_text(text, reply_markup=support_keyboard(support_username))
    await call.answer()


@router.callback_query(F.data == "btn_support")
async def user_support(call: CallbackQuery):
    """Display customer support contact."""
    support_username = await db.get_setting("support_username", "@PubgUcSupport")

    text = (
        f"{DIVIDER}\n"
        f"   {E('support')} <b>MIJOZLARNI QO'LLAB-QUVVATLASH</b>\n"
        f"{DIVIDER}\n\n"
        f"Savol, taklif yoki buyurtmangiz bo'yicha yordam kerakmi?\n"
        f"Bizning operatorlarimiz sizga yordam berishga doim tayyor.\n\n"
        f"{E('profile')} <b>Operator:</b> {support_username}\n"
        f"{E('clock')} <b>Ish vaqti:</b> 24/7 uzluksiz"
    )

    await call.message.edit_text(text, reply_markup=support_keyboard(support_username))
    await call.answer()
