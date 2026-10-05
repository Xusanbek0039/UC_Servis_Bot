from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from utils.helpers import format_currency

router = Router()


@router.callback_query(F.data == "btn_my_balance")
async def user_balance(call: CallbackQuery):
    """Display user's account balance."""
    user = await db.get_user(call.from_user.id)
    balance = user["balance"] if user else 0.0

    text = (
        f"💰 <b>Sizning balansingiz:</b>\n\n"
        f"Hisob: <b>{format_currency(balance)}</b>\n"
        f"Telegram ID: <code>{call.from_user.id}</code>\n\n"
        f"<i>Balans orqali UC xaridlarini bir zumda to'lashingiz mumkin.</i>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 UC sotib olish", callback_data="btn_buy_uc")],
            [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="btn_cancel")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "btn_help")
async def user_help(call: CallbackQuery):
    """Display help information."""
    text = (
        f"ℹ️ <b>Yordam va Yo'riqnoma:</b>\n\n"
        f"1. <b>🎮 UC sotib olish</b> tugmasini bosing.\n"
        f"2. PUBG Mobile Player ID raqamingizni kiriting.\n"
        f"3. O'zingizga ma'qul UC paketini tanlang.\n"
        f"4. To'lov usulini (TezCheck yoki Karta orqali) tanlang.\n"
        f"5. To'lov amalga oshirilgach, UC akkauntingizga yetkaziladi!\n\n"
        f"Savollaringiz bo'lsa <b>📞 Admin</b> bo'limiga murojaat qiling."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="btn_cancel")]]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "btn_support")
async def user_support(call: CallbackQuery):
    """Display customer support contact."""
    support_username = await db.get_setting("support_username", "@PubgUcSupport")
    text = (
        f"📞 <b>Mijozlarni qo'llab-quvvatlash:</b>\n\n"
        f"Savol yoki muammolar bo'lsa administrator bilan bog'laning:\n"
        f"Operator: <b>{support_username}</b>\n\n"
        f"Ish vaqti: 24/7"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Adminga yozish", url=f"https://t.me/{support_username.lstrip('@')}")],
            [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="btn_cancel")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
