from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from apps.users.models import TelegramUser

router = Router()


@router.callback_query(F.data == "admin_users")
async def list_admin_users(call: CallbackQuery):
    """Display user overview for admin."""
    total_users = await sync_to_async(TelegramUser.objects.count)()
    recent_users = await sync_to_async(list)(TelegramUser.objects.order_by("-created_at")[:8])

    text = f"👥 <b>FOYDALANUVCHILAR</b>\n\nJami ro'yxatdan o'tganlar: <b>{total_users} nafar</b>\n\n<b>So'nggi foydalanuvchilar:</b>\n"
    for u in recent_users:
        text += f"• {u.display_name} (ID: <code>{u.telegram_id}</code>) | Balans: {u.balance:,.0f} UZS\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")]]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "admin_promos")
async def list_admin_promos(call: CallbackQuery):
    """Display promo codes overview for admin."""
    from apps.promo.models import PromoCode
    promos = await sync_to_async(list)(PromoCode.objects.all().order_by("-created_at")[:8])

    text = "🎟 <b>PROMO KODLAR:</b>\n\n"
    if not promos:
        text += "<i>Hozircha promo kodlar yaratilmagan. Django Admindan qo'shishingiz mumkin.</i>"
    else:
        for p in promos:
            status = "🟢" if p.is_active else "🔴"
            val = f"{p.discount_value}%" if p.discount_type == "PERCENTAGE" else f"{p.discount_value:,.0f} UZS"
            text += f"{status} <b>{p.code}</b>: -{val} (Ishlatildi: {p.used_count}/{p.max_uses})\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")]]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "admin_logs")
async def list_admin_logs(call: CallbackQuery):
    """Display recent audit logs."""
    from apps.audit.models import AdminAction
    logs = await sync_to_async(list)(AdminAction.objects.order_by("-created_at")[:10])

    text = "📋 <b>SO'NGGI ADMIN HARAKATLARI (AUDIT LOG):</b>\n\n"
    if not logs:
        text += "<i>Hali hech qanday amal qayd etilmagan.</i>"
    else:
        for l in logs:
            dt = l.created_at.strftime("%d.%m %H:%M")
            text += f"• [{dt}] <b>{l.admin_identifier}</b>: {l.action_type} (#{l.target_id})\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")]]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()
