from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.order import OrderStates
from keyboards.user import products_keyboard, payment_methods_keyboard, cancel_keyboard
import database as db
from services.midasbuy import MidasbuyService
from utils.helpers import is_valid_player_id, format_currency

router = Router()


@router.callback_query(F.data == "btn_buy_uc")
async def start_buy_uc(call: CallbackQuery, state: FSMContext):
    """User clicks Buy UC."""
    await state.clear()
    await state.set_state(OrderStates.WAITING_PLAYER_ID)

    text = (
        "🎮 <b>PUBG Mobile UC xarid qilish</b>\n\n"
        "🆔 <b>PUBG Mobile Player ID'ingizni yuboring:</b>\n"
        "<i>(Masalan: 5123456789)</i>"
    )
    await call.message.edit_text(text, reply_markup=cancel_keyboard())
    await call.answer()


@router.message(OrderStates.WAITING_PLAYER_ID)
async def process_player_id(message: Message, state: FSMContext):
    """Validate player ID and display active UC packages."""
    player_id = message.text.strip()

    if not is_valid_player_id(player_id):
        await message.answer(
            "⚠️ <b>Noto'g'ri Player ID formati!</b>\n"
            "Player ID faqat 8 dan 12 gacha bo'lgan raqamlardan iborat bo'lishi kerak.\n\n"
            "Qaytadan kiriting:",
            reply_markup=cancel_keyboard(),
        )
        return

    # Check via Midasbuy service
    is_valid, nickname, err = await MidasbuyService.validate_player(player_id)
    if not is_valid:
        await message.answer(
            f"❌ <b>Xatolik:</b> {err}\n\nIltimos, tekshirib qayta kiriting:",
            reply_markup=cancel_keyboard(),
        )
        return

    # Save player ID and nickname in FSM
    await state.update_data(player_id=player_id, nickname=nickname)

    products = await db.get_active_products()
    if not products:
        await message.answer("⚠️ Hozirda sotuvda faol paketlar mavjud emas.")
        await state.clear()
        return

    await state.set_state(OrderStates.WAITING_PRODUCT)
    text = (
        f"👤 <b>Player:</b> {nickname}\n"
        f"🆔 <b>ID:</b> <code>{player_id}</code>\n\n"
        f"💎 <b>Kerakli UC paketini tanlang:</b>"
    )
    await message.answer(text, reply_markup=products_keyboard(products))


@router.callback_query(OrderStates.WAITING_PRODUCT, F.data.startswith("buy_prod:"))
async def product_selected(call: CallbackQuery, state: FSMContext):
    """Product selected; create order and prompt payment method."""
    product_id = int(call.data.split(":")[1])
    product = await db.get_product(product_id)

    if not product:
        await call.answer("Paket topilmadi!", show_alert=True)
        return

    data = await state.get_data()
    player_id = data.get("player_id")
    nickname = data.get("nickname", "")

    # Create order in SQLite
    order_id = await db.create_order(
        telegram_id=call.from_user.id,
        player_id=player_id,
        product_id=product["id"],
        price=product["price"],
        payment_method="PENDING",
    )

    await state.update_data(order_id=order_id, product_id=product["id"], price=product["price"])
    await state.set_state(OrderStates.WAITING_PAYMENT_METHOD)

    user = await db.get_user(call.from_user.id)
    user_balance = user["balance"] if user else 0.0

    summary_text = (
        f"📦 <b>Buyurtma yaratildi:</b> <code>{order_id}</code>\n\n"
        f"🎮 <b>Player:</b> {nickname} (ID: <code>{player_id}</code>)\n"
        f"💎 <b>Paket:</b> {product['name']}\n"
        f"💰 <b>Narxi:</b> <b>{format_currency(product['price'])}</b>\n\n"
        f"💳 To'lov usulini tanlang 👇"
    )

    await call.message.edit_text(
        summary_text,
        reply_markup=payment_methods_keyboard(user_balance=user_balance, order_price=product["price"]),
    )
    await call.answer()
