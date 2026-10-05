import os
from pathlib import Path
from dotenv import load_dotenv

# Project Root Directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()

# Admin IDs
_raw_admins = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(x.strip()) for x in _raw_admins if x.strip().isdigit()]

# Delivery Mode: 'MANUAL' or 'AUTO'
DELIVERY_MODE = os.getenv("DELIVERY_MODE", "MANUAL").strip().upper()

# TezCheck Gateway
TEZCHECK_BASE_URL = os.getenv("TEZCHECK_BASE_URL", "https://api.tezcheck.uz").rstrip("/")
TEZCHECK_API_KEY = os.getenv("TEZCHECK_API_KEY", "").strip()
TEZCHECK_CASH_DESK_CODE = os.getenv("TEZCHECK_CASH_DESK_CODE", "").strip()
TEZCHECK_WEBHOOK_SECRET = os.getenv("TEZCHECK_WEBHOOK_SECRET", "").strip()

# Midasbuy API
MIDASBUY_BASE_URL = os.getenv("MIDASBUY_BASE_URL", "https://api.midasbuy.com").rstrip("/")
MIDASBUY_API_KEY = os.getenv("MIDASBUY_API_KEY", "").strip()
MIDASBUY_SECRET = os.getenv("MIDASBUY_SECRET", "").strip()

# SQLite Database File Path
DB_PATH = str(BASE_DIR / "bot.db")

# FastAPI Webhook Server Port
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8000))
