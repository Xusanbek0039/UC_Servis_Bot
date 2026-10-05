import re
from typing import Dict, Any
from datetime import datetime
from emojis import E

DIVIDER = "━━━━━━━━━━━━━━━━━━"
SUB_DIVIDER = "────────────────────"


def format_currency(amount: float) -> str:
    """Format numeric amount into human readable Uzbek currency: 135 000 UZS."""
    return f"{int(amount):,}".replace(",", " ") + " UZS"


def is_valid_player_id(player_id: str) -> bool:
    """Verify PUBG Mobile Player ID format (5 to 12 digits)."""
    return bool(re.match(r"^\d{5,12}$", str(player_id).strip()))


def get_status_badge(status: str) -> str:
    """Return high-clarity status badge for orders."""
    badges = {
        "PENDING": "🟡 Kutilmoqda",
        "WAITING_PAYMENT": "🟡 To'lov kutilmoqda",
        "PAID": "🔵 To'langan",
        "PROCESSING": "⚡ Yetkazilmoqda",
        "COMPLETED": "🟢 Bajarildi",
        "CANCELLED": "🔴 Bekor qilingan",
        "FAILED": "⚠️ Muvaffaqiyatsiz",
        "MANUAL_REVIEW": "🔍 Tekshiruvda",
    }
    return badges.get(status, f"⚪ {status}")


def format_order_summary(order: Dict[str, Any]) -> str:
    """Formats full order summary for user and admin inspection."""
    order_id = order.get("order_id", "—")
    status_badge = get_status_badge(order.get("status", ""))
    username_str = f"@{order['username']}" if order.get("username") else (order.get("first_name") or "—")
    product_name = order.get("product_name") or (f"{order.get('uc_amount', '')} UC" if order.get("uc_amount") else "PUBG UC")
    price_str = format_currency(order.get("price", 0))

    created_at = order.get("created_at")
    if isinstance(created_at, datetime):
        date_str = created_at.strftime("%Y-%m-%d %H:%M")
    elif created_at:
        date_str = str(created_at)[:16]
    else:
        date_str = "—"
    proof_sent = order.get("proof_sent", False)
    proof_msg_id = order.get("proof_message_id")
    if proof_sent and proof_msg_id:
        proof_line = f"📢 <b>Isbot posti:</b> 🟢 Yuborilgan (#{proof_msg_id}) [{order.get('proof_status', 'OK')}]"
    elif proof_sent:
        proof_line = f"📢 <b>Isbot posti:</b> 🟢 Yuborilgan [{order.get('proof_status', 'OK')}]"
    else:
        proof_line = "📢 <b>Isbot posti:</b> ⚠️ Yuborilmagan"

    pay_method_raw = order.get("payment_method", "Noma'lum")
    if pay_method_raw == "TEZCHECK":
        pay_method_str = "Onlayn to'lov (Avtomatik)"
    elif pay_method_raw == "MANUAL_CARD":
        pay_method_str = "Karta orqali"
    elif pay_method_raw == "BALANCE":
        pay_method_str = "Ichki balansdan"
    else:
        pay_method_str = pay_method_raw

    user_total_uc = order.get("user_total_uc")
    uc_history_line = f"{E('uc')} <b>Jami xarid qilgan:</b> <b>{user_total_uc:,} UC</b>\n" if user_total_uc is not None else ""

    return (
        f"{DIVIDER}\n"
        f"{E('order')} <b>BUYURTMA: #{order_id}</b>\n"
        f"{DIVIDER}\n\n"
        f"{E('game')} <b>O'yin:</b> PUBG Mobile\n"
        f"{E('profile')} <b>Mijoz:</b> {username_str}\n"
        f"🆔 <b>Telegram ID:</b> <code>{order.get('user_id')}</code>\n"
        f"{uc_history_line}\n"
        f"🕹 <b>Player ID:</b> <code>{order.get('player_id')}</code>\n"
        f"{E('uc')} <b>Paket:</b> <b>{product_name}</b>\n"
        f"{E('balance')} <b>Summa:</b> <b>{price_str}</b>\n"
        f"{E('payment')} <b>To'lov usuli:</b> <b>{pay_method_str}</b>\n"
        f"{E('stats')} <b>Holat:</b> <b>{status_badge}</b>\n"
        f"{proof_line}\n"
        f"{E('clock')} <b>Sana:</b> <code>{date_str}</code>\n"
        f"{DIVIDER}"
    )


def format_user_order_card(order: Dict[str, Any]) -> str:
    """Formats user-facing compact order card."""
    order_id = order.get("order_id", "—")
    status_badge = get_status_badge(order.get("status", ""))
    product_name = order.get("product_name") or (f"{order.get('uc_amount', '')} UC" if order.get("uc_amount") else "PUBG UC")
    price_str = format_currency(order.get("price", 0))

    created_at = order.get("created_at")
    if isinstance(created_at, datetime):
        date_str = created_at.strftime("%d.%m.%Y %H:%M")
    elif created_at:
        date_str = str(created_at)[:16]
    else:
        date_str = "—"

    return (
        f"{DIVIDER}\n"
        f"{E('order')} <b>BUYURTMA #{order_id}</b>\n"
        f"{DIVIDER}\n\n"
        f"{E('game')} <b>O'yin:</b> PUBG Mobile\n"
        f"🆔 <b>Player ID:</b> <code>{order.get('player_id')}</code>\n"
        f"{E('uc')} <b>Paket:</b> <b>{product_name}</b>\n"
        f"{E('balance')} <b>Narxi:</b> <b>{price_str}</b>\n"
        f"{SUB_DIVIDER}\n"
        f"{E('stats')} <b>Holati:</b> <b>{status_badge}</b>\n"
        f"{E('clock')} <b>Vaqti:</b> <code>{date_str}</code>\n"
        f"{DIVIDER}"
    )
