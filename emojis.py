import os
from typing import Dict, Any

# ==============================================================================
# PREMIUM TELEGRAM CUSTOM EMOJI & UNICODE FALLBACK SYSTEM
# ==============================================================================
# If an EMOJI_* environment variable contains a Telegram Custom Emoji ID,
# the bot will render <tg-emoji emoji-id="ID">fallback</tg-emoji> in HTML messages.
# If no ID is provided, it cleanly falls back to high-grade Unicode emojis.
# Buttons always use clean Unicode characters because Telegram buttons do not parse HTML.
# ==============================================================================

EMOJI_CONFIG: Dict[str, Dict[str, str]] = {
    "uc": {
        "env_var": "EMOJI_UC",
        "default_id": "5386358072627184204",
        "fallback": "💎",
    },
    "game": {
        "env_var": "EMOJI_GAME",
        "default_id": "5341747651777930077",
        "fallback": "🎮",
    },
    "payment": {
        "env_var": "EMOJI_PAYMENT",
        "fallback": "💳",
    },
    "order": {
        "env_var": "EMOJI_ORDER",
        "default_id": "6323328338123293863",
        "fallback": "📦",
    },
    "profile": {
        "env_var": "EMOJI_PROFILE",
        "default_id": "5818715087237549366",
        "fallback": "👤",
    },
    "balance": {
        "env_var": "EMOJI_BALANCE",
        "default_id": "5388996449562285785",
        "fallback": "💰",
    },
    "support": {
        "env_var": "EMOJI_SUPPORT",
        "fallback": "💬",
    },
    "settings": {
        "env_var": "EMOJI_SETTINGS",
        "fallback": "⚙️",
    },
    "success": {
        "env_var": "EMOJI_SUCCESS",
        "default_id": "5222068860521290556",
        "fallback": "✨",
    },
    "check": {
        "env_var": "EMOJI_CHECK",
        "default_id": "5980930633298350051",
        "fallback": "✅",
    },
    "error": {
        "env_var": "EMOJI_ERROR",
        "fallback": "⚠️",
    },
    "cross": {
        "env_var": "EMOJI_CROSS",
        "fallback": "❌",
    },
    "star": {
        "env_var": "EMOJI_STAR",
        "fallback": "⭐",
    },
    "fire": {
        "env_var": "EMOJI_FIRE",
        "fallback": "🔥",
    },
    "lightning": {
        "env_var": "EMOJI_LIGHTNING",
        "fallback": "⚡",
    },
    "verified": {
        "env_var": "EMOJI_VERIFIED",
        "fallback": "🛡️",
    },
    "clock": {
        "env_var": "EMOJI_CLOCK",
        "fallback": "⏱",
    },
    "back": {
        "env_var": "EMOJI_BACK",
        "fallback": "◀️",
    },
    "home": {
        "env_var": "EMOJI_HOME",
        "fallback": "🏠",
    },
    "edit": {
        "env_var": "EMOJI_EDIT",
        "fallback": "✏️",
    },
    "refresh": {
        "env_var": "EMOJI_REFRESH",
        "fallback": "🔄",
    },
    "stats": {
        "env_var": "EMOJI_STATS",
        "fallback": "📊",
    },
    "users": {
        "env_var": "EMOJI_USERS",
        "fallback": "👥",
    },
    "card": {
        "env_var": "EMOJI_CARD",
        "default_id": "6323185173978416820",
        "fallback": "💳",
    },
    "link": {
        "env_var": "EMOJI_LINK",
        "fallback": "🔗",
    },
    "pin": {
        "env_var": "EMOJI_PIN",
        "fallback": "📍",
    },
    "bulb": {
        "env_var": "EMOJI_BULB",
        "default_id": "5472146462362048818",
        "fallback": "💡",
    },
    "proof": {
        "env_var": "EMOJI_PROOF",
        "fallback": "📢",
    },
    "processing": {
        "env_var": "EMOJI_PROCESSING",
        "fallback": "⚙️",
    },
    "time": {
        "env_var": "EMOJI_TIME",
        "fallback": "🕐",
    },
    "id": {
        "env_var": "EMOJI_ID",
        "default_id": "5841276284155467413",
        "fallback": "🆔",
    },
    "cart": {
        "env_var": "EMOJI_CART",
        "fallback": "🛒",
    },
    "bank": {"env_var": "EMOJI_BANK", "default_id": "5388974304710906586", "fallback": "🏦"},
    "tag": {"env_var": "EMOJI_TAG", "default_id": "6323468994007271113", "fallback": "🏷"},
    "pointer": {"env_var": "EMOJI_POINTER", "default_id": "5265165687650797923", "fallback": "👉"},
    "visa": {"env_var": "EMOJI_VISA", "default_id": "5247131613896126178", "fallback": "💳"},
    "humo": {"env_var": "EMOJI_HUMO", "default_id": "5386365640359567570", "fallback": "💳"},
    "mastercard": {"env_var": "EMOJI_MASTERCARD", "default_id": "5278219081105811309", "fallback": "💳"},
    "uzcard": {"env_var": "EMOJI_UZCARD", "default_id": "5389085445579626838", "fallback": "💳"},
    "click": {"env_var": "EMOJI_CLICK", "default_id": "5192986687772303380", "fallback": "💸"},
    "payme": {"env_var": "EMOJI_PAYME", "default_id": "5190915130556162925", "fallback": "💸"},
    "paynet": {"env_var": "EMOJI_PAYNET", "default_id": "5474339588627509561", "fallback": "💸"},
}


def get_emoji(key: str, for_button: bool = False) -> str:
    """
    Returns custom emoji HTML tag or fallback Unicode emoji.
    - If for_button=True: always returns clean Unicode (Telegram button text does not parse HTML).
    - If for_button=False and custom ID exists: returns <tg-emoji emoji-id="ID">fallback</tg-emoji>.
    - Otherwise returns clean fallback.
    """
    conf = EMOJI_CONFIG.get(key)
    if not conf:
        return ""

    fallback = conf["fallback"]
    if for_button:
        return fallback

    custom_id = os.getenv(conf["env_var"], conf.get("default_id", "")).strip()
    if custom_id and custom_id.isdigit():
        return f'<tg-emoji emoji-id="{custom_id}">{fallback}</tg-emoji>'

    return fallback


def E(key: str, for_button: bool = False) -> str:
    """Shorthand alias for get_emoji."""
    return get_emoji(key, for_button)
