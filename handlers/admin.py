import logging
import html
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS, MAX_PROFIT_PERCENT
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
from services.proof_channel import ProofChannelService
from services.order_reminder import delete_reminder_messages
from utils.helpers import format_order_summary, format_currency, DIVIDER, SUB_DIVIDER, get_status_badge
from emojis import E
from services.pricing import calculate_price, product_sellable
from services.price_monitor import refresh_product_prices

router = Router()
logger = logging.getLogger("handlers.admin")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
@router.callback_query(F.data == "btn_admin_menu")
async def admin_dashboard(event: Message | CallbackQuery, state: FSMContext):
    """Admin control center dashboard."""
    user_id = event.from_user.id
    if not is_admin(user_id):
        if isinstance(event, Message):
            await event.answer("⛔️ Sizda administratorlik huquqi yo'q!")
        else:
            await event.answer("⛔️ Ruxsat berilmagan!", show_alert=True)
        return

    await state.clear()
    text = (
        f"{DIVIDER}\n"
        f"   {E('settings')} <b>ADMIN BOSHQARUV PANELI</b>\n"
        f"{DIVIDER}\n\n"
        f"👤 <b>Administrator:</b> <code>{user_id}</code>\n\n"
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
    text = (
        f"{DIVIDER}\n"
        f"   {E('order')} <b>BUYURTMALAR BOSHQARUVI</b>\n"
        f"{DIVIDER}\n\n"
        f"Qaysi statusdagi buyurtmalarni ko'rmoqchisiz? Tanlang 👇"
    )
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
        title = (
            f"{DIVIDER}\n"
            f"   📋 <b>SO'NGGI BARCHA BUYURTMALAR</b>\n"
            f"{DIVIDER}\n\n"
        )
    else:
        orders = await db.get_orders_by_status(flt, limit=10)
        badge = get_status_badge(flt)
        title = (
            f"{DIVIDER}\n"
            f"   📦 <b>BUYURTMALAR ({badge})</b>\n"
            f"{DIVIDER}\n\n"
        )

    if not orders:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Ortga", callback_data="adm_orders_menu")]]
        )
        await call.message.edit_text(title + "<i>Ushbu holatda buyurtmalar topilmadi.</i>", reply_markup=kb)
        await call.answer()
        return

    buttons = []
    for o in orders:
        badge = get_status_badge(o.get("status", ""))
        btn_text = f"#{o['order_id']} | {o.get('product_name', 'UC')} ({badge})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_ord:{o['order_id']}")])

    buttons.append([InlineKeyboardButton(text=f"{E('back', True)} Ortga", callback_data="adm_orders_menu")])
    await call.message.edit_text(title + "Ko'rish uchun buyurtmani tanlang 👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
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

    if order.get("payment_status", "PENDING") != "PENDING" or order.get("status") != "WAITING_PAYMENT":
        await call.answer("To'lov qabul qilingan buyurtmani bekor qilmang; refund/manual review qiling.", show_alert=True)
        return

    await db.transition_order(order_id, ["WAITING_PAYMENT"], "CANCELLED", payment_status="FAILED")
    await OrderService.notify_user(
        bot,
        order["user_id"],
        f"{DIVIDER}\n"
        f"   {E('cross')} <b>BUYURTMA BEKOR QILINDI</b>\n"
        f"{DIVIDER}\n\n"
        f"📦 Buyurtma kodi: <code>{order_id}</code>\n"
        f"To'lov tasdiqlanmadi yoki bekor qilindi.\n\n"
        f"Savollaringiz bo'lsa, adminga murojaat qiling.",
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
    completed = await OrderService.mark_manual_delivered(bot, order_id=order_id)
    await call.answer("✅ UC yuborildi deb tasdiqlandi! Eslatmalar to'xtatildi." if completed else "Order yakunlashga tayyor emas yoki allaqachon yakunlangan.", show_alert=True)
    order = await db.get_order(order_id)
    if order and order.get("delivery_status") == "COMPLETED":
        await delete_reminder_messages(bot, order_id, keep=(call.message.chat.id, call.message.message_id))
    try:
        if call.message.photo or call.message.document:
            await call.message.edit_caption(caption=format_order_summary(order), reply_markup=admin_order_detail_keyboard(order))
        else:
            await call.message.edit_text(format_order_summary(order), reply_markup=admin_order_detail_keyboard(order))
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_proof_send:") | F.data.startswith("adm_proof_upd:"))
async def admin_trigger_proof(call: CallbackQuery, bot: Bot):
    """Admin manually dispatches or updates proof post in the channel."""
    if not is_admin(call.from_user.id):
        return

    order_id = call.data.split(":")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order.get("delivery_status") != "COMPLETED":
        await call.answer("Isbot faqat yetkazish yakunlangandan keyin yuboriladi.", show_alert=True)
        return
    target_proof_status = "COMPLETED"

    success = await ProofChannelService.send_or_update_proof(
        bot=bot,
        order_id=order_id,
        new_proof_status=target_proof_status,
        force=True,
    )

    if success:
        await call.answer("✅ Isbot posti kanalga yuborildi / yangilandi!", show_alert=True)
    else:
        await call.answer("⚠️ Kanalga yuborib bo'lmadi. PROOF_CHANNEL_ID va bot huquqlarini tekshiring.", show_alert=True)

    updated_order = await db.get_order(order_id)
    await call.message.edit_text(format_order_summary(updated_order), reply_markup=admin_order_detail_keyboard(updated_order))


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
            inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Admin panel", callback_data="btn_admin_menu")]]
        )
        text = (
            f"{DIVIDER}\n"
            f"   {E('payment')} <b>TO'LOV CHEKLARI</b>\n"
            f"{DIVIDER}\n\n"
            f"Hozirda tasdiqlash kutilayotgan to'lov cheklari mavjud emas."
        )
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
        return

    text = (
        f"{DIVIDER}\n"
        f"   {E('payment')} <b>TASDIQLASH KUTILAYOTGAN TO'LOVLAR</b>\n"
        f"{DIVIDER}\n\n"
        f"Tekshirish uchun buyurtmani tanlang 👇"
    )
    buttons = []
    for o in pending_orders:
        btn_text = f"Chek #{o['order_id']} — {format_currency(o['price'])}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_view_ord:{o['order_id']}")])

    buttons.append([InlineKeyboardButton(text=f"{E('back', True)} Admin panel", callback_data="btn_admin_menu")])
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
    pricing_mode = await db.get_pricing_mode()
    rows = []
    for product in products:
        manual = bool(product.get("manual_block"))
        reason = product.get("auto_block_reason") or ""
        status = "🔴 MANUAL BLOCK" if manual else ("🟢 ACTIVE" if product_sellable(product, pricing_mode) else (f"🔴 {reason}" if reason else "🔴 NARX KIRITILMAGAN"))
        if pricing_mode == "MANUAL":
            rows.append(f"📦 <b>{html.escape(product.get('name', 'UC'))}</b> · Tannarx {format_currency(product.get('cost_price', 0))} · Sotuv {format_currency(product.get('price', 0))} · {status}")
        else:
            rows.append(
                f"📦 <b>{html.escape(product.get('name', 'UC'))}</b> · Cost {format_currency(product.get('cost_price', 0))} · "
                f"+{product.get('profit_percent', 0):g}% · MAX {format_currency(product.get('max_price', 0))} · {status}"
            )
    product_rows = "\n".join(rows)
    text = (
        f"{DIVIDER}\n"
        f"   {E('uc')} <b>UC PAKETLARI BOSHQARUVI</b>\n"
        f"{DIVIDER}\n\n"
        f"{product_rows}\n\nPaketni tahrirlash uchun ustiga bosing yoki yangisini qo'shing 👇"
    )
    await call.message.edit_text(text, reply_markup=admin_products_management_keyboard(products, pricing_mode))
    await call.answer()


@router.callback_query(F.data == "adm_supplier_refresh")
async def admin_refresh_supplier_prices(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    await refresh_product_prices(bot)
    await call.answer("Tekshiruv tugadi. Sababini paket kartochkasidan ko'ring.", show_alert=True)


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

    manual = bool(product.get("manual_block"))
    auto_reason = product.get("auto_block_reason") or ""
    pricing_mode = await db.get_pricing_mode()
    status_str = "🔴 MANUAL BLOCK" if manual else ("🟢 ACTIVE" if product_sellable(product, pricing_mode) else (f"🔴 {auto_reason}" if auto_reason else "🔴 NARX KIRITILMAGAN"))
    if pricing_mode == "MANUAL":
        pricing_details = (
            f"💰 <b>Sotuv narxi:</b> {format_currency(product.get('price', 0))}\n"
            f"📦 <b>Tannarx (ma'lumot uchun):</b> {format_currency(product.get('cost_price', 0))}\n"
            "💵 <b>Narxlash:</b> Qo'lda\n"
        )
    else:
        pricing_details = (
            f"💰 <b>Sotuv narxi:</b> {format_currency(product['price'])}\n"
            f"📦 <b>Tannarxi:</b> {format_currency(product.get('cost_price', 0))}\n"
            f"📈 <b>Ustama:</b> {product.get('profit_percent', 0):g}%\n"
            f"🔴 <b>Max narx:</b> {format_currency(product.get('max_price', 0)) if product.get('max_price', 0) else 'Belgilanmagan'}\n"
            f"💵 <b>LioGames:</b> ${float(product.get('supplier_price_usd', 0)):.2f} · USD kurs: {await db.get_setting('usd_rate', '—')} UZS\n"
            f"🛠 <b>Tekshiruv:</b> <code>{html.escape(str(product.get('supplier_error') or 'OK'))}</code>\n"
        )
    text = (
        f"{DIVIDER}\n"
        f"   {E('uc')} <b>PAKET: {product['name']}</b>\n"
        f"{DIVIDER}\n\n"
        f"{E('uc')} <b>UC miqdori:</b> <b>{product['uc_amount']} UC</b>\n"
        f"{pricing_details}"
        f"📊 <b>Holati:</b> <b>{status_str}</b>\n"
        f"{DIVIDER}"
    )
    await call.message.edit_text(text, reply_markup=admin_single_product_keyboard(prod_id, product.get("is_active", 1), pricing_mode))
    await call.answer()


@router.callback_query(F.data.startswith("adm_profit:"))
async def prompt_profit_percent(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    product_id = int(call.data.split(":")[1])
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminProductStates.WAITING_PROFIT_PERCENT)
    await call.message.edit_text(f"📈 Yangi ustama foizini yuboring (0–{MAX_PROFIT_PERCENT:g}%). Masalan: 30")
    await call.answer()


@router.message(AdminProductStates.WAITING_PROFIT_PERCENT)
async def save_profit_percent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        value = float((message.text or "").strip().replace(",", "."))
        if not 0 <= value <= MAX_PROFIT_PERCENT:
            raise ValueError
    except ValueError:
        await message.answer(f"Foiz 0 dan {MAX_PROFIT_PERCENT:g}% gacha bo'lgan son bo'lishi kerak.")
        return
    product_id = (await state.get_data()).get("editing_product_id")
    await db.set_product_pricing(product_id, profit_percent=value)
    await _recalculate_product(product_id)
    await state.clear()
    await message.answer("✅ Ustama saqlandi. Narx yangilandi.", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data.startswith("adm_max_price:"))
async def prompt_max_price(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    product_id = int(call.data.split(":")[1])
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminProductStates.WAITING_MAX_PRICE)
    await call.message.edit_text("💰 Max narxni so'mda faqat musbat butun son bilan yuboring. Masalan: 13500")
    await call.answer()


@router.message(AdminProductStates.WAITING_MAX_PRICE)
async def save_max_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").replace(" ", "").replace(",", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("Max narx 0 dan katta, faqat raqam bo'lishi kerak.")
        return
    product_id = (await state.get_data()).get("editing_product_id")
    await db.set_product_pricing(product_id, max_price=float(raw))
    await _recalculate_product(product_id)
    await state.clear()
    await message.answer("✅ Max narx saqlandi. Paket narxi qayta hisoblandi.", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data.startswith("adm_manual_block:"))
async def toggle_manual_block(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    product_id = int(call.data.split(":")[1])
    product = await db.get_product(product_id)
    if not product:
        await call.answer("Paket topilmadi", show_alert=True)
        return
    blocked = not bool(product.get("manual_block"))
    await db.set_product_pricing(product_id, manual_block=blocked)
    await call.answer("Manual blok yoqildi" if blocked else "Paket ochildi", show_alert=True)
    await admin_view_single_product(call)


async def _recalculate_product(product_id: int):
    product = await db.get_product(product_id)
    if not product or float(product.get("supplier_price_usd", 0)) <= 0:
        return
    rate = float(await db.get_setting("usd_rate", "0") or 0)
    quote = calculate_price(product["supplier_price_usd"], rate, product.get("profit_percent", 0), product.get("max_price", 0))
    await db.set_product_pricing(product_id, cost_price=float(quote.cost_uzs), price=float(quote.sale_price), auto_block_reason=quote.blocked_reason)


@router.callback_query(F.data == "adm_toggle_global_sales")
async def toggle_global_sales(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    enabled = await db.global_sales_enabled()
    await db.set_setting("global_sales_enabled", "false" if enabled else "true")
    await call.answer("Yangi savdolar to'xtatildi" if enabled else "Yangi savdolar yoqildi", show_alert=True)
    await call.message.edit_text(
        f"{DIVIDER}\n👑 <b>ADMIN PANEL</b>\n{DIVIDER}\n\n"
        f"Global savdo: <b>{'ON 🟢' if not enabled else 'OFF 🔴'}</b>",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("adm_prod_toggle:"))
async def toggle_product_handler(call: CallbackQuery):
    """Toggle active/inactive status of product."""
    if not is_admin(call.from_user.id):
        return
    prod_id = int(call.data.split(":")[1])
    await db.toggle_product_status(prod_id)
    await call.answer("Paket holati o'zgartirildi!")
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
        f"{DIVIDER}\n"
        f"{E('edit')} <b>PAKET NARXINI O'ZGARTIRISH</b>\n"
        f"{DIVIDER}\n\n"
        f"Yangi narxni so'mda (UZS) kiriting:\n<i>Masalan: 140000</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_products_menu")]]),
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
        await message.answer("⚠️ Iltimos, narxni faqat raqamlarda kiriting:")
        return
    if new_price <= 0:
        await message.answer("⚠️ Narx 0 dan katta bo'lishi kerak:")
        return

    data = await state.get_data()
    prod_id = data.get("editing_product_id")
    await db.update_product_price(prod_id, new_price)
    await state.clear()
    await message.answer(f"✅ Narx saqlandi: <b>{format_currency(new_price)}</b>. Manual narxlashda paket shu narxda ko'rinadi.", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_add_product")
async def start_add_product(call: CallbackQuery, state: FSMContext):
    """Begin adding a new UC package."""
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminProductStates.WAITING_NAME)
    await call.message.edit_text(
        f"{DIVIDER}\n"
        f"➕ <b>YANGI UC PAKETI QO'SHISH</b>\n"
        f"{DIVIDER}\n\n"
        f"1. Paket nomini kiriting (masalan: <code>60 UC</code>):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_products_menu")]]),
    )
    await call.answer()


@router.message(AdminProductStates.WAITING_NAME)
async def process_new_product_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    await state.update_data(new_prod_name=name)
    await state.set_state(AdminProductStates.WAITING_UC_AMOUNT)
    await message.answer("2. UC miqdorini kiriting (faqat raqam, masalan: <code>60</code>):")


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

    text = (
        f"{DIVIDER}\n"
        f"   {E('users')} <b>FOYDALANUVCHILAR</b>\n"
        f"{DIVIDER}\n\n"
        f"👥 <b>Jami a'zolar:</b> <b>{total_users} nafar</b>\n\n"
        f"<b>So'nggi foydalanuvchilar:</b>\n"
    )
    for u in recent:
        uname = f"@{u['username']}" if u.get("username") else (u.get("first_name") or "User")
        total_uc = u.get("total_uc", 0)
        uc_part = f" | {E('uc')} <b>{total_uc:,} UC</b>" if total_uc > 0 else " | 0 UC"
        text += f"• {uname} (ID: <code>{u.get('telegram_id')}</code>){uc_part} | Balans: {format_currency(u.get('balance', 0))}\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Eng ko'p UC olganlar (Top)", callback_data="adm_top_buyers")],
            [InlineKeyboardButton(text=f"{E('back', True)} Admin panel", callback_data="btn_admin_menu")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "adm_top_buyers")
async def admin_top_buyers(call: CallbackQuery):
    """View top UC buyers leaderboard."""
    if not is_admin(call.from_user.id):
        return
    top_users = await db.get_top_uc_users(limit=15)

    text = (
        f"{DIVIDER}\n"
        f"   🏆 <b>ENG KO'P UC XARID QILGANLAR</b>\n"
        f"{DIVIDER}\n\n"
    )
    if not top_users:
        text += "<i>Hozircha muvaffaqiyatli buyurtmalar mavjud emas.</i>\n"
    else:
        medals = ["🥇", "🥈", "🥉"]
        for idx, u in enumerate(top_users, start=1):
            badge = medals[idx - 1] if idx <= 3 else f"<b>{idx}.</b>"
            uname = f"@{u['username']}" if u.get("username") else u.get("first_name", "User")
            text += (
                f"{badge} {uname} (ID: <code>{u['telegram_id']}</code>)\n"
                f"   └── {E('uc')} Jami: <b>{u['total_uc']:,} UC</b> | Balans: {format_currency(u.get('balance', 0))}\n"
            )

    text += f"\n{DIVIDER}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{E('back', True)} Foydalanuvchilar", callback_data="adm_users_menu")],
            [InlineKeyboardButton(text=f"{E('home', True)} Admin panel", callback_data="btn_admin_menu")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "adm_stats")
async def admin_statistics(call: CallbackQuery):
    """View business statistics."""
    if not is_admin(call.from_user.id):
        return
    stats = await db.get_order_stats()
    proof_stats = await db.get_proof_stats()
    users_count = await db.get_all_users_count()
    text = (
        f"{DIVIDER}\n"
        f"   {E('stats')} <b>TIZIM STATISTIKASI</b>\n"
        f"{DIVIDER}\n\n"
        f"📅 <b>Bugungi ko'rsatkichlar:</b>\n"
        f"• Buyurtmalar: <b>{stats['today_orders']} ta</b>\n"
        f"• Tushum: <b>{format_currency(stats['today_revenue'])}</b>\n\n"
        f"📈 <b>Umumiy ko'rsatkichlar:</b>\n"
        f"• Jami buyurtmalar: <b>{stats['total_orders']} ta</b>\n"
        f"• Bajarilgan: <b>{stats['completed_orders']} ta</b>\n"
        f"• Bekor qilingan: <b>{stats['cancelled_orders']} ta</b>\n"
        f"• Jami tushum: <b>{format_currency(stats['total_revenue'])}</b>\n"
        f"{SUB_DIVIDER}\n"
        f"📢 <b>Isbot kanali statistikasi:</b>\n"
        f"• Jami bajarilgan: <b>{proof_stats['total_completed']} ta</b>\n"
        f"• Isbot yuborilgan: <b>{proof_stats['proof_sent']} ta</b>\n"
        f"• Isbot kutilmoqda: <b>{proof_stats['proof_not_sent']} ta</b>\n"
        f"{SUB_DIVIDER}\n"
        f"👥 <b>Foydalanuvchilar soni:</b> <b>{users_count} nafar</b>\n"
        f"{DIVIDER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Admin panel", callback_data="btn_admin_menu")]])
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
    payment_destinations = {
        "VISA": await db.get_setting("payment_visa", "Sozlanmagan"),
        "HUMO": await db.get_setting("payment_humo", "Sozlanmagan"),
        "MASTERCARD": await db.get_setting("payment_mastercard", "Sozlanmagan"),
        "UZCARD": await db.get_setting("payment_uzcard", "Sozlanmagan"),
        "CLICK": await db.get_setting("payment_click", "Sozlanmagan"),
        "PAYME": await db.get_setting("payment_payme", "Sozlanmagan"),
        "PAYNET": await db.get_setting("payment_paynet", "Sozlanmagan"),
    }
    support_username = await db.get_setting("support_username", "@PubgUcSupport")
    proof_channel_url = await db.get_setting("proof_channel_url", "Sozlanmagan")
    delivery_mode = await db.get_setting("delivery_mode", "MANUAL")

    text = (
        f"{DIVIDER}\n"
        f"   {E('settings')} <b>TIZIM SOZLAMALARI</b>\n"
        f"{DIVIDER}\n\n"
        f"💳 <b>Karta:</b> <code>{card_num}</code>\n"
        f"👤 <b>Egasi:</b> <b>{card_owner}</b>\n"
        f"{E('bank')} <b>Bank:</b> {bank_name}\n"
        f"{E('visa')} <b>Visa:</b> {payment_destinations['VISA']}\n"
        f"{E('humo')} <b>Humo:</b> {payment_destinations['HUMO']}\n"
        f"{E('mastercard')} <b>Mastercard:</b> {payment_destinations['MASTERCARD']}\n"
        f"{E('uzcard')} <b>Uzcard:</b> {payment_destinations['UZCARD']}\n"
        f"{E('click')} <b>Click:</b> {payment_destinations['CLICK']}\n"
        f"{E('payme')} <b>Payme:</b> {payment_destinations['PAYME']}\n"
        f"{E('paynet')} <b>Paynet:</b> {payment_destinations['PAYNET']}\n"
        f"📞 <b>Support:</b> {support_username}\n"
        f"📢 <b>Isbot kanali:</b> {html.escape(proof_channel_url)}\n"
        f"💵 <b>Narxlash manbasi:</b> <b>{await db.get_pricing_mode()}</b>\n"
        f"🔧 <b>Yetkazish rejimi:</b> <b>{delivery_mode}</b>\n"
        f"{SUB_DIVIDER}\n"
        f"O'zgartirish uchun kerakli tugmani bosing 👇"
    )
    await call.message.edit_text(text, reply_markup=admin_settings_keyboard())
    await call.answer()


@router.callback_query(F.data.in_({"adm_set_delivery_mode", "adm_toggle_delivery"}))
async def toggle_delivery_mode(call: CallbackQuery, state: FSMContext):
    """Toggle delivery mode between AUTO and MANUAL."""
    if not is_admin(call.from_user.id):
        return
    current = await db.get_setting("delivery_mode", "MANUAL")
    new_mode = "AUTO" if current == "MANUAL" else "MANUAL"
    await db.set_setting("delivery_mode", new_mode)
    await call.answer(f"Yetkazish rejimi o'zgartirildi: {new_mode}", show_alert=True)
    await admin_settings_menu(call, state)


@router.callback_query(F.data == "adm_toggle_pricing_mode")
async def toggle_pricing_mode(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    current = await db.get_pricing_mode()
    new_mode = "LIOGAMES" if current == "MANUAL" else "MANUAL"
    await db.set_pricing_mode(new_mode)
    if new_mode == "LIOGAMES":
        await refresh_product_prices(call.bot)
        message = "LioGames narxlashi yoqildi. Paketlar API narxi tasdiqlangach ochiladi."
    else:
        message = "Manual narxlash yoqildi. LioGames narx tekshiruvi to'xtatildi; sotuv narxlarini admin belgilaydi."
    await call.answer(message, show_alert=True)
    await admin_settings_menu(call, state)


@router.callback_query(F.data == "adm_set_card_num")
async def prompt_set_card_num(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminSettingsStates.WAITING_CARD_NUMBER)
    await call.message.edit_text(
        f"{DIVIDER}\n"
        f"{E('card')} <b>Yangi karta raqamini kiriting:</b>\n"
        f"{DIVIDER}\n<i>Masalan: 8600 1234 5678 9012</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_settings_menu")]]),
    )
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
    await call.message.edit_text(
        f"{DIVIDER}\n"
        f"{E('profile')} <b>Karta egasining ism-familiyasini kiriting:</b>\n"
        f"{DIVIDER}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_settings_menu")]]),
    )
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
    await call.message.edit_text(
        f"{DIVIDER}\n"
        f"🏦 <b>Bank nomini kiriting:</b>\n"
        f"{DIVIDER}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_settings_menu")]]),
    )
    await call.answer()


@router.message(AdminSettingsStates.WAITING_BANK_NAME)
async def save_bank_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("bank_name", message.text.strip())
    await state.clear()
    await message.answer("✅ Bank nomi saqlandi!", reply_markup=admin_menu_keyboard())


PAYMENT_SETTING_KEYS = {
    "VISA": "payment_visa",
    "HUMO": "payment_humo",
    "MASTERCARD": "payment_mastercard",
    "UZCARD": "payment_uzcard",
    "CLICK": "payment_click",
    "PAYME": "payment_payme",
    "PAYNET": "payment_paynet",
}


@router.callback_query(F.data.startswith("adm_set_payment:"))
async def prompt_set_payment_detail(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    method = call.data.split(":", 1)[1]
    if method not in PAYMENT_SETTING_KEYS:
        await call.answer("To'lov turi topilmadi.", show_alert=True)
        return
    await state.set_state(AdminSettingsStates.WAITING_PAYMENT_DETAIL)
    await state.update_data(payment_setting_method=method)
    await call.message.edit_text(
        f"{DIVIDER}\n{E('card')} <b>{method} uchun to'lov rekvizitini yuboring:</b>\n{DIVIDER}\n"
        "Karta raqami, telefon raqami yoki to'lov hisobini yuborishingiz mumkin.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_settings_menu")]]),
    )
    await call.answer()


@router.message(AdminSettingsStates.WAITING_PAYMENT_DETAIL)
async def save_payment_detail(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    method = data.get("payment_setting_method")
    if method not in PAYMENT_SETTING_KEYS:
        await state.clear()
        return
    await db.set_setting(PAYMENT_SETTING_KEYS[method], message.text.strip())
    await state.clear()
    await message.answer(f"✅ {method} to'lov rekviziti saqlandi!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_set_support")
async def prompt_set_support(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminSettingsStates.WAITING_SUPPORT_USERNAME)
    await call.message.edit_text(
        f"{DIVIDER}\n"
        f"{E('support')} <b>Support username kiriting:</b>\n"
        f"{DIVIDER}\n<i>Masalan: @PubgSupport</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_settings_menu")]]),
    )
    await call.answer()


@router.message(AdminSettingsStates.WAITING_SUPPORT_USERNAME)
async def save_support(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("support_username", message.text.strip())
    await state.clear()
    await message.answer("✅ Support username saqlandi!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm_set_proof_channel")
async def prompt_set_proof_channel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminSettingsStates.WAITING_PROOF_CHANNEL_URL)
    await call.message.edit_text(
        f"{DIVIDER}\n📢 <b>Isbot kanalining havolasini yuboring:</b>\n{DIVIDER}\n\n"
        "Masalan: <code>@kanal_nomi</code> yoki <code>https://t.me/kanal_nomi</code>.\n"
        "O‘chirish uchun <code>off</code> yuboring.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{E('back', True)} Bekor qilish", callback_data="adm_settings_menu")]]),
    )
    await call.answer()


@router.message(AdminSettingsStates.WAITING_PROOF_CHANNEL_URL)
async def save_proof_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    if value.lower() == "off":
        value = ""
    elif value.startswith("@"):
        value = f"https://t.me/{value[1:]}"
    elif not (value.startswith("https://t.me/") or value.startswith("http://t.me/")):
        await message.answer("Havola noto‘g‘ri. @kanal_nomi yoki https://t.me/kanal_nomi yuboring:")
        return
    await db.set_setting("proof_channel_url", value)
    await state.clear()
    await message.answer("✅ Isbot kanali havolasi saqlandi!", reply_markup=admin_menu_keyboard())
