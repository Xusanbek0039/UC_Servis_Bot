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
        "fallback": "💎",
    },
    "game": {
        "env_var": "EMOJI_GAME",
        "fallback": "🎮",
    },
    "payment": {
        "env_var": "EMOJI_PAYMENT",
        "fallback": "💳",
    },
    "order": {
        "env_var": "EMOJI_ORDER",
        "fallback": "📦",
    },
    "profile": {
        "env_var": "EMOJI_PROFILE",
        "fallback": "👤",
    },
    "balance": {
        "env_var": "EMOJI_BALANCE",
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
        "fallback": "✨",
    },
    "check": {
        "env_var": "EMOJI_CHECK",
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
        "fallback": "💡",
    },
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

    custom_id = os.getenv(conf["env_var"], "").strip()
    if custom_id and custom_id.isdigit():
        return f'<tg-emoji emoji-id="{custom_id}">{fallback}</tg-emoji>'

    return fallback


def E(key: str, for_button: bool = False) -> str:
    """Shorthand alias for get_emoji."""
    return get_emoji(key, for_button)
