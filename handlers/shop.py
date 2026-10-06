from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.order import OrderStates
from keyboards.user import (
    products_keyboard,
    payment_methods_keyboard,
    player_confirm_keyboard,
    nav_back_home_keyboard,
)
import database as db
from services.midasbuy import MidasbuyService
from utils.helpers import is_valid_player_id, format_currency, DIVIDER, SUB_DIVIDER
from emojis import E
from services.pricing import product_sellable, calculate_price
from services.liogames import LioGamesService

router = Router()


@router.callback_query(F.data == "btn_buy_uc")
async def start_buy_uc(call: CallbackQuery, state: FSMContext):
    """User clicks Buy UC button."""
    await state.clear()
    await state.set_state(OrderStates.WAITING_PLAYER_ID)

    text = (
        f"{DIVIDER}\n"
        f"   {E('game')} <b>PUBG MOBILE PLAYER ID</b>\n"
        f"{DIVIDER}\n\n"
        f"🆔 <b>PUBG Mobile Player ID'ingizni yuboring:</b>\n\n"
        f"{E('bulb')} <i>Player ID'ni PUBG Mobile profil sahifangizdan (Avatar ustiga bosib) nusxalab olishingiz mumkin.\n"
        f"Masalan: <code>5123456789</code></i>"
    )
    await call.message.edit_text(text, reply_markup=nav_back_home_keyboard("btn_home"))
    await call.answer()


@router.message(OrderStates.WAITING_PLAYER_ID)
async def process_player_id(message: Message, state: FSMContext):
    """Validate player ID format and lookup via Midasbuy."""
    player_id = message.text.strip()

    if not is_valid_player_id(player_id):
        text = (
            f"{DIVIDER}\n"
            f"   {E('error')} <b>NOTO'G'RI FORMAT</b>\n"
            f"{DIVIDER}\n\n"
            f"Player ID faqat raqamlardan iborat bo'lishi kerak (kamida 5-12 ta raqam).\n\n"
            f"Iltimos, tekshirib qaytadan kiriting:"
        )
        await message.answer(text, reply_markup=nav_back_home_keyboard("btn_home"))
        return

    # Configuration/API errors are distinct from a genuine "player not found" result.
    if not LioGamesService.configured():
        await message.answer(
            f"{DIVIDER}\n"
            f"   {E('error')} <b>TEKSHIRUV VAQTINCHA ISHLAMAYAPTI</b>\n"
            f"{DIVIDER}\n\n"
            "LioGames API sozlamalari kiritilmagan. Iltimos, keyinroq urinib ko'ring yoki bot administratoriga xabar bering.",
            reply_markup=nav_back_home_keyboard("btn_home"),
        )
        return

    # Use LioGames username API; no mock player-name fallback in live ordering.
    wait_msg = await message.answer(f"{E('clock')} <i>Player ID tekshirilmoqda...</i>")
    is_valid, nickname, err = await MidasbuyService.validate_player(player_id)

    if not is_valid:
        is_not_found = err.startswith("LioGames bu Player ID")
        title = "PLAYER TOPILMADI" if is_not_found else "PLAYER ID TEKSHIRILMADI"
        detail = (
            "Iltimos, Player ID'ni tekshirib qayta yuboring:"
            if is_not_found
            else "LioGames tekshiruv xizmatida vaqtinchalik muammo bor. Birozdan so'ng qayta urinib ko'ring."
        )
        await wait_msg.edit_text(
            f"{DIVIDER}\n"
            f"   {E('error')} <b>{title}</b>\n"
            f"{DIVIDER}\n\n"
            f"{err if is_not_found else detail}",
            reply_markup=nav_back_home_keyboard("btn_home"),
        )
        return

    # Save player ID and nickname in FSM
    await state.update_data(player_id=player_id, nickname=nickname)

    text = (
        f"{DIVIDER}\n"
        f"   {E('profile')} <b>PLAYER TASDIQLASH</b>\n"
        f"{DIVIDER}\n\n"
        f"{E('game')} <b>O'yin:</b> PUBG Mobile\n"
        f"{E('profile')} <b>Nickname:</b> <b>{nickname}</b>\n"
        f"🆔 <b>Player ID:</b> <code>{player_id}</code>\n"
        f"{SUB_DIVIDER}\n"
        f"{E('verified')} <i>Ushbu akkauntga UC yuklansinmi?</i>"
    )
    await wait_msg.edit_text(text, reply_markup=player_confirm_keyboard())


@router.callback_query(F.data == "confirm_player_id")
async def show_products_list(call: CallbackQuery, state: FSMContext):
    """Player confirmed; display active UC packages."""
    data = await state.get_data()
    player_id = data.get("player_id")
    nickname = data.get("nickname", "Player")

    if not player_id:
        await call.answer("Iltimos, avval Player ID kiriting.", show_alert=True)
        return await start_buy_uc(call, state)

    products = await db.get_active_products()
    if not await db.global_sales_enabled():
        await call.answer("Hozirda yangi buyurtmalar vaqtincha to'xtatilgan.", show_alert=True)
        return
    if not products:
        await call.message.edit_text(
            f"{DIVIDER}\n"
            f"{E('error')} <b>Hozirda sotuvda faol UC paketlar mavjud emas.</b>\n"
            f"Birozdan so'ng qayta urinib ko'ring.\n"
            f"{DIVIDER}",
            reply_markup=nav_back_home_keyboard("btn_home"),
        )
        await state.clear()
        return

    await state.set_state(OrderStates.WAITING_PRODUCT)
    text = (
        f"{DIVIDER}\n"
        f"   {E('uc')} <b>UC PAKETINI TANLANG</b>\n"
        f"{DIVIDER}\n\n"
        f"{E('profile')} <b>Player:</b> <b>{nickname}</b>\n"
        f"🆔 <b>ID:</b> <code>{player_id}</code>\n\n"
        f"O'zingizga kerakli UC paketini tanlang 👇"
    )
    await call.message.edit_text(text, reply_markup=products_keyboard(products))
    await call.answer()


@router.callback_query(F.data == "back_to_products")
async def back_to_products_handler(call: CallbackQuery, state: FSMContext):
    """Back button from payment method back to product selection."""
    await show_products_list(call, state)


@router.callback_query(OrderStates.WAITING_PRODUCT, F.data.startswith("buy_prod:"))
async def product_selected(call: CallbackQuery, state: FSMContext):
    """Product selected; create order and prompt payment method."""
    product_id = int(call.data.split(":")[1])
    product = await db.get_product(product_id)

    if not product:
        await call.answer("Tanlangan paket topilmadi!", show_alert=True)
        return

    if product.get("manual_block") or product.get("is_active") != 1 or product.get("auto_block_reason") == "SUPPLIER_UNAVAILABLE":
        await call.answer("Bu paket hozircha sotuvda mavjud emas.", show_alert=True)
        await show_products_list(call, state)
        return

    rate = float(await db.get_setting("usd_rate", "0") or 0)
    quote = calculate_price(product.get("supplier_price_usd", 0), rate, product.get("profit_percent", 0), product.get("max_price", 0))
    if quote.blocked_reason:
        await db.set_product_pricing(product_id, auto_block_reason=quote.blocked_reason)
        await call.answer("Bu paketning narxi hozircha belgilangan limitdan oshdi yoki supplier narxi yo'q.", show_alert=True)
        await show_products_list(call, state)
        return
    await db.set_product_pricing(product_id, cost_price=float(quote.cost_uzs), price=float(quote.sale_price), auto_block_reason="")
    product = await db.get_product(product_id)

    if not await db.global_sales_enabled() or not product_sellable(product) or float(product.get("price", 0)) <= 0:
        await call.answer("Bu paket hozircha sotuvda mavjud emas.", show_alert=True)
        await show_products_list(call, state)
        return

    data = await state.get_data()
    player_id = data.get("player_id")
    nickname = data.get("nickname", "Player")

    # Create order in MongoDB
    order_id = await db.create_order(
        telegram_id=call.from_user.id,
        player_id=player_id,
        product_id=product["id"],
        price=product["price"],
        payment_method="PENDING",
        player_name=nickname,
        supplier_price_usd=product.get("supplier_price_usd", 0),
        usd_rate=rate,
        supplier_cost_uzs=product.get("cost_price", 0),
        profit_percent=product.get("profit_percent", 0),
        max_price=product.get("max_price", 0),
        supplier_product_id=product.get("supplier_product_id", ""),
        supplier_variation_id=product.get("supplier_variation_id", ""),
    )

    await state.update_data(order_id=order_id, product_id=product["id"], price=product["price"])
    await state.set_state(OrderStates.WAITING_PAYMENT_METHOD)

    user = await db.get_user(call.from_user.id)
    user_balance = user["balance"] if user else 0.0

    summary_text = (
        f"{DIVIDER}\n"
        f"   {E('order')} <b>BUYURTMA TASDIQLASH</b>\n"
        f"{DIVIDER}\n\n"
        f"📦 <b>Buyurtma kodi:</b> <code>{order_id}</code>\n"
        f"{E('game')} <b>O'yin:</b> PUBG Mobile\n\n"
        f"{E('profile')} <b>Player:</b> <b>{nickname}</b>\n"
        f"🆔 <b>Player ID:</b> <code>{player_id}</code>\n"
        f"{SUB_DIVIDER}\n"
        f"{E('uc')} <b>Paket:</b> <b>{product['name']}</b>\n"
        f"{E('balance')} <b>To'lov summasi:</b> <b>{format_currency(product['price'])}</b>\n"
        f"{E('lightning')} <b>Yetkazib berish:</b> Tezkor (1-5 daqiqa)\n"
        f"{SUB_DIVIDER}\n\n"
        f"To'lov usulini tanlang 👇"
    )

    if not player_id:
        await call.answer("Player ID ma'lumotlari topilmadi. Qaytadan boshlang.", show_alert=True)
        return
    await call.message.edit_text(
        summary_text,
        reply_markup=payment_methods_keyboard(user_balance=user_balance, order_price=product["price"]),
    )
    await call.answer()
