import logging
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from apps.products.services import ProductService
from apps.promo.services import PromoService
from apps.orders.services import OrderService
from apps.payments.services import PaymentService
from apps.users.services import UserService
from apps.settings.models import BotSettings
from providers.factory import get_topup_provider
from providers.base import PlayerValidationError
from bot.states.buy_uc import BuyUCStates
from bot.keyboards.reply import main_menu_keyboard, cancel_keyboard
from bot.keyboards.inline import (
    player_confirmation_inline,
    products_inline,
    promo_prompt_inline,
    payment_methods_inline,
    tezcheck_pay_inline,
    cancel_inline,
)

router = Router()
logger = logging.getLogger("bot.buy_uc")


@router.message(F.text.in_(["🎮 PUBG UC", "🎮 UC sotib olish", "/buy"]))
async def start_buy_uc(message: Message, state: FSMContext):
    """Entry point for PUBG UC purchase."""
    await state.clear()
    await state.set_state(BuyUCStates.WAITING_PLAYER_ID)

    text = (
        "🎮 <b>PUBG Mobile Player ID'ingizni kiriting:</b>\n\n"
        "<i>(Masalan: 5123456789 — ID raqamingiz o'yin profilingizda ko'rsatilgan)</i>"
    )
    await message.answer(text, reply_markup=cancel_keyboard())


@router.message(BuyUCStates.WAITING_PLAYER_ID)
async def process_player_id(message: Message, state: FSMContext, db_user):
    """Receive and validate Player ID with provider."""
    raw_id = message.text.strip()
    if not raw_id.isdigit() or len(raw_id) < 8 or len(raw_id) > 12:
        await message.answer(
            "⚠️ <b>Noto'g'ri Player ID formati!</b>\n"
            "PUBG Player ID faqat 8 dan 12 gacha raqamlardan iborat bo'lishi kerak.\n\n"
            "Iltimos, qaytadan kiriting:",
            reply_markup=cancel_keyboard(),
        )
        return

    wait_msg = await message.answer("🔍 <i>PUBG serveridan player ma'lumotlari tekshirilmoqda...</i>")

    provider = get_topup_provider()
    try:
        player_info = await provider.validate_player(raw_id)
    except PlayerValidationError as e:
        await wait_msg.delete()
        await message.answer(
            f"❌ <b>Xatolik:</b> {e.message}\n\nIltimos, IDingizni tekshirib qayta kiriting:",
            reply_markup=cancel_keyboard(),
        )
        return
    except Exception as e:
        logger.exception("Player validation unexpected error")
        await wait_msg.delete()
        await message.answer(
            "⚠️ Hozircha texnik muammo yuz berdi. Iltimos, keyinroq urinib ko'ring yoki adminga murojaat qiling.",
            reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
        )
        await state.clear()
        return

    await wait_msg.delete()

    # Save validated info into FSM context
    await state.update_data(
        player_id=player_info.player_id,
        nickname=player_info.nickname,
        region=player_info.region,
    )
    await sync_to_async(UserService.save_player)(
        user=db_user,
        player_id=player_info.player_id,
        nickname=player_info.nickname,
        region=player_info.region,
    )

    await state.set_state(BuyUCStates.WAITING_PLAYER_CONFIRMATION)
    confirm_text = (
        f"👤 <b>Player:</b> {player_info.nickname}\n"
        f"🆔 <b>ID:</b> <code>{player_info.player_id}</code>\n"
        f"🌐 <b>Region:</b> {player_info.region}\n\n"
        f"❓ <b>Shu akkauntga UC yuborilsinmi?</b>"
    )
    await message.answer(confirm_text, reply_markup=player_confirmation_inline())


@router.callback_query(BuyUCStates.WAITING_PLAYER_CONFIRMATION, F.data == "confirm_player_no")
async def player_rejected(call: CallbackQuery, state: FSMContext):
    """User wants to re-enter Player ID."""
    await state.set_state(BuyUCStates.WAITING_PLAYER_ID)
    await call.message.delete()
    await call.message.answer(
        "🎮 PUBG Mobile Player ID'ingizni qaytadan kiriting:",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


@router.callback_query(BuyUCStates.WAITING_PLAYER_CONFIRMATION, F.data == "confirm_player_yes")
async def player_confirmed(call: CallbackQuery, state: FSMContext, db_user):
    """Player ID confirmed; display UC packages."""
    # Ensure default products exist if table is empty
    await sync_to_async(ProductService.seed_default_products)()
    products = await sync_to_async(list)(ProductService.get_active_products())

    if not products:
        await call.message.delete()
        await call.message.answer(
            "⚠️ Hozirda sotuvda faol UC paketlar mavjud emas. Tez orada qo'shiladi.",
            reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
        )
        await state.clear()
        await call.answer()
        return

    await state.set_state(BuyUCStates.WAITING_PRODUCT)
    await call.message.delete()
    await call.message.answer(
        "💎 <b>O'zingizga kerakli UC paketini tanlang:</b>",
        reply_markup=products_inline(products),
    )
    await call.answer()


@router.callback_query(BuyUCStates.WAITING_PRODUCT, F.data.startswith("select_product:"))
async def product_selected(call: CallbackQuery, state: FSMContext):
    """User selected a product."""
    product_id = int(call.data.split(":")[1])
    product = await sync_to_async(ProductService.get_product)(product_id)

    if not product:
        await call.answer("Tanlangan paket topilmadi!", show_alert=True)
        return

    await state.update_data(product_id=product.id, price=str(product.price))
    await call.message.delete()

    # Ask for promo code
    await state.set_state(BuyUCStates.WAITING_PROMO_CODE)
    await call.message.answer(
        f"📦 Tanlangan paket: <b>{product.name}</b>\n"
        f"💰 Narxi: <b>{product.price:,.0f} UZS</b>\n\n"
        f"🎟 Sizda chegirma promo kodingiz bormi?",
        reply_markup=promo_prompt_inline(),
    )
    await call.answer()


@router.callback_query(BuyUCStates.WAITING_PROMO_CODE, F.data == "promo_skip")
async def promo_skipped(call: CallbackQuery, state: FSMContext, db_user):
    """User skips promo code."""
    await state.update_data(promo_code=None, discount_amount="0.00")
    await show_payment_methods(call.message, state, db_user)
    await call.answer()


@router.callback_query(BuyUCStates.WAITING_PROMO_CODE, F.data == "promo_enter")
async def promo_enter_request(call: CallbackQuery):
    """User clicks to enter promo code."""
    await call.message.edit_text(
        "🎟 <b>Promo kodingizni yozib yuboring:</b>\n<i>(Masalan: WELCOME10)</i>",
        reply_markup=cancel_inline(),
    )
    await call.answer()


@router.message(BuyUCStates.WAITING_PROMO_CODE)
async def process_promo_code(message: Message, state: FSMContext, db_user):
    """Validate entered promo code."""
    code_text = message.text.strip().upper()
    data = await state.get_data()
    product_id = data.get("product_id")
    product = await sync_to_async(ProductService.get_product)(product_id)

    promo, discount, msg = await sync_to_async(PromoService.validate_promo)(
        code=code_text,
        order_amount=product.price,
        user=db_user,
    )

    if not promo:
        await message.answer(
            f"❌ <b>Xatolik:</b> {msg}\n\nQaytadan kiriting yoki o'tkazib yuboring:",
            reply_markup=promo_prompt_inline(),
        )
        return

    await state.update_data(promo_code=promo.code, discount_amount=str(discount))
    await message.answer(f"✅ {msg}")
    await show_payment_methods(message, state, db_user)


async def show_payment_methods(message_or_call, state: FSMContext, db_user):
    """Displays order summary and payment method options."""
    data = await state.get_data()
    product_id = data.get("product_id")
    player_id = data.get("player_id")
    nickname = data.get("nickname")
    promo_code = data.get("promo_code")
    discount = Decimal(data.get("discount_amount", "0.00"))

    product = await sync_to_async(ProductService.get_product)(product_id)
    final_amount = max(Decimal("0.00"), product.price - discount)
    await state.update_data(final_amount=str(final_amount))

    summary_text = (
        f"📦 <b>Buyurtma ma'lumotlari:</b>\n\n"
        f"🎮 <b>O'yin:</b> PUBG Mobile\n"
        f"🆔 <b>Player ID:</b> <code>{player_id}</code>\n"
        f"👤 <b>Nickname:</b> {nickname}\n"
        f"💎 <b>Paket:</b> {product.name}\n"
        f"💰 <b>Narx:</b> {product.price:,.0f} UZS\n"
    )

    if discount > 0:
        summary_text += f"🎟 <b>Chegirma ({promo_code}):</b> -{discount:,.0f} UZS\n"

    summary_text += (
        f"💵 <b>Jami to'lov summasi:</b> <b>{final_amount:,.0f} UZS</b>\n\n"
        f"💳 To'lov usulini tanlang 👇"
    )

    await state.set_state(BuyUCStates.WAITING_PAYMENT_METHOD)

    # Refresh user balance from database
    await sync_to_async(db_user.refresh_from_db)()

    kb = payment_methods_inline(user_balance=db_user.balance, final_amount=final_amount)
    if isinstance(message_or_call, CallbackQuery):
        await message_or_call.message.answer(summary_text, reply_markup=kb)
    else:
        await message_or_call.answer(summary_text, reply_markup=kb)


@router.callback_query(BuyUCStates.WAITING_PAYMENT_METHOD, F.data.startswith("pay_method:"))
async def process_payment_method_selection(call: CallbackQuery, state: FSMContext, db_user):
    """Handle payment method selection."""
    method = call.data.split(":")[1]
    data = await state.get_data()
    product_id = data.get("product_id")
    player_id = data.get("player_id")
    nickname = data.get("nickname")
    promo_code_str = data.get("promo_code")

    product = await sync_to_async(ProductService.get_product)(product_id)

    # 1. Internal Balance Payment
    if method == "BALANCE":
        order = await sync_to_async(OrderService.create_order)(
            user=db_user,
            product=product,
            player_id=player_id,
            player_nickname=nickname,
            payment_method=Order.PaymentMethod.BALANCE,
            promo_code_str=promo_code_str,
        )
        success, msg = await sync_to_async(OrderService.pay_with_balance)(order)
        await call.message.delete()
        if success:
            await call.message.answer(
                f"🎉 <b>To'lov balansingizdan muvaffaqiyatli amalga oshirildi!</b>\n\n"
                f"📦 Buyurtma raqamingiz: <code>{order.order_id}</code>\n"
                f"🚀 UC qisqa vaqt ichida PUBG akkauntingizga yetkaziladi!",
                reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
            )
        else:
            await call.message.answer(
                f"❌ {msg}",
                reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
            )
        await state.clear()
        await call.answer()
        return

    # 2. TezCheck Payment
    if method == "TEZCHECK":
        order = await sync_to_async(OrderService.create_order)(
            user=db_user,
            product=product,
            player_id=player_id,
            player_nickname=nickname,
            payment_method=Order.PaymentMethod.TEZCHECK,
            promo_code_str=promo_code_str,
        )
        await state.update_data(order_id=order.order_id)
        await state.set_state(BuyUCStates.WAITING_PAYMENT)

        wait_msg = await call.message.edit_text("⏳ <i>TezCheck to'lov havolasi tayyorlanmoqda...</i>")
        success, pay_url, err_msg = await PaymentService.create_tezcheck_payment(order)

        if not success:
            await wait_msg.edit_text(
                f"⚠️ To'lov tizimida vaqtinchalik muammo: {err_msg}\n"
                f"Iltimos, karta orqali to'lov usulidan foydalaning.",
                reply_markup=cancel_inline(),
            )
            await call.answer()
            return

        pay_text = (
            f"⚡️ <b>TezCheck orqali to'lov</b>\n\n"
            f"📦 Buyurtma: <code>{order.order_id}</code>\n"
            f"💎 Paket: {product.name}\n"
            f"💵 To'lov summasi: <b>{order.final_amount:,.0f} UZS</b>\n\n"
            f"To'lovni amalga oshirish uchun quyidagi tugmani bosing 👇"
        )
        await wait_msg.edit_text(pay_text, reply_markup=tezcheck_pay_inline(pay_url, order.order_id))
        await call.answer()
        return

    # 3. Manual Card Payment
    if method == "MANUAL_CARD":
        order = await sync_to_async(OrderService.create_order)(
            user=db_user,
            product=product,
            player_id=player_id,
            player_nickname=nickname,
            payment_method=Order.PaymentMethod.MANUAL_CARD,
            promo_code_str=promo_code_str,
        )
        await state.update_data(order_id=order.order_id)
        await state.set_state(BuyUCStates.WAITING_SCREENSHOT)

        bot_settings = await sync_to_async(BotSettings.load)()
        card_text = (
            f"💳 <b>Karta orqali to'lov</b>\n\n"
            f"Karta raqami:\n<code>{bot_settings.card_number}</code>\n"
            f"Karta egasi: <b>{bot_settings.card_owner}</b>\n"
            f"Bank: <b>{bot_settings.bank_name}</b>\n\n"
            f"📦 Buyurtma: <code>{order.order_id}</code>\n"
            f"💰 To'lanishi kerak bo'lgan summa:\n<b>{order.final_amount:,.0f} so'm</b>\n\n"
            f"❗️ <b>To'lov qilganingizdan keyin chek yoki skrinshotni shu yerga rasm holida yuboring.</b>"
        )
        await call.message.delete()
        await call.message.answer(card_text, reply_markup=cancel_keyboard())
        await call.answer()


@router.message(BuyUCStates.WAITING_SCREENSHOT, F.photo | F.document)
async def process_manual_check_screenshot(message: Message, state: FSMContext, db_user):
    """Receive receipt screenshot from user."""
    data = await state.get_data()
    order_id = data.get("order_id")

    from apps.orders.models import Order
    order = await sync_to_async(Order.objects.filter(order_id=order_id).first)()
    if not order:
        await message.answer("Buyurtma topilmadi!", reply_markup=main_menu_keyboard(is_admin=db_user.is_admin))
        await state.clear()
        return

    # Extract telegram file ID
    file_id = ""
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id

    await sync_to_async(PaymentService.create_manual_card_payment)(
        order=order,
        telegram_file_id=file_id,
    )

    await state.clear()
    await message.answer(
        "⏳ <b>To‘lovingiz admin tomonidan tekshirilmoqda.</b>\n\n"
        "Tez orada chekingiz ko'rib chiqiladi va UC akkauntingizga yetkazib beriladi.\n"
        "Buyurtma holatini <b>📦 Buyurtmalarim</b> bo'limida kuzatishingiz mumkin.",
        reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
    )


@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment_status(call: CallbackQuery, db_user):
    """User clicks verify payment."""
    order_id = call.data.split(":")[1]
    from apps.orders.models import Order
    order = await sync_to_async(Order.objects.filter(order_id=order_id).first)()

    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order.is_paid:
        await call.message.delete()
        await call.message.answer(
            f"✅ <b>To'lov qabul qilindi!</b>\nBuyurtma holati: <b>{order.status}</b>",
            reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
        )
    else:
        await call.answer("To'lov hali qabul qilinmadi. Iltimos, to'lab bo'lgach qayta bosing.", show_alert=True)
