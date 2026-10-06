from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS, PROOF_CHANNEL_URL
import database as db
from keyboards.user import main_menu_keyboard
from utils.helpers import DIVIDER
from utils.helpers import format_currency
from emojis import E

router = Router()


def get_welcome_text(first_name: str) -> str:
    """Generates premium gaming welcome message."""
    return (
        f"{DIVIDER}\n"
        f"   {E('uc')} <b>PUBG MOBILE UC STORE</b>\n"
        f"{DIVIDER}\n\n"
        f"Assalomu alaykum, <b>{first_name}</b>!\n\n"
        f"{E('game')} <b>Rasmiy va tezkor PUBG Mobile UC xarid qilish xizmati.</b>\n\n"
        f"{E('lightning')} <b>Tezkor yetkazib berish</b> — 1-5 daqiqa\n"
        f"{E('payment')} <b>Xavfsiz to'lov</b> — Onlayn & Karta orqali\n"
        f"{E('verified')} <b>Kafolatlangan xizmat</b> — 100% ishonchli\n\n"
        f"{E('proof')} Isbotlarimizni kanalimizda kuzatib boring.\n\n"
        f"Kerakli bo'limni tanlang 👇"
    )


async def get_welcome_text_with_catalog(first_name: str) -> str:
    """Add the currently available UC package prices to the /start greeting."""
    products = await db.get_active_products()
    if not products:
        return get_welcome_text(first_name)

    catalog = "\n".join(
        f"{E('uc')} <b>{product.get('name', str(product.get('uc_amount', '')) + ' UC')}</b> — "
        f"{format_currency(product.get('price', 0))}"
        for product in products
    )
    return f"{get_welcome_text(first_name)}\n\n{DIVIDER}\n{E('uc')} <b>UC NARXLARI</b>\n{DIVIDER}\n{catalog}"


async def welcome_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    channel_url = await db.get_setting("proof_channel_url", PROOF_CHANNEL_URL)
    keyboard = main_menu_keyboard(is_admin=is_admin)
    if channel_url:
        keyboard.inline_keyboard.insert(
            0,
            [InlineKeyboardButton(text="📢 Isbot kanalimiz", url=channel_url)],
        )
    return keyboard


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Foydalanuvchi"

    # Register or update user in MongoDB
    user = await db.get_or_create_user(telegram_id=user_id, username=username, first_name=first_name)

    # If this is a newly registered user, alert admins
    if user.get("is_new"):
        total_users = await db.get_all_users_count()
        uname_str = f"@{username}" if username else "Mavjud emas"
        admin_alert = (
            f"🔔 <b>YANGI FOYDALANUVCHI QO'SHILDI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Ism:</b> {first_name}\n"
            f"🏷 <b>Username:</b> {uname_str}\n"
            f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
            f"👥 <b>Jami a'zolar:</b> <b>{total_users} nafar</b>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(chat_id=admin_id, text=admin_alert, parse_mode="HTML")
            except Exception:
                pass

    is_admin = user_id in ADMIN_IDS
    await message.answer(await get_welcome_text_with_catalog(first_name), reply_markup=await welcome_keyboard(is_admin))


@router.callback_query(F.data.in_({"btn_cancel", "btn_home", "adm_exit"}))
async def return_to_main_menu(call: CallbackQuery, state: FSMContext):
    """Cancel operation or return to main menu from any sub-state."""
    await state.clear()
    is_admin = call.from_user.id in ADMIN_IDS
    first_name = call.from_user.first_name or "Foydalanuvchi"

    try:
        welcome_text = await get_welcome_text_with_catalog(first_name)
        await call.message.edit_text(welcome_text, reply_markup=await welcome_keyboard(is_admin))
    except Exception:
        await call.message.delete()
        welcome_text = await get_welcome_text_with_catalog(first_name)
        await call.message.answer(welcome_text, reply_markup=await welcome_keyboard(is_admin))

    await call.answer()
