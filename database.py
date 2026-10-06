import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument, ASCENDING, DESCENDING

from config import (MONGODB_URI, MONGODB_DB_NAME, DELIVERY_MODE, ORDER_PAYMENT_TTL_MINUTES,
                    DEFAULT_PROFIT_PERCENT, DEFAULT_MAX_PRICE_BUFFER_PERCENT)

import asyncio

logger = logging.getLogger("database")

# Global Mongo Client, Database & Event Loop reference
_client: Optional[AsyncIOMotorClient] = None
_db = None
_loop = None


def get_db():
    global _client, _db, _loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _db is None or _loop != current_loop:
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI aniqlanmadi! .env fayliga MONGODB_URI kiriting.")
        _client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
        _db = _client[MONGODB_DB_NAME]
        _loop = current_loop
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
    await db.payments.create_index([("bill_id", ASCENDING)], unique=True, partialFilterExpression={"bill_id": {"$gt": ""}})
    await db.payments.create_index([("provider_payment_id", ASCENDING)], unique=True, partialFilterExpression={"provider_payment_id": {"$gt": ""}})
    await db.supplier_orders.create_index([("order_id", ASCENDING)], unique=True)
    await db.price_snapshots.create_index([("order_id", ASCENDING)], unique=True)

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
    await db.settings.update_one({"key": "global_sales_enabled"}, {"$setOnInsert": {"value": "true"}}, upsert=True)
    await db.products.update_many(
        {"$or": [{"profit_percent": {"$exists": False}}, {"profit_percent": {"$lte": 0}}]},
        {"$set": {"profit_percent": DEFAULT_PROFIT_PERCENT}},
    )
    # Give packages with no configured cap a 25% buffer above their last known cost.
    # Existing nonzero admin-defined caps are preserved.
    async for product in db.products.find({"$or": [{"max_price": {"$exists": False}}, {"max_price": {"$lte": 0}}]}):
        cost = float(product.get("cost_price", 0) or 0)
        if cost > 0:
            cap = ((cost * (1 + DEFAULT_MAX_PRICE_BUFFER_PERCENT / 100) + 99) // 100) * 100
            await db.products.update_one({"_id": product["_id"]}, {"$set": {"max_price": float(cap)}})
        else:
            await db.products.update_one({"_id": product["_id"]}, {"$set": {"max_price": 0.0}})
    await db.products.update_many({"manual_block": {"$exists": False}}, {"$set": {"manual_block": False}})
    await db.products.update_many({"auto_block_reason": {"$exists": False}}, {"$set": {"auto_block_reason": ""}})
    await db.products.update_many({"supplier_price_usd": {"$exists": False}}, {"$set": {"supplier_price_usd": 0.0}})
    await db.orders.update_many(
        {"payment_status": {"$exists": False}, "status": {"$in": ["PAID", "PROCESSING", "MANUAL_REVIEW"]}},
        {"$set": {"payment_status": "SUCCESS", "delivery_status": "PROCESSING"}},
    )
    await db.orders.update_many(
        {"payment_status": {"$exists": False}, "status": "COMPLETED"},
        {"$set": {"payment_status": "SUCCESS", "delivery_status": "LEGACY_COMPLETED_REVIEW"}},
    )
    await db.orders.update_many(
        {"payment_status": {"$exists": False}},
        {"$set": {"payment_status": "PENDING", "delivery_status": "NOT_STARTED"}},
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
        doc = clean_doc(user)
        doc["is_new"] = False
        return doc

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
    doc = clean_doc(new_user)
    doc["is_new"] = True
    return doc


async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    user = await db.users.find_one({"telegram_id": telegram_id})
    return clean_doc(user)


async def update_user_balance(telegram_id: int, amount: float) -> bool:
    db = get_db()
    user = await get_user(telegram_id)
    if not user:
        return False
    if amount < 0:
        result = await db.users.update_one(
            {"telegram_id": telegram_id, "balance": {"$gte": abs(float(amount))}},
            {"$inc": {"balance": round(float(amount), 2)}},
        )
    else:
        result = await db.users.update_one(
            {"telegram_id": telegram_id}, {"$inc": {"balance": round(float(amount), 2)}}
        )
    return result.modified_count == 1


async def get_all_users_count() -> int:
    db = get_db()
    return await db.users.count_documents({})


async def get_user_total_uc(telegram_id: int) -> int:
    """Returns total UC bought by this user across COMPLETED orders."""
    db = get_db()
    cursor = db.orders.find({"user_id": telegram_id, "status": "COMPLETED"})
    total_uc = 0
    products_cache = {}
    async for order in cursor:
        if "uc_amount" in order and order["uc_amount"]:
            total_uc += int(order["uc_amount"])
        else:
            pid = int(order.get("product_id", 0))
            if pid not in products_cache:
                p = await db.products.find_one({"id": pid})
                products_cache[pid] = p.get("uc_amount", 0) if p else 0
            total_uc += products_cache[pid]
    return total_uc


async def get_top_uc_users(limit: int = 15) -> List[Dict[str, Any]]:
    """Returns top buyers ordered by total purchased UC."""
    db = get_db()
    cursor = db.orders.find({"status": "COMPLETED"})
    user_totals = {}
    products_cache = {}
    async for order in cursor:
        uid = order.get("user_id")
        if not uid:
            continue
        if "uc_amount" in order and order["uc_amount"]:
            uc = int(order["uc_amount"])
        else:
            pid = int(order.get("product_id", 0))
            if pid not in products_cache:
                p = await db.products.find_one({"id": pid})
                products_cache[pid] = p.get("uc_amount", 0) if p else 0
            uc = products_cache[pid]
        user_totals[uid] = user_totals.get(uid, 0) + uc

    sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    result = []
    for uid, total_uc in sorted_users:
        user = await db.users.find_one({"telegram_id": uid})
        result.append({
            "telegram_id": uid,
            "username": user.get("username", "") if user else "",
            "first_name": user.get("first_name", "") if user else "Foydalanuvchi",
            "total_uc": total_uc,
            "balance": user.get("balance", 0.0) if user else 0.0,
        })
    return result


async def get_recent_users(limit: int = 8) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.users.find({}).sort("created_at", DESCENDING).limit(limit)
    users = []
    async for doc in cursor:
        u = clean_doc(doc)
        u["total_uc"] = await get_user_total_uc(u["telegram_id"])
        users.append(u)
    return users


# ==============================================================================
# PRODUCT FUNCTIONS
# ==============================================================================

async def get_active_products() -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.products.find({"is_active": 1, "manual_block": {"$ne": True}, "auto_block_reason": {"$in": ["", None]}, "supplier_price_usd": {"$gt": 0}, "supplier_product_id": {"$exists": True, "$ne": ""}, "supplier_variation_id": {"$exists": True, "$ne": ""}, "max_price": {"$gt": 0}, "price": {"$gt": 0}}).sort([("sort_order", ASCENDING), ("uc_amount", ASCENDING)])
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


async def get_product_by_uc(uc_amount: int) -> Optional[Dict[str, Any]]:
    return clean_doc(await get_db().products.find_one({"uc_amount": int(uc_amount)}))


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


async def set_product_pricing(product_id: int, **fields) -> bool:
    allowed = {"profit_percent", "max_price", "manual_block", "auto_block_reason", "supplier_price_usd", "cost_price", "price", "supplier_product_id", "supplier_variation_id"}
    update = {key: value for key, value in fields.items() if key in allowed}
    if not update:
        return False
    update["updated_at"] = datetime.now()
    result = await get_db().products.update_one({"id": int(product_id)}, {"$set": update})
    return result.matched_count == 1


async def global_sales_enabled() -> bool:
    return (await get_setting("global_sales_enabled", "true")).lower() == "true"


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


async def create_order(telegram_id: int, player_id: str, product_id: int, price: float, payment_method: str, **snapshot) -> str:
    db = get_db()
    order_id = await generate_order_id()
    prod = await db.products.find_one({"id": int(product_id)})
    uc_amount = prod.get("uc_amount", 0) if prod else 0

    new_order = {
        "order_id": order_id,
        "user_id": telegram_id,
        "player_id": player_id,
        "product_id": int(product_id),
        "uc_amount": int(uc_amount),
        "price": float(price),
        "status": "WAITING_PAYMENT",
        "payment_status": "PENDING",
        "delivery_status": "NOT_STARTED",
        "payment_expires_at": datetime.now() + timedelta(minutes=ORDER_PAYMENT_TTL_MINUTES),
        "player_name": str(snapshot.get("player_name", "")),
        "supplier_order_id": "",
        "supplier_price_usd": float(snapshot.get("supplier_price_usd", prod.get("supplier_price_usd", 0))) if prod else 0.0,
        "usd_rate": float(snapshot.get("usd_rate", 0)),
        "supplier_cost_uzs": float(snapshot.get("supplier_cost_uzs", prod.get("cost_price", 0))) if prod else 0.0,
        "profit_percent": float(snapshot.get("profit_percent", prod.get("profit_percent", 0))) if prod else 0.0,
        "max_price": float(snapshot.get("max_price", prod.get("max_price", 0))) if prod else 0.0,
        "sale_price": float(price),
        "product_name": prod.get("name", "") if prod else "",
        "supplier_product_id": str(snapshot.get("supplier_product_id", prod.get("supplier_product_id", ""))) if prod else "",
        "supplier_variation_id": str(snapshot.get("supplier_variation_id", prod.get("supplier_variation_id", ""))) if prod else "",
        "payment_method": payment_method,
        "screenshot_file_id": "",
        # Proof channel fields
        "proof_message_id": None,
        "proof_channel_id": "",
        "proof_sent": False,
        "proof_status": "NOT_SENT",
        "proof_created_at": None,
        "proof_updated_at": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    await db.orders.insert_one(new_order)
    await db.price_snapshots.update_one(
        {"order_id": order_id},
        {"$setOnInsert": {"order_id": order_id, "product_id": int(product_id), "supplier_price_usd": new_order["supplier_price_usd"], "usd_rate": new_order["usd_rate"], "supplier_cost_uzs": new_order["supplier_cost_uzs"], "profit_percent": new_order["profit_percent"], "max_price": new_order["max_price"], "sale_price": new_order["sale_price"], "created_at": new_order["created_at"]}},
        upsert=True,
    )
    return order_id


async def _enrich_order(order_doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Enriches order dictionary with product name, uc_amount and user info."""
    if not order_doc:
        return None
    order = clean_doc(order_doc)
    db = get_db()

    # Product info
    prod = await db.products.find_one({"id": int(order.get("product_id", 0))})
    order["product_name"] = order.get("product_name") or (prod.get("name", "Noma'lum paket") if prod else "Noma'lum paket")
    order["uc_amount"] = order.get("uc_amount") or (prod.get("uc_amount", 0) if prod else 0)

    # User info
    user = await db.users.find_one({"telegram_id": order.get("user_id")})
    if user:
        order["username"] = user.get("username", "")
        order["first_name"] = user.get("first_name", "")
    else:
        order["username"] = ""
        order["first_name"] = ""

    # User's total purchased UC
    order["user_total_uc"] = await get_user_total_uc(order.get("user_id", 0))

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


async def transition_order(order_id: str, expected: List[str], status: str, **fields) -> bool:
    update = {"status": status, "updated_at": datetime.now(), **fields}
    result = await get_db().orders.update_one({"order_id": order_id, "status": {"$in": expected}}, {"$set": update})
    return result.modified_count == 1


async def claim_delivery(order_id: str) -> bool:
    result = await get_db().orders.update_one(
        {"order_id": order_id, "payment_status": "SUCCESS", "delivery_status": "NOT_STARTED"},
        {"$set": {"delivery_status": "PROCESSING", "status": "PROCESSING", "updated_at": datetime.now()}},
    )
    return result.modified_count == 1


async def mark_order_payment_success(order_id: str, provider_payment_id: str = "") -> bool:
    result = await get_db().orders.update_one(
        {"order_id": order_id, "payment_status": "PENDING", "delivery_status": "NOT_STARTED", "status": "WAITING_PAYMENT"},
        {"$set": {"payment_status": "SUCCESS", "provider_payment_id": provider_payment_id, "updated_at": datetime.now()}},
    )
    return result.modified_count == 1


async def debit_balance_for_order(order_id: str, telegram_id: int, amount: float) -> bool:
    """Atomically debit a wallet and claim its order payment exactly once."""
    if _client is None or amount <= 0:
        return False
    database = get_db()

    async def apply(session):
        order_update = await database.orders.update_one(
            {"order_id": order_id, "user_id": telegram_id, "payment_status": "PENDING", "status": "WAITING_PAYMENT"},
            {"$set": {"payment_status": "SUCCESS", "payment_method": "BALANCE", "provider_payment_id": f"balance:{order_id}", "updated_at": datetime.now()}},
            session=session,
        )
        if order_update.modified_count != 1:
            raise ValueError("order is not payable")
        balance_update = await database.users.update_one(
            {"telegram_id": telegram_id, "balance": {"$gte": float(amount)}},
            {"$inc": {"balance": -float(amount)}}, session=session,
        )
        if balance_update.modified_count != 1:
            raise ValueError("insufficient wallet balance")
        await database.payments.update_one(
            {"order_id": order_id, "payment_method": "BALANCE"},
            {"$setOnInsert": {"order_id": order_id, "payment_id": f"balance:{order_id}", "amount": float(amount), "amount_minor": int(round(amount * 100)), "payment_method": "BALANCE", "payment_type": "ORDER", "status": "SUCCESS", "created_at": datetime.now(), "paid_at": datetime.now()}},
            upsert=True, session=session,
        )
        return True
    try:
        async with await _client.start_session() as session:
            return bool(await session.with_transaction(apply))
    except ValueError:
        return False


async def store_supplier_order(order_id: str, supplier_order_id: str, raw_status: str, data: Optional[Dict[str, Any]] = None) -> None:
    db = get_db()
    now = datetime.now()
    await db.orders.update_one({"order_id": order_id}, {"$set": {"supplier_order_id": str(supplier_order_id or ""), "supplier_status": str(raw_status).upper(), "supplier_submitted": True, "updated_at": now}})
    await db.supplier_orders.update_one(
        {"order_id": order_id},
        {"$set": {"supplier_order_id": str(supplier_order_id or ""), "status": str(raw_status).upper(), "updated_at": now}, "$setOnInsert": {"created_at": now, "client_ref": order_id}},
        upsert=True,
    )


async def mark_supplier_submission_started(order_id: str) -> None:
    database = get_db()
    now = datetime.now()
    await database.orders.update_one({"order_id": order_id}, {"$set": {"supplier_submitted": True, "supplier_status": "SUBMITTING", "updated_at": now}})
    await database.supplier_orders.update_one(
        {"order_id": order_id},
        {"$setOnInsert": {"order_id": order_id, "client_ref": order_id, "supplier_order_id": "", "status": "SUBMITTING", "created_at": now, "updated_at": now}},
        upsert=True,
    )


async def set_delivery_status(order_id: str, delivery_status: str, **fields) -> bool:
    result = await get_db().orders.update_one({"order_id": order_id}, {"$set": {"delivery_status": delivery_status, "updated_at": datetime.now(), **fields}})
    return result.modified_count == 1


async def complete_delivery_once(order_id: str, **fields) -> bool:
    result = await get_db().orders.update_one(
        {"order_id": order_id, "payment_status": "SUCCESS", "delivery_status": {"$ne": "COMPLETED"}},
        {"$set": {"delivery_status": "COMPLETED", "status": "COMPLETED", "updated_at": datetime.now(), **fields}},
    )
    return result.modified_count == 1


async def get_recoverable_supplier_orders(limit: int = 100) -> List[Dict[str, Any]]:
    cursor = get_db().orders.find({"delivery_status": "PROCESSING", "supplier_submitted": True}).sort("updated_at", ASCENDING).limit(limit)
    return [clean_doc(doc) async for doc in cursor]


async def expire_unpaid_orders() -> int:
    now = datetime.now()
    result = await get_db().orders.update_many(
        {"payment_status": "PENDING", "status": "WAITING_PAYMENT", "payment_expires_at": {"$lte": now}},
        {"$set": {"payment_status": "EXPIRED", "status": "EXPIRED", "updated_at": now}},
    )
    await get_db().payments.update_many(
        {"status": "PENDING", "created_at": {"$lte": now - timedelta(minutes=ORDER_PAYMENT_TTL_MINUTES)}},
        {"$set": {"status": "EXPIRED", "expired_at": now, "monitor_until": now + timedelta(hours=24)}},
    )
    return result.modified_count


async def update_order_payment_method(order_id: str, payment_method: str) -> bool:
    db = get_db()
    res = await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"payment_method": payment_method, "updated_at": datetime.now()}},
    )
    return res.modified_count > 0


async def attach_order_screenshot(order_id: str, file_id: str) -> bool:
    db = get_db()
    res = await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"screenshot_file_id": file_id, "status": "WAITING_PAYMENT", "updated_at": datetime.now()}},
    )
    return res.modified_count > 0


async def update_order_proof_info(order_id: str, message_id: int, channel_id: str, status: str) -> bool:
    """Updates proof post message_id, channel_id and proof_status."""
    db = get_db()
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        return False

    update_fields = {
        "proof_message_id": message_id,
        "proof_channel_id": str(channel_id),
        "proof_sent": True,
        "proof_status": status,
        "proof_updated_at": datetime.now(),
    }
    if not order.get("proof_created_at"):
        update_fields["proof_created_at"] = datetime.now()

    res = await db.orders.update_one(
        {"order_id": order_id},
        {"$set": update_fields},
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


async def get_proof_stats() -> Dict[str, Any]:
    """Returns analytics regarding proof channel postings."""
    db = get_db()
    total_completed = await db.orders.count_documents({"status": "COMPLETED"})
    proof_sent = await db.orders.count_documents({"proof_sent": True})
    proof_completed = await db.orders.count_documents({"proof_status": "COMPLETED"})
    proof_not_sent = await db.orders.count_documents({"status": "COMPLETED", "proof_sent": False})
    return {
        "total_completed": total_completed,
        "proof_sent": proof_sent,
        "proof_completed": proof_completed,
        "proof_not_sent": proof_not_sent,
    }


# ==============================================================================
# PAYMENT FUNCTIONS
# ==============================================================================

async def create_payment(
    order_id: str,
    amount: float,
    payment_method: str,
    payment_id: str = "",
    *,
    bill_id: str = "",
    amount_minor: int = 0,
    payment_type: str = "ORDER",
    telegram_id: Optional[int] = None,
) -> str:
    db = get_db()
    payment = {
        "order_id": order_id,
        "payment_id": payment_id,
        "amount": float(amount),
        "payment_method": payment_method,
        "payment_type": payment_type,
        "bill_id": bill_id,
        "amount_minor": int(amount_minor or round(float(amount) * 100)),
        "telegram_id": telegram_id,
        "status": "PENDING",
        "raw_data": "",
        "created_at": datetime.now(),
    }
    res = await db.payments.insert_one(payment)
    return str(res.inserted_id)


async def get_pending_tezcheck_payments(limit: int = 100) -> List[Dict[str, Any]]:
    db = get_db()
    now = datetime.now()
    cursor = db.payments.find({
        "payment_method": "TEZCHECK",
        "$or": [{"status": "PENDING"}, {"status": "EXPIRED", "monitor_until": {"$gt": now}}],
        "bill_id": {"$exists": True, "$ne": ""},
    }).sort("created_at", ASCENDING).limit(limit)
    return [clean_doc(doc) async for doc in cursor]


async def mark_payment_paid_if_pending(order_id: str, raw_data: str = "", provider_payment_id: str = "") -> bool:
    db = get_db()
    result = await db.payments.update_one(
        {"order_id": order_id, "payment_method": "TEZCHECK", "status": "PENDING"},
        {"$set": {"status": "SUCCESS", "raw_data": raw_data, "provider_payment_id": provider_payment_id, "paid_at": datetime.now()}},
    )
    return result.modified_count == 1


async def credit_topup_if_pending(order_id: str, raw_data: str = "") -> Optional[Dict[str, Any]]:
    """Atomically mark a top-up paid and credit its user's balance once."""
    global _client
    db = get_db()
    if _client is None:
        return None

    async def apply(session):
        payment = await db.payments.find_one_and_update(
            {
                "order_id": order_id,
                "payment_type": "BALANCE_TOPUP",
                "payment_method": "TEZCHECK",
                "status": "PENDING",
            },
            {"$set": {"status": "SUCCESS", "raw_data": raw_data, "paid_at": datetime.now()}},
            return_document=ReturnDocument.BEFORE,
            session=session,
        )
        if not payment:
            return None
        updated = await db.users.update_one(
            {"telegram_id": payment["telegram_id"]},
            {"$inc": {"balance": float(payment["amount"])}},
            session=session,
        )
        if updated.modified_count != 1:
            raise RuntimeError(f"Top-up user not found for payment {order_id}")
        return clean_doc(payment)

    async with await _client.start_session() as session:
        return await session.with_transaction(apply)


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
