from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from django.conf import settings
from apps.settings.models import BotSettings
from apps.referrals.models import ReferralRelationship, ReferralReward
from bot.keyboards.reply import main_menu_keyboard

router = Router()


@router.message(F.text.in_(["💰 Balansim", "💳 To‘lov qilish", "/balance"]))
async def balance_handler(message: Message, db_user):
    """Display user's balance and referral statistics."""
    await sync_to_async(db_user.refresh_from_db)()

    # Get referral count & total earned
    ref_count = await sync_to_async(ReferralRelationship.objects.filter(referrer=db_user).count)()
    rewards_sum = await sync_to_async(
        lambda: sum(
            r.bonus_amount
            for r in ReferralReward.objects.filter(referrer=db_user, is_paid=True)
        )
    )()

    bot_username = getattr(settings, "BOT_USERNAME", "PubgUcServisBot")
    ref_link = f"https://t.me/{bot_username}?start=ref_{db_user.telegram_id}"
    bot_settings = await sync_to_async(BotSettings.load)()

    balance_text = (
        f"💰 <b>Sizning balansingiz:</b>\n"
        f"<b>{db_user.balance:,.0f} so'm</b>\n\n"
        f"👥 <b>Do'stlarni taklif qilish (Referral):</b>\n"
        f"Har bir taklif qilingan do'stingiz birinchi marta UC sotib olganda balansingizga "
        f"<b>{bot_settings.referral_bonus:,.0f} UZS</b> bonus beriladi!\n\n"
        f"🔗 <b>Sizning taklif havolangiz:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 Taklif qilingan do'stlar: <b>{ref_count} ta</b>\n"
        f"🎁 Jami ishlangan bonus: <b>{rewards_sum:,.0f} UZS</b>\n"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 UC sotib olish", callback_data="start_buy_uc_inline")],
            [InlineKeyboardButton(text="👥 Do'stlarga ulashish", url=f"https://t.me/share/url?url={ref_link}&text=PUBG%20Mobile%20uchun%20arzon%20va%20ishonchli%20UC!")],
        ]
    )

    await message.answer(balance_text, reply_markup=kb)


@router.callback_query(F.data == "start_buy_uc_inline")
async def start_buy_inline(call: CallbackQuery, state: FSMContext):
    """Trigger buy uc from balance inline button."""
    from bot.handlers.user.buy_uc import start_buy_uc
    await call.message.delete()
    await start_buy_uc(call.message, state)
    await call.answer()
