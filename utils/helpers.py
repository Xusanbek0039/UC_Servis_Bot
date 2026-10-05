import re
from typing import Dict, Any


def format_currency(amount: float) -> str:
    """Format numeric amount into human readable Uzbek currency."""
    return f"{int(amount):,}".replace(",", " ") + " UZS"


def is_valid_player_id(player_id: str) -> bool:
    """Verify PUBG Mobile Player ID format (8 to 12 digits)."""
    return bool(re.match(r"^\d{8,12}$", str(player_id).strip()))


def get_status_emoji(status: str) -> str:
    """Return visual status emoji for orders."""
    mapping = {
        "PENDING": "⏳ Kutilmoqda",
        "WAITING_PAYMENT": "💳 To'lov kutilmoqda",
        "PAID": "💰 To'langan",
        "PROCESSING": "⚙️ Jarayonda",
        "COMPLETED": "✅ Yakunlangan",
        "CANCELLED": "🚫 Bekor qilingan",
        "FAILED": "❌ Xatolik",
        "MANUAL_REVIEW": "🟡 Admin tekshiruvida",
    }
    return mapping.get(status, status)


def format_order_summary(order: Dict[str, Any]) -> str:
    """Formats full order summary for user and admin."""
    status_text = get_status_emoji(order.get("status", ""))
    username_str = f"@{order['username']}" if order.get("username") else (order.get("first_name") or "—")
    
    return (
        f"📦 <b>Order:</b> <code>{order.get('order_id')}</code>\n\n"
        f"👤 <b>User:</b> {username_str}\n"
        f"🆔 <b>Telegram ID:</b> <code>{order.get('user_id')}</code>\n\n"
        f"🎮 <b>Player ID:</b> <code>{order.get('player_id')}</code>\n"
        f"💎 <b>UC:</b> {order.get('product_name') or str(order.get('product_id')) + ' UC'}\n"
        f"💰 <b>Narx:</b> {format_currency(order.get('price', 0))}\n\n"
        f"💳 <b>Payment:</b> {order.get('payment_method')}\n\n"
        f"📊 <b>Status:</b> <b>{status_text}</b>"
    )
