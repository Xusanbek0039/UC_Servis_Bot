from datetime import timedelta
from decimal import Decimal
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.utils import timezone
from asgiref.sync import sync_to_async
from apps.users.models import TelegramUser
from apps.orders.models import Order
from apps.settings.models import BotSettings
from apps.audit.models import AdminAction
from apps.payments.models import ManualPayment
from bot.keyboards.admin import admin_menu_inline

router = Router()


@router.message(Command("admin"))
@router.message(F.text == "👑 Admin Panel")
async def admin_dashboard(message: Message, db_user):
    """Admin dashboard entrypoint."""
    welcome_text = (
        f"👑 <b>Admin Boshqaruv Paneliga xush kelibsiz!</b>\n\n"
        f"Xodim: <b>{db_user.display_name}</b> (ID: <code>{db_user.telegram_id}</code>)\n\n"
        f"Kerakli bo'limni tanlang 👇"
    )
    await message.answer(welcome_text, reply_markup=admin_menu_inline())


@router.callback_query(F.data == "admin_stats")
async def admin_statistics(call: CallbackQuery):
    """Display comprehensive business statistics (Today, Weekly, Monthly)."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    def calc_stats(start_time):
        qs = Order.objects.filter(created_at__gte=start_time)
        comp_qs = qs.filter(status=Order.Status.COMPLETED)
        revenue = sum(o.final_amount for o in comp_qs)
        profit = sum(max(Decimal("0.00"), o.final_amount - o.product.cost_price) for o in comp_qs.select_related("product"))
        orders_count = qs.count()
        success_count = comp_qs.count()
        fail_count = qs.filter(status__in=[Order.Status.FAILED, Order.Status.CANCELLED]).count()
        users_count = TelegramUser.objects.filter(created_at__gte=start_time).count()
        return {
            "revenue": revenue,
            "profit": profit,
            "orders": orders_count,
            "success": success_count,
            "failed": fail_count,
            "users": users_count,
        }

    s_today = await sync_to_async(calc_stats)(today_start)
    s_week = await sync_to_async(calc_stats)(week_start)
    s_month = await sync_to_async(calc_stats)(month_start)

    text = (
        f"📊 <b>PUBG UC SHOP STATISTIKASI</b>\n\n"
        f"📅 <b>BUGUNGI:</b>\n"
        f"• Tushum (Revenue): <b>{s_today['revenue']:,.0f} UZS</b>\n"
        f"• Sof foyda (Profit): <b>{s_today['profit']:,.0f} UZS</b>\n"
        f"• Buyurtmalar: <b>{s_today['orders']} ta</b> (✅ {s_today['success']} | ❌ {s_today['failed']})\n"
        f"• Yangi foydalanuvchilar: <b>{s_today['users']} ta</b>\n\n"
        f"🗓 <b>OXIRGI 7 KUN (HAFTALIK):</b>\n"
        f"• Tushum: <b>{s_week['revenue']:,.0f} UZS</b>\n"
        f"• Sof foyda: <b>{s_week['profit']:,.0f} UZS</b>\n"
        f"• Muvaffaqiyatli buyurtmalar: <b>{s_week['success']} ta</b>\n\n"
        f"📆 <b>OXIRGI 30 KUN (OYLIK):</b>\n"
        f"• Jami savdo: <b>{s_month['revenue']:,.0f} UZS</b>\n"
        f"• Jami sof foyda: <b>{s_month['profit']:,.0f} UZS</b>\n"
        f"• Jami buyurtmalar: <b>{s_month['orders']} ta</b>\n"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Bosh menyuga qaytish", callback_data="admin_menu_back")]]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "admin_settings")
async def admin_settings_view(call: CallbackQuery):
    """View and toggle bot settings."""
    settings_obj = await sync_to_async(BotSettings.load)()

    m_status = "🔴 YOQILGAN (Foydalanuvchilar uchun yopiq)" if settings_obj.maintenance_mode else "🟢 O'CHIRILGAN (Bot ochiq)"
    d_mode = "⚡️ AVTOMATIK (Midasbuy/Mock)" if settings_obj.default_delivery_mode == BotSettings.DeliveryMode.AUTO else "✋ MANUAL (Admin qo'lda yuboradi)"

    text = (
        f"⚙️ <b>BOT SOZLAMALARI</b>\n\n"
        f"• Texnik ta'mirlash rejimi: <b>{m_status}</b>\n"
        f"• Yetkazish usuli: <b>{d_mode}</b>\n"
        f"• Karta raqami: <code>{settings_obj.card_number}</code> ({settings_obj.card_owner})\n"
        f"• Referral bonusi: <b>{settings_obj.referral_bonus:,.0f} UZS</b>\n\n"
        f"Rejimlarni o'zgartirish uchun quyidagi tugmalarni bosing 👇"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Maintenance rejimini almashtirish", callback_data="toggle_maintenance")],
            [InlineKeyboardButton(text="🔄 Yetkazish rejimini (AUTO/MANUAL) almashtirish", callback_data="toggle_delivery_mode")],
            [InlineKeyboardButton(text="🔙 Bosh menyuga qaytish", callback_data="admin_menu_back")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance(call: CallbackQuery):
    """Toggle maintenance mode."""
    settings_obj = await sync_to_async(BotSettings.load)()
    settings_obj.maintenance_mode = not settings_obj.maintenance_mode
    await sync_to_async(settings_obj.save)(update_fields=["maintenance_mode"])
    await admin_settings_view(call)


@router.callback_query(F.data == "toggle_delivery_mode")
async def toggle_delivery_mode(call: CallbackQuery):
    """Toggle delivery mode between AUTO and MANUAL."""
    settings_obj = await sync_to_async(BotSettings.load)()
    if settings_obj.default_delivery_mode == BotSettings.DeliveryMode.AUTO:
        settings_obj.default_delivery_mode = BotSettings.DeliveryMode.MANUAL
    else:
        settings_obj.default_delivery_mode = BotSettings.DeliveryMode.AUTO
    await sync_to_async(settings_obj.save)(update_fields=["default_delivery_mode"])
    await admin_settings_view(call)


@router.callback_query(F.data == "admin_menu_back")
async def admin_menu_back(call: CallbackQuery, db_user):
    """Back to admin root menu."""
    welcome_text = (
        f"👑 <b>Admin Boshqaruv Paneli</b>\n\n"
        f"Xodim: <b>{db_user.display_name}</b> (ID: <code>{db_user.telegram_id}</code>)\n"
    )
    await call.message.edit_text(welcome_text, reply_markup=admin_menu_inline())
    await call.answer()


@router.callback_query(F.data == "admin_close")
async def admin_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer()
