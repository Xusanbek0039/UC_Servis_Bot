from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from utils.helpers import format_currency, DIVIDER, SUB_DIVIDER
from keyboards.user import profile_keyboard, balance_keyboard, support_keyboard, nav_back_home_keyboard
from emojis import E

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
async def user_topup_balance(call: CallbackQuery):
    """Prompt user on how to topup internal balance."""
    support_username = await db.get_setting("support_username", "@PubgUcSupport")
    card_num = await db.get_setting("card_number", "8600 0000 0000 1234")
    card_owner = await db.get_setting("card_owner", "PUBG OPERATOR")

    text = (
        f"{DIVIDER}\n"
        f"   {E('card')} <b>BALANS TO'LDIRISH</b>\n"
        f"{DIVIDER}\n\n"
        f"Hisobingizni to'ldirish uchun operator kartasiga to'lov qiling va chekni adminga yuboring:\n\n"
        f"{E('card')} <b>Karta:</b> <code>{card_num}</code>\n"
        f"{E('profile')} <b>Egasi:</b> <b>{card_owner}</b>\n"
        f"🆔 <b>Sizning ID:</b> <code>{call.from_user.id}</code>\n"
        f"{SUB_DIVIDER}\n"
        f"To'lov qilgach, {support_username} profiliga chekni va o'z ID raqamingizni yuboring."
    )
    await call.message.edit_text(text, reply_markup=support_keyboard(support_username))
    await call.answer()


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
        f"4️⃣ To'lov usulini tanlang (<b>TezCheck</b> yoki <b>Karta</b> orqali).\n"
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
