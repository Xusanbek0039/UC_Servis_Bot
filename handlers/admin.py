import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS
import database as db
from keyboards.admin import (
    admin_menu_keyboard,
    admin_orders_filter_keyboard,
    admin_order_detail_keyboard,
    admin_products_management_keyboard,
    admin_single_product_keyboard,
    admin_settings_keyboard,
)
from states.order import AdminProductStates, AdminSettingsStates
from services.order_service import OrderService
from utils.helpers import format_order_summary, format_currency

router = Router()
logger = logging.getLogger("handlers.admin")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
@router.callback_query(F.data == "btn_admin_menu")
async def admin_dashboard(event: Message | CallbackQuery, state: FSMContext):
    """Admin control center."""
    user_id = event.from_user.id
    if not is_admin(user_id):
        if isinstance(event, Message):
            await event.answer("⛔️ Sizda admin huquqi yo'q!")
        else:
            await event.answer("⛔️ Ruxsat berilmagan!", show_alert=True)
        return

    await state.clear()
    text = (
        f"👑 <b>Admin Boshqaruv Paneli</b>\n\n"
        f"Admin ID: <code>{user_id}</code>\n"
        f"Boshqarish uchun quyidagi bo'limni tanlang 👇"
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=admin_menu_keyboard())
    else:
        await event.message.edit_text(text, reply_markup=admin_menu_keyboard())
        await event.answer()


# ==============================================================================
# 1. ADMIN ORDERS MANAGEMENT
# ==============================================================================

@router.callback_query(F.data == "adm_orders_menu")
async def admin_orders_menu(call: CallbackQuery):
    """Filter orders menu."""
    if not is_admin(call.from_user.id):
        return
    text = "📦 <b>Buyurtmalar bo'limi:</b>\nQaysi statusdagi buyurtmalarni ko'rmoqchisiz?"
    await call.message.edit_text(text, reply_markup=admin_orders_filter_keyboard())
    await call.answer()


@router.callback_query(F.data.startswith("adm_ord_flt:"))
async def filter_orders_list(call: CallbackQuery):
    """Display list of orders based on filter."""
    if not is_admin(call.from_user.id):
        return

    flt = call.data.split(":")[1]
    if flt == "ALL":
        orders = await db.get_recent_orders(limit=10)
        title = "📋 <b>Oxirgi barcha buyurtmalar:</b>\n\n"
    else:
        orders = await db.get_orders_by_status(flt, limit=10)
        title = f"📦 <b>Buyurtmalar ({flt}):</b>\n\n"

    if not orders:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Ortga", callback_data="adm_orders_menu")]]
        )
        await call.message.edit_text(title + "<i>Ushbu holatda buyurtmalar mavjud emas.</i>", reply_markup=kb)
        await call.answer()
        return

    buttons = []
    for o in orders:
        btn_text = f"{o['order_id']} | {o['product_name']} | {o['status']}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_ord:{o['order_id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="adm_orders_menu")])
    await call.message.edit_text(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()


@router.callback_query(F.data.startswith("adm_view_ord:"))
async def view_admin_order(call: CallbackQuery, bot: Bot):
    """Display single order details for admin with action buttons."""
    if not is_admin(call.from_user.id):
        return

    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    summary = format_order_summary(order)
    file_id = order.get("screenshot_file_id")

    # If order has a screenshot, send photo
    if file_id:
        try:
            await call.message.delete()
            await bot.send_photo(
                chat_id=call.from_user.id,
                photo=file_id,
                caption=summary,
                reply_markup=admin_order_detail_keyboard(order),
            )
            await call.answer()
            return
        except Exception:
            pass

    await call.message.edit_text(summary, reply_markup=admin_order_detail_keyboard(order))
    await call.answer()


@router.callback_query(F.data.startswith("adm_appr_ord:"))
async def approve_order_payment(call: CallbackQuery, bot: Bot):
    """Admin approves payment for an order."""
    if not is_admin(call.from_user.id):
        return

    order_id = call.data.split(":")[1]
    await OrderService.handle_payment_success(bot, order_id=order_id, provider_tx_id="ADMIN_APPROVED")
    await call.answer("✅ To'lov tasdiqlandi!", show_alert=True)
    order = await db.get_order(order_id)
    await call.message.edit_text(format_order_summary(order), reply_markup=admin_order_detail_keyboard(order))


@router.callback_query(F.data.startswith("adm_rej_ord:"))
async def reject_order_payment(call: CallbackQuery, bot: Bot):
    """Admin rejects payment / cancels order."""
    if not is_admin(call.from_user.id):
        return

    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order:
        return

    await db.update_order_status(order_id, "CANCELLED")
    await OrderService.notify_user(
        bot,
        order["user_id"],
        f"❌ <b>Buyurtmangiz bekor qilindi.</b>\n📦 Order: <code>{order_id}</code>\nTo'lov tasdiqlanmadi.",
    )
    await call.answer("❌ Buyurtma bekor qilindi.", show_alert=True)
    order = await db.get_order(order_id)
    await call.message.edit_text(format_order_summary(order), reply_markup=admin_order_detail_keyboard(order))


@router.callback_query(F.data.startswith("adm_deliver_ord:"))
async def deliver_order_manual(call: CallbackQuery, bot: Bot):
    """Admin marks manual order as delivered."""
    if not is_admin(call.from_user.id):
        return

    order_id = call.data.split(":")[1]
    await OrderService.mark_manual_delivered(bot, order_id=order_id)
    await call.answer("✅ UC yuborildi deb tasdiqlandi va foydalanuvchiga xabar berildi!", show_alert=True)
    order = await db.get_order(order_id)
    await call.message.edit_text(format_order_summary(order), reply_markup=admin_order_detail_keyboard(order))


# ==============================================================================
# 2. ADMIN PAYMENTS LIST (CHECKS)
# ==============================================================================

@router.callback_query(F.data == "adm_payments_menu")
async def admin_payments_list(call: CallbackQuery):
    """List orders waiting for check approval."""
    if not is_admin(call.from_user.id):
        return

    pending_orders = await db.get_orders_by_status("WAITING_PAYMENT", limit=10)
    if not pending_orders:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Admin menyu", callback_data="btn_admin_menu")]]
        )
        await call.message.edit_text("💳 <b>Tasdiqlash kutilayotgan to'lovlar mavjud emas.</b>", reply_markup=kb)
        await call.answer()
        return

    text = "💳 <b>Tasdiqlash kutilayotgan to'lovlar:</b>\n\n"
    buttons = []
    for o in pending_orders:
        btn_text = f"Chek {o['order_id']} — {format_currency(o['price'])}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_ord:{o['order_id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 Admin menyu", callback_data="btn_admin_menu")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()


# ==============================================================================
# 3. ADMIN PRODUCTS MANAGEMENT
# ==============================================================================

@router.callback_query(F.data == "adm_products_menu")
async def admin_products_list(call: CallbackQuery, state: FSMContext):
    """List products with editing options."""
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    products = await db.get_all_products()
    text = "🎮 <b>UC PAKETLARI BOSHQARUVI:</b>\n\nPaketni tahrirlash uchun ustiga bosing:"
    await call.message.edit_text(text, reply_markup=admin_products_management_keyboard(products))
    await call.answer()


@router.callback_query(F.data.startswith("adm_prod_view:"))
async def admin_view_single_product(call: CallbackQuery):
    """View options for one product."""
    if not is_admin(call.from_user.id):
        return
    prod_id = int(call.data.split(":")[1])
    product = await db.get_product(prod_id)
    if not product:
        await call.answer("Paket topilmadi!", show_alert=True)
        return

    status_str = "🟢 Faol" if product["is_active"] == 1 else "🔴 Nofaol"
    text = (
        f"💎 <b>Paket ma'lumotlari:</b>\n\n"
        f"Nomi: <b>{product['name']}</b>\n"
        f"UC miqdori: <b>{product['uc_amount']} UC</b>\n"
        f"Sotuv narxi: <b>{format_currency(product['price'])}</b>\n"
        f"Tannarxi: <b>{format_currency(product['cost_price'])}</b>\n"
        f"Holati: <b>{status_str}</b>\n"
    )
    await call.message.edit_text(text, reply_markup=admin_single_product_keyboard(prod_id, product["is_active"]))
    await call.answer()


@router.callback_query(F.data.startswith("adm_prod_toggle:"))
async def toggle_product_handler(call: CallbackQuery):
    """Toggle active/inactive status of product."""
    if not is_admin(call.from_user.id):
        return
    prod_id = int(call.data.split(":")[1])
    await db.toggle_product_status(prod_id)
    await call.answer("Holat o'zgartirildi!")
    await admin_view_single_product(call)


@router.callback_query(F.data.startswith("adm_prod_del:"))
async def delete_product_handler(call: CallbackQuery, state: FSMContext):
    """Delete a product."""
    if not is_admin(call.from_user.id):
        return
    prod_id = int(call.data.split(":")[1])
    await db.delete_product(prod_id)
    await call.answer("Paket o'chirildi!", show_alert=True)
    await admin_products_list(call, state)


@router.callback_query(F.data.startswith("adm_prod_chg_price:"))
async def prompt_new_price(call: CallbackQuery, state: FSMContext):
    """Prompt admin for new product price."""
    if not is_admin(call.from_user.id):
        return
    prod_id = int(call.data.split(":")[1])
    await state.update_data(editing_product_id=prod_id)
    await state.set_state(AdminProductStates.WAITING_NEW_PRICE)
    await call.message.edit_text(
        "💰 <b>Paket uchun yangi narxni kiriting (UZS):</b>\n<i>Masalan: 145000</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="adm_products_menu")]]),
    )
    await call.answer()


@router.message(AdminProductStates.WAITING_NEW_PRICE)
async def save_new_price(message: Message, state: FSMContext):
    """Save new product price."""
    if not is_admin(message.from_user.id):
        return
    val = message.text.strip().replace(" ", "")
    try:
        new_price = float(val)
    except ValueError:
        await message.answer("⚠️ Iltimos, faqat raqam kiriting:")
        return

    data = await state.get_data()
    prod_id = data.get("editing_product_id")
    await db.update_product_price(prod_id, new_price)
    await state.clear()
    await message.answer(f"✅ Narx muvaffaqiyatli yangilandi: <b>{format_currency(new_price)}</b>", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_add_product")
async def start_add_product(call: CallbackQuery, state: FSMContext):
    """Begin adding a new UC package."""
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminProductStates.WAITING_NAME)
    await call.message.edit_text(
        "➕ <b>Yangi UC paketi qo'shish</b>\n\n1. Paket nomini kiriting (masalan: <code>60 UC</code>):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="adm_products_menu")]]),
    )
    await call.answer()


@router.message(AdminProductStates.WAITING_NAME)
async def process_new_product_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    await state.update_data(new_prod_name=name)
    await state.set_state(AdminProductStates.WAITING_UC_AMOUNT)
    await message.answer("2. UC miqdorini kiriting (masalan: <code>60</code>):")


@router.message(AdminProductStates.WAITING_UC_AMOUNT)
async def process_new_product_uc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Faqat raqam kiriting:")
        return
    await state.update_data(new_prod_uc=int(val))
    await state.set_state(AdminProductStates.WAITING_PRICE)
    await message.answer("3. Sotuv narxini kiriting (UZS, masalan: <code>15000</code>):")


@router.message(AdminProductStates.WAITING_PRICE)
async def process_new_product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    val = message.text.strip().replace(" ", "")
    try:
        price = float(val)
    except ValueError:
        await message.answer("⚠️ Narxni faqat raqamda kiriting:")
        return

    data = await state.get_data()
    name = data.get("new_prod_name")
    uc_amount = data.get("new_prod_uc")

    await db.add_product(name=name, uc_amount=uc_amount, price=price)
    await state.clear()
    await message.answer(f"🎉 <b>Yangi paket muvaffaqiyatli qo'shildi:</b>\n{name} — {format_currency(price)}", reply_markup=admin_menu_keyboard())


# ==============================================================================
# 4. ADMIN USERS & STATISTICS
# ==============================================================================

@router.callback_query(F.data == "adm_users_menu")
async def admin_users_menu(call: CallbackQuery):
    """View registered users."""
    if not is_admin(call.from_user.id):
        return
    total_users = await db.get_all_users_count()
    recent = await db.get_recent_users(limit=8)

    text = f"👥 <b>Foydalanuvchilar:</b>\n\nJami ro'yxatdan o'tganlar: <b>{total_users} ta</b>\n\n<b>So'nggi a'zolar:</b>\n"
    for u in recent:
        uname = f"@{u['username']}" if u['username'] else u['first_name']
        text += f"• {uname} (ID: <code>{u['telegram_id']}</code>) | Balans: {format_currency(u['balance'])}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Admin menyu", callback_data="btn_admin_menu")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "adm_stats")
async def admin_statistics(call: CallbackQuery):
    """View business statistics."""
    if not is_admin(call.from_user.id):
        return
    stats = await db.get_order_stats()
    text = (
        f"📊 <b>PUBG UC DO'KONI STATISTIKASI</b>\n\n"
        f"📅 <b>Bugungi ko'rsatkichlar:</b>\n"
        f"• Buyurtmalar: <b>{stats['today_orders']} ta</b>\n"
        f"• Tushum: <b>{format_currency(stats['today_revenue'])}</b>\n\n"
        f"📈 <b>Jami ko'rsatkichlar:</b>\n"
        f"• Jami buyurtmalar: <b>{stats['total_orders']} ta</b>\n"
        f"• Muvaffaqiyatli yakunlangan: <b>{stats['completed_orders']} ta</b>\n"
        f"• Bekor qilingan / Xato: <b>{stats['cancelled_orders']} ta</b>\n"
        f"• Jami umumiy tushum: <b>{format_currency(stats['total_revenue'])}</b>\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Admin menyu", callback_data="btn_admin_menu")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


# ==============================================================================
# 5. ADMIN SETTINGS
# ==============================================================================

@router.callback_query(F.data == "adm_settings_menu")
async def admin_settings_menu(call: CallbackQuery, state: FSMContext):
    """View and change settings."""
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    card_num = await db.get_setting("card_number", "8600 0000 0000 1234")
    card_owner = await db.get_setting("card_owner", "PUBG OPERATOR")
    bank_name = await db.get_setting("bank_name", "Kapitalbank")
    support_username = await db.get_setting("support_username", "@PubgUcSupport")
    delivery_mode = await db.get_setting("delivery_mode", "MANUAL")

    text = (
        f"⚙️ <b>BOT SOZLAMALARI:</b>\n\n"
        f"💳 Karta: <code>{card_num}</code>\n"
        f"👤 Egasi: <b>{card_owner}</b>\n"
        f"🏦 Bank: <b>{bank_name}</b>\n"
        f"📞 Support: <b>{support_username}</b>\n"
        f"🔧 Yetkazish rejimi: <b>{delivery_mode}</b>\n"
    )
    await call.message.edit_text(text, reply_markup=admin_settings_keyboard())
    await call.answer()


@router.callback_query(F.data == "adm_set_delivery_mode")
async def toggle_delivery_mode(call: CallbackQuery, state: FSMContext):
    """Toggle delivery mode between AUTO and MANUAL."""
    if not is_admin(call.from_user.id):
        return
    current = await db.get_setting("delivery_mode", "MANUAL")
    new_mode = "AUTO" if current == "MANUAL" else "MANUAL"
    await db.set_setting("delivery_mode", new_mode)
    await call.answer(f"Yetkazish rejimi o'zgartirildi: {new_mode}")
    await admin_settings_menu(call, state)


@router.callback_query(F.data == "adm_set_card_num")
async def prompt_set_card_num(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminSettingsStates.WAITING_CARD_NUMBER)
    await call.message.edit_text("Yangi karta raqamini kiriting:")
    await call.answer()


@router.message(AdminSettingsStates.WAITING_CARD_NUMBER)
async def save_card_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("card_number", message.text.strip())
    await state.clear()
    await message.answer("✅ Karta raqami saqlandi!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_set_card_owner")
async def prompt_set_card_owner(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminSettingsStates.WAITING_CARD_OWNER)
    await call.message.edit_text("Karta egasining ism-familiyasini kiriting:")
    await call.answer()


@router.message(AdminSettingsStates.WAITING_CARD_OWNER)
async def save_card_owner(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("card_owner", message.text.strip())
    await state.clear()
    await message.answer("✅ Karta egasi saqlandi!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_set_bank_name")
async def prompt_set_bank_name(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminSettingsStates.WAITING_BANK_NAME)
    await call.message.edit_text("Bank nomini kiriting:")
    await call.answer()


@router.message(AdminSettingsStates.WAITING_BANK_NAME)
async def save_bank_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("bank_name", message.text.strip())
    await state.clear()
    await message.answer("✅ Bank nomi saqlandi!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_set_support")
async def prompt_set_support(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminSettingsStates.WAITING_SUPPORT_USERNAME)
    await call.message.edit_text("Support username kiriting (masalan: @PubgSupport):")
    await call.answer()


@router.message(AdminSettingsStates.WAITING_SUPPORT_USERNAME)
async def save_support(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("support_username", message.text.strip())
    await state.clear()
    await message.answer("✅ Support username saqlandi!", reply_markup=admin_menu_keyboard())
