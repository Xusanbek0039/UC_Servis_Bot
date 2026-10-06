import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Project Root Directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")

# Admin IDs
_raw_admins = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(x.strip()) for x in _raw_admins if x.strip().isdigit()]

# MongoDB Atlas Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "pubg_uc_db").strip()

# Delivery Mode: 'MANUAL' or 'AUTO'
DELIVERY_MODE = os.getenv("DELIVERY_MODE", "MANUAL").strip().upper()

# TezCheck Gateway
TEZCHECK_BASE_URL = (
    os.getenv("TEZ_BASE_URL") or os.getenv("TEZCHECK_BASE_URL") or "https://api.tezcheck.uz"
).strip().rstrip("/")
TEZCHECK_API_KEY = (os.getenv("TEZ_API_KEY") or os.getenv("TEZCHECK_API_KEY") or "").strip()
TEZCHECK_CASH_DESK_CODE = (
    os.getenv("TEZ_CASH_DESK_CODE") or os.getenv("TEZCHECK_CASH_DESK_CODE") or ""
).strip()
TEZCHECK_WEBHOOK_SECRET = os.getenv("TEZCHECK_WEBHOOK_SECRET", "").strip()

# Midasbuy API
MIDASBUY_BASE_URL = os.getenv("MIDASBUY_BASE_URL", "https://api.midasbuy.com").rstrip("/")
MIDASBUY_API_KEY = os.getenv("MIDASBUY_API_KEY", "").strip()
MIDASBUY_SECRET = os.getenv("MIDASBUY_SECRET", "").strip()

# LioGames reseller API. Live delivery stays disabled until all credentials and
# the selected PUBG product/variation mapping are configured.
LIOGAMES_BASE_URL = os.getenv("LIOGAMES_BASE_URL", "https://distribution.liogames.com/api/v1").strip().rstrip("/")
LIOGAMES_MEMBER_CODE = os.getenv("LIOGAMES_MEMBER_CODE", "").strip()
LIOGAMES_SECRET = os.getenv("LIOGAMES_SECRET", "").strip()
LIOGAMES_KEY_ID = os.getenv("LIOGAMES_KEY_ID", "").strip()
LIOGAMES_PUBG_PRODUCT_ID = os.getenv("LIOGAMES_PUBG_PRODUCT_ID", "").strip()
LIOGAMES_VARIATIONS = os.getenv("LIOGAMES_VARIATIONS", "").strip()
try:
    LIOGAMES_PRODUCT_MAP = json.loads(LIOGAMES_VARIATIONS) if LIOGAMES_VARIATIONS else {
        "60": {"product_id": 66719, "variation_id": 533766},
        "325": {"product_id": 66719, "variation_id": 533768},
        "660": {"product_id": 66719, "variation_id": 533770},
        "1800": {"product_id": 66719, "variation_id": 533772},
        "3850": {"product_id": 66719, "variation_id": 533774},
        "8100": {"product_id": 66719, "variation_id": 533776},
    }
except json.JSONDecodeError:
    LIOGAMES_PRODUCT_MAP = {}
LIOGAMES_PRICE_TIER = os.getenv("LIOGAMES_PRICE_TIER", "GOLD").strip().upper()
DEFAULT_PROFIT_PERCENT = max(0, float(os.getenv("DEFAULT_PROFIT_PERCENT", "10")))
DEFAULT_MAX_PRICE_BUFFER_PERCENT = max(0, float(os.getenv("DEFAULT_MAX_PRICE_BUFFER_PERCENT", "25")))
LIOGAMES_AUTO_DELIVERY = os.getenv("LIOGAMES_AUTO_DELIVERY", "false").strip().lower() in ("1", "true", "yes")
LIOGAMES_STATUS_INTERVAL = max(10, int(os.getenv("LIOGAMES_STATUS_INTERVAL", "20")))
LIOGAMES_MAX_RETRIES = max(0, min(5, int(os.getenv("LIOGAMES_MAX_RETRIES", "3"))))
LOW_BALANCE_THRESHOLD = float(os.getenv("LOW_BALANCE_THRESHOLD", "20"))
LIOGAMES_STOP_ON_LOW_BALANCE = os.getenv("LIOGAMES_STOP_ON_LOW_BALANCE", "true").strip().lower() in ("1", "true", "yes")
USD_RATE_URL = os.getenv("USD_RATE_URL", "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/").strip()
USD_RATE_INTERVAL_HOURS = max(1, int(os.getenv("USD_RATE_INTERVAL_HOURS", "12")))
MAX_PROFIT_PERCENT = max(0, float(os.getenv("MAX_PROFIT_PERCENT", "200")))
ORDER_PAYMENT_TTL_MINUTES = max(5, int(os.getenv("ORDER_PAYMENT_TTL_MINUTES", "20")))
BACKUP_RETENTION_DAYS = max(1, int(os.getenv("BACKUP_RETENTION_DAYS", "7")))
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups").strip()

# Proof Channel Configuration
PROOF_CHANNEL_ID = os.getenv("PROOF_CHANNEL_ID", "").strip()
PROOF_CHANNEL_URL = os.getenv("PROOF_CHANNEL_URL", "").strip()
PROOF_ENABLED = os.getenv("PROOF_ENABLED", "True").strip().lower() in ("true", "1", "yes")
PROOF_SHOW_PRICE = os.getenv("PROOF_SHOW_PRICE", "True").strip().lower() in ("true", "1", "yes")
PROOF_SHOW_PLAYER_ID = os.getenv("PROOF_SHOW_PLAYER_ID", "True").strip().lower() in ("true", "1", "yes")
PROOF_HASHTAGS = os.getenv("PROOF_HASHTAGS", "True").strip().lower() in ("true", "1", "yes")
PROOF_AUTO_POST = os.getenv("PROOF_AUTO_POST", "True").strip().lower() in ("true", "1", "yes")

# FastAPI Webhook Server Port
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8000))
