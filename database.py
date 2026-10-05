import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument, ASCENDING, DESCENDING

from config import MONGODB_URI, MONGODB_DB_NAME, DELIVERY_MODE

logger = logging.getLogger("database")

# Global Mongo Client & Database instance
_client: Optional[AsyncIOMotorClient] = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI aniqlanmadi! .env fayliga MONGODB_URI kiriting.")
        _client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
        _db = _client[MONGODB_DB_NAME]
    return _db


def clean_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Helper to convert MongoDB ObjectId to string and make document JSON-safe."""
    if not doc:
        return None
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return d


async def init_db():
    """Initialize MongoDB collections, unique indexes, default products, and settings."""
    db = get_db()

    # 1. Create Indexes
    await db.users.create_index([("telegram_id", ASCENDING)], unique=True)
    await db.orders.create_index([("order_id", ASCENDING)], unique=True)
    await db.orders.create_index([("user_id", ASCENDING)])
    await db.orders.create_index([("status", ASCENDING)])
    await db.products.create_index([("id", ASCENDING)], unique=True)
    await db.settings.create_index([("key", ASCENDING)], unique=True)
    await db.payments.create_index([("order_id", ASCENDING)])

    # 2. Seed initial products if collection is empty
    prod_count = await db.products.count_documents({})
    if prod_count == 0:
        default_products = [
            {"id": 1, "name": "60 UC", "uc_amount": 60, "price": 15000.0, "cost_price": 12000.0, "is_active": 1, "sort_order": 1},
            {"id": 2, "name": "325 UC", "uc_amount": 325, "price": 70000.0, "cost_price": 58000.0, "is_active": 1, "sort_order": 2},
            {"id": 3, "name": "660 UC", "uc_amount": 660, "price": 135000.0, "cost_price": 115000.0, "is_active": 1, "sort_order": 3},
            {"id": 4, "name": "1800 UC", "uc_amount": 1800, "price": 350000.0, "cost_price": 300000.0, "is_active": 1, "sort_order": 4},
            {"id": 5, "name": "3850 UC", "uc_amount": 3850, "price": 700000.0, "cost_price": 600000.0, "is_active": 1, "sort_order": 5},
            {"id": 6, "name": "8100 UC", "uc_amount": 8100, "price": 1400000.0, "cost_price": 1200000.0, "is_active": 1, "sort_order": 6},
        ]
        await db.products.insert_many(default_products)
        await db.counters.update_one(
            {"_id": "product_id"},
            {"$set": {"seq": 6}},
            upsert=True,
        )
        logger.info("Default UC products seeded to MongoDB.")

    # 3. Seed initial settings if empty
    default_settings = [
        {"key": "card_number", "value": "8600 0000 0000 1234"},
        {"key": "card_owner", "value": "PUBG UC OPERATOR"},
        {"key": "bank_name", "value": "Kapitalbank / Uzcard / Humo"},
        {"key": "support_username", "value": "@PubgUcSupport"},
        {"key": "delivery_mode", "value": DELIVERY_MODE},
    ]
    for s in default_settings:
        await db.settings.update_one(
            {"key": s["key"]},
            {"$setOnInsert": {"value": s["value"]}},
            upsert=True,
        )

    logger.info("MongoDB Atlas initialized successfully.")


# ==============================================================================
# USER FUNCTIONS
# ==============================================================================

async def get_or_create_user(telegram_id: int, username: Optional[str] = "", first_name: Optional[str] = "") -> Dict[str, Any]:
    db = get_db()
    user = await db.users.find_one({"telegram_id": telegram_id})
    if user:
        # Update user info if changed
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"username": username or "", "first_name": first_name or ""}},
        )
        user["username"] = username or ""
        user["first_name"] = first_name or ""
        return clean_doc(user)

    # Insert new user
    new_user = {
        "id": telegram_id,
        "telegram_id": telegram_id,
        "username": username or "",
        "first_name": first_name or "",
        "balance": 0.0,
        "created_at": datetime.now(),
    }
    await db.users.insert_one(new_user)
    return clean_doc(new_user)


async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    user = await db.users.find_one({"telegram_id": telegram_id})
    return clean_doc(user)


async def update_user_balance(telegram_id: int, amount: float) -> bool:
    db = get_db()
    user = await get_user(telegram_id)
    if not user:
        return False
    new_balance = float(user.get("balance", 0.0)) + float(amount)
    if new_balance < 0:
        return False

    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"balance": round(new_balance, 2)}},
    )
    return True


async def get_all_users_count() -> int:
    db = get_db()
    return await db.users.count_documents({})


async def get_recent_users(limit: int = 8) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.users.find({}).sort("created_at", DESCENDING).limit(limit)
    users = []
    async for doc in cursor:
        users.append(clean_doc(doc))
    return users


# ==============================================================================
# PRODUCT FUNCTIONS
# ==============================================================================

async def get_active_products() -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.products.find({"is_active": 1}).sort([("sort_order", ASCENDING), ("uc_amount", ASCENDING)])
    products = []
    async for doc in cursor:
        products.append(clean_doc(doc))
    return products


async def get_all_products() -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.products.find({}).sort([("sort_order", ASCENDING), ("uc_amount", ASCENDING)])
    products = []
    async for doc in cursor:
        products.append(clean_doc(doc))
    return products


async def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    prod = await db.products.find_one({"id": int(product_id)})
    return clean_doc(prod)


async def add_product(name: str, uc_amount: int, price: float, cost_price: float = 0.0, sort_order: int = 0) -> int:
    db = get_db()
    counter_doc = await db.counters.find_one_and_update(
        {"_id": "product_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    new_id = counter_doc["seq"]

    new_prod = {
        "id": new_id,
        "name": name,
        "uc_amount": int(uc_amount),
        "price": float(price),
        "cost_price": float(cost_price),
        "is_active": 1,
        "sort_order": int(sort_order),
    }
    await db.products.insert_one(new_prod)
    return new_id


async def update_product_price(product_id: int, new_price: float) -> bool:
    db = get_db()
    res = await db.products.update_one(
        {"id": int(product_id)},
        {"$set": {"price": float(new_price)}},
    )
    return res.modified_count > 0


async def toggle_product_status(product_id: int) -> bool:
    db = get_db()
    prod = await get_product(product_id)
    if not prod:
        return False
    new_status = 0 if prod.get("is_active") == 1 else 1
    await db.products.update_one(
        {"id": int(product_id)},
        {"$set": {"is_active": new_status}},
    )
    return True


async def delete_product(product_id: int) -> bool:
    db = get_db()
    res = await db.products.delete_one({"id": int(product_id)})
    return res.deleted_count > 0


# ==============================================================================
# ORDER FUNCTIONS
# ==============================================================================

async def generate_order_id() -> str:
    """Generate sequential PUBG-000001 style order ID via MongoDB atomic counter."""
    db = get_db()
    counter_doc = await db.counters.find_one_and_update(
        {"_id": "order_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    next_num = counter_doc["seq"]
    return f"PUBG-{next_num:06d}"


async def create_order(telegram_id: int, player_id: str, product_id: int, price: float, payment_method: str) -> str:
    db = get_db()
    order_id = await generate_order_id()
    new_order = {
        "order_id": order_id,
        "user_id": telegram_id,
        "player_id": player_id,
        "product_id": int(product_id),
        "price": float(price),
        "status": "WAITING_PAYMENT",
        "payment_method": payment_method,
        "screenshot_file_id": "",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    await db.orders.insert_one(new_order)
    return order_id


async def _enrich_order(order_doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Enriches order dictionary with product name, uc_amount and user info."""
    if not order_doc:
        return None
    order = clean_doc(order_doc)
    db = get_db()

    # Product info
    prod = await db.products.find_one({"id": int(order.get("product_id", 0))})
    order["product_name"] = prod.get("name", "Noma'lum paket") if prod else "Noma'lum paket"
    order["uc_amount"] = prod.get("uc_amount", 0) if prod else 0

    # User info
    user = await db.users.find_one({"telegram_id": order.get("user_id")})
    if user:
        order["username"] = user.get("username", "")
        order["first_name"] = user.get("first_name", "")
    else:
        order["username"] = ""
        order["first_name"] = ""

    return order


async def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    order = await db.orders.find_one({"order_id": order_id})
    return await _enrich_order(order)


async def get_user_orders(telegram_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.orders.find({"user_id": telegram_id}).sort("created_at", DESCENDING).limit(limit)
    orders = []
    async for doc in cursor:
        enriched = await _enrich_order(doc)
        orders.append(enriched)
    return orders


async def update_order_status(order_id: str, status: str) -> bool:
    db = get_db()
    res = await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"status": status, "updated_at": datetime.now()}},
    )
    return res.modified_count > 0


async def attach_order_screenshot(order_id: str, file_id: str) -> bool:
    db = get_db()
    res = await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"screenshot_file_id": file_id, "status": "WAITING_PAYMENT", "updated_at": datetime.now()}},
    )
    return res.modified_count > 0


async def get_orders_by_status(status: str, limit: int = 10) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.orders.find({"status": status}).sort("created_at", DESCENDING).limit(limit)
    orders = []
    async for doc in cursor:
        enriched = await _enrich_order(doc)
        orders.append(enriched)
    return orders


async def get_recent_orders(limit: int = 10) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.orders.find({}).sort("created_at", DESCENDING).limit(limit)
    orders = []
    async for doc in cursor:
        enriched = await _enrich_order(doc)
        orders.append(enriched)
    return orders


async def get_order_stats() -> Dict[str, Any]:
    db = get_db()
    today_start = datetime.combine(date.today(), time.min)
    today_end = datetime.combine(date.today(), time.max)

    # Today's orders
    today_orders_count = await db.orders.count_documents({
        "created_at": {"$gte": today_start, "$lte": today_end}
    })

    # Today's revenue
    today_rev_pipeline = [
        {"$match": {"created_at": {"$gte": today_start, "$lte": today_end}, "status": "COMPLETED"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}},
    ]
    today_rev_cursor = db.orders.aggregate(today_rev_pipeline)
    today_revenue = 0.0
    async for doc in today_rev_cursor:
        today_revenue = float(doc.get("total", 0.0))

    # Total orders
    total_orders = await db.orders.count_documents({})

    # Total revenue & completed count
    tot_rev_pipeline = [
        {"$match": {"status": "COMPLETED"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}, "count": {"$sum": 1}}},
    ]
    tot_rev_cursor = db.orders.aggregate(tot_rev_pipeline)
    total_revenue = 0.0
    completed_orders = 0
    async for doc in tot_rev_cursor:
        total_revenue = float(doc.get("total", 0.0))
        completed_orders = int(doc.get("count", 0))

    # Cancelled / Failed count
    cancelled_orders = await db.orders.count_documents({
        "status": {"$in": ["CANCELLED", "FAILED"]}
    })

    return {
        "today_orders": today_orders_count,
        "today_revenue": today_revenue,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
    }


# ==============================================================================
# PAYMENT FUNCTIONS
# ==============================================================================

async def create_payment(order_id: str, amount: float, payment_method: str, payment_id: str = "") -> str:
    db = get_db()
    payment = {
        "order_id": order_id,
        "payment_id": payment_id,
        "amount": float(amount),
        "payment_method": payment_method,
        "status": "PENDING",
        "raw_data": "",
        "created_at": datetime.now(),
    }
    res = await db.payments.insert_one(payment)
    return str(res.inserted_id)


async def get_payment_by_order(order_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    pay = await db.payments.find_one({"order_id": order_id}, sort=[("created_at", DESCENDING)])
    return clean_doc(pay)


async def update_payment_status(order_id: str, status: str, raw_data: str = "") -> bool:
    db = get_db()
    res = await db.payments.update_one(
        {"order_id": order_id},
        {"$set": {"status": status, "raw_data": raw_data}},
    )
    return res.modified_count > 0


# ==============================================================================
# SETTINGS FUNCTIONS
# ==============================================================================

async def get_setting(key: str, default: str = "") -> str:
    db = get_db()
    s = await db.settings.find_one({"key": key})
    return str(s.get("value", default)) if s else default


async def set_setting(key: str, value: str):
    db = get_db()
    await db.settings.update_one(
        {"key": key},
        {"$set": {"value": str(value)}},
        upsert=True,
    )


async def get_all_settings() -> Dict[str, str]:
    db = get_db()
    cursor = db.settings.find({})
    settings = {}
    async for s in cursor:
        settings[s["key"]] = str(s.get("value", ""))
    return settings
