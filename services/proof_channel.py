import logging
from typing import Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError

from config import (
    PROOF_CHANNEL_ID,
    PROOF_ENABLED,
    PROOF_SHOW_PRICE,
    PROOF_SHOW_PLAYER_ID,
    PROOF_HASHTAGS,
    BOT_USERNAME,
)
import database as db
from utils.helpers import format_currency
from emojis import E

logger = logging.getLogger("services.proof")

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
PROOF_DIVIDER = "━━━━━━━━━━━━━━━━━━"

# Progression stage rankings to prevent backwards status transitions
PROOF_STAGES = {
    "NOT_SENT": 0,
    "RECEIVED": 1,
    "PROCESSING": 2,
    "COMPLETED": 3,
}


def mask_player_id(player_id: str) -> str:
    """
    Masks PUBG Player ID for privacy on public channels.
    Example: 123456789 -> 1234****6789, 123456 -> 12****56
    """
    pid = str(player_id).strip()
    length = len(pid)
    if length <= 4:
        return "****"
    elif length <= 6:
        return f"{pid[:2]}****{pid[-2:]}"
    elif length <= 8:
        return f"{pid[:3]}****{pid[-3:]}"
    else:
        return f"{pid[:4]}****{pid[-4:]}"


def get_tashkent_time_str(dt: Optional[datetime] = None) -> str:
    """Formats datetime to Tashkent timezone: 05.10.2026 • 17:30."""
    if dt is None:
        dt = datetime.now(TASHKENT_TZ)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(TASHKENT_TZ)
    else:
        dt = dt.astimezone(TASHKENT_TZ)
    return dt.strftime("%d.%m.%Y • %H:%M")


class ProofChannelService:
    @staticmethod
    def get_proof_keyboard(support_username: str = "") -> InlineKeyboardMarkup:
        """Inline keyboard for proof channel posts."""
        clean_bot = BOT_USERNAME.lstrip("@").strip() or "bot"
        clean_support = support_username.lstrip("@").strip() or clean_bot

        buttons = [
            [
                InlineKeyboardButton(
                    text=f"{E('uc', True)} UC SOTIB OLISH",
                    url=f"https://t.me/{clean_bot}?start=buy",
                ),
                InlineKeyboardButton(
                    text=f"{E('support', True)} SUPPORT",
                    url=f"https://t.me/{clean_support}",
                ),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @classmethod
    def format_proof_text(cls, order: Dict[str, Any], proof_status: str) -> str:
        """
        Builds sleek, premium Telegram channel post for order proof.
        Statuses: RECEIVED, PROCESSING, COMPLETED.
        """
        order_id = order.get("order_id", "—")
        product_name = order.get("product_name") or (f"{order.get('uc_amount', '')} UC" if order.get("uc_amount") else "PUBG UC")
        price_str = format_currency(order.get("price", 0))
        masked_id = mask_player_id(order.get("player_id", ""))
        bot_handle = f"@{BOT_USERNAME.lstrip('@')}" if BOT_USERNAME else "@bot"

        # Created time & Completed time
        created_at = order.get("created_at")
        created_time_str = get_tashkent_time_str(created_at if isinstance(created_at, datetime) else None)
        updated_time_str = get_tashkent_time_str()

        # A compact card header reads cleanly on mobile and allows custom emoji.
        if proof_status == "COMPLETED":
            header = (
                f"{E('success')} <b>BUYURTMA MUVAFFAQIYATLI BAJARILDI</b>\n"
                f"{PROOF_DIVIDER}"
            )
        elif proof_status == "PROCESSING":
            header = (
                f"{E('processing')} <b>BUYURTMA YETKAZILMOQDA</b>\n"
                f"{PROOF_DIVIDER}"
            )
        else:  # RECEIVED
            header = (
                f"{E('cart')} <b>BUYURTMA QABUL QILINDI</b>\n"
                f"{PROOF_DIVIDER}"
            )

        # Body items
        lines = [
            header,
            "",
            f"{E('game')} <b>PUBG MOBILE</b>",
            f"{E('uc')} <b>{product_name}</b>",
        ]

        if PROOF_SHOW_PLAYER_ID:
            lines.extend([
                f"{E('id')} <b>Player ID:</b>",
                f"<code>{masked_id}</code>",
            ])

        lines.extend([
            f"{E('order')} <b>Buyurtma:</b>",
            f"#{order_id}",
        ])

        if PROOF_SHOW_PRICE:
            lines.extend([
                f"{E('payment')} <b>Summa:</b>",
                f"<b>{price_str}</b>",
            ])

        # Status & Progression block
        lines.append(f"\n{PROOF_DIVIDER}\n")

        if proof_status == "COMPLETED":
            lines.extend([
                "🟢 <b>Holat:</b>",
                "<b>MUVAFFAQIYATLI YETKAZILDI</b>\n",
                f"{E('success')} <i>Buyurtma muvaffaqiyatli bajarildi.</i>\n",
                f"{E('time')} <b>Bajarilgan vaqt:</b>",
                f"<code>{updated_time_str}</code>",
            ])
        elif proof_status == "PROCESSING":
            lines.extend([
                "🟡 <b>Holat:</b>",
                "<b>BUYURTMA JARAYONDA</b>\n",
                f"{E('processing')} <i>UC hisobga yetkazib berilmoqda...</i>",
            ])
        else:  # RECEIVED
            lines.extend([
                "🔵 <b>Holat:</b>",
                "<b>BUYURTMA QABUL QILINDI</b>\n",
                f"{E('lightning')} <i>Buyurtmangiz tez orada qayta ishlanadi.</i>\n",
                f"{E('time')} <b>Vaqt:</b>",
                f"<code>{created_time_str}</code>",
            ])

        lines.append(f"\n{PROOF_DIVIDER}")
        lines.append(f"{E('uc')} <b>UC xarid:</b> {bot_handle}")

        if PROOF_HASHTAGS:
            if proof_status == "COMPLETED":
                lines.append("\n#PUBG #UC #PROOF")
            else:
                lines.append("\n#PUBG #UC #BUYURTMA")

        return "\n".join(lines)

    @classmethod
    async def send_or_update_proof(
        cls,
        bot: Bot,
        order_id: str,
        new_proof_status: str,
        force: bool = False,
    ) -> bool:
        """
        Primary entry point for Proof Channel posting & editing.
        Guarantees:
        1. Only ONE message per order (subsequent updates use editMessageText)
        2. Never crashes or interrupts core order processing
        3. Respects progression hierarchy (COMPLETED never regresses to PROCESSING)
        """
        if not PROOF_ENABLED:
            logger.debug(f"Proof Channel disabled, skipping proof for {order_id}")
            return False

        if not PROOF_CHANNEL_ID:
            logger.debug(f"PROOF_CHANNEL_ID not configured, skipping proof for {order_id}")
            return False

        try:
            order = await db.get_order(order_id)
            if not order:
                logger.warning(f"Order {order_id} not found when generating proof post")
                return False

            current_status = order.get("proof_status", "NOT_SENT")

            # Check progression (only forward, unless force=True)
            if not force:
                current_rank = PROOF_STAGES.get(current_status, 0)
                new_rank = PROOF_STAGES.get(new_proof_status, 0)
                if current_rank >= 3 and new_rank < 3:
                    logger.info(f"Order {order_id} proof is already COMPLETED. Ignoring regression to {new_proof_status}.")
                    return True

            support_username = await db.get_setting("support_username", "@PubgUcSupport")
            text = cls.format_proof_text(order, new_proof_status)
            keyboard = cls.get_proof_keyboard(support_username)

            existing_msg_id = order.get("proof_message_id")
            channel_id = order.get("proof_channel_id") or PROOF_CHANNEL_ID

            # Case A: Edit existing proof post
            if existing_msg_id:
                try:
                    await bot.edit_message_text(
                        text=text,
                        chat_id=channel_id,
                        message_id=existing_msg_id,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                    await db.update_order_proof_info(
                        order_id=order_id,
                        message_id=existing_msg_id,
                        channel_id=channel_id,
                        status=new_proof_status,
                    )
                    logger.info(f"Proof message #{existing_msg_id} edited to {new_proof_status} for {order_id}")
                    return True
                except TelegramAPIError as e:
                    if "message is not modified" in str(e).lower():
                        logger.debug(f"Proof message #{existing_msg_id} unchanged.")
                        return True
                    logger.error(f"Failed to edit proof message #{existing_msg_id}: {e}")
                    # If message was deleted from channel, we may fall through to send a fresh one if force=True
                    if not force:
                        return False

            # Case B: Send fresh initial proof post
            msg = await bot.send_message(
                chat_id=PROOF_CHANNEL_ID,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await db.update_order_proof_info(
                order_id=order_id,
                message_id=msg.message_id,
                channel_id=PROOF_CHANNEL_ID,
                status=new_proof_status,
            )
            logger.info(f"Proof message #{msg.message_id} created as {new_proof_status} for {order_id}")
            return True

        except Exception as e:
            logger.error(f"Error handling proof post for order {order_id}: {e}")
            # Notification layer must never break business logic
            return False
