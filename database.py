import aiosqlite
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging
from config import DB_PATH, DELIVERY_MODE

logger = logging.getLogger("database")


class DBContext:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def __aenter__(self) -> aiosqlite.Connection:
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.conn.close()


async def get_connection() -> DBContext:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return DBContext(conn)


async def init_db():
    """Create all required tables and seed default products and settings."""
    async with await get_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                uc_amount INTEGER NOT NULL,
                price REAL NOT NULL,
                cost_price REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'WAITING_PAYMENT',
                payment_method TEXT NOT NULL,
                screenshot_file_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                payment_id TEXT DEFAULT '',
                amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                raw_data TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.commit()

        # Seed initial products if table is empty
        async with db.execute("SELECT COUNT(*) as count FROM products") as cursor:
            row = await cursor.fetchone()
            if row["count"] == 0:
                default_products = [
                    ("60 UC", 60, 15000.0, 12000.0, 1),
                    ("325 UC", 325, 70000.0, 58000.0, 2),
                    ("660 UC", 660, 135000.0, 115000.0, 3),
                    ("1800 UC", 1800, 350000.0, 300000.0, 4),
                    ("3850 UC", 3850, 700000.0, 600000.0, 5),
                    ("8100 UC", 8100, 1400000.0, 1200000.0, 6),
                ]
                await db.executemany(
                    "INSERT INTO products (name, uc_amount, price, cost_price, sort_order) VALUES (?, ?, ?, ?, ?)",
                    default_products,
                )
                await db.commit()

        # Seed initial default settings if empty
        default_settings = [
            ("card_number", "8600 0000 0000 1234"),
            ("card_owner", "PUBG UC OPERATOR"),
            ("bank_name", "Kapitalbank / Uzcard / Humo"),
            ("support_username", "@PubgUcSupport"),
            ("delivery_mode", DELIVERY_MODE),
        ]
        for key, val in default_settings:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        await db.commit()

    logger.info("Database initialized successfully.")


# ==============================================================================
# USER FUNCTIONS
# ==============================================================================

async def get_or_create_user(telegram_id: int, username: Optional[str] = "", first_name: Optional[str] = "") -> Dict[str, Any]:
    async with await get_connection() as db:
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            user = await cursor.fetchone()
            if user:
                # Update username or first_name if changed
                await db.execute(
                    "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
                    (username or "", first_name or "", telegram_id),
                )
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as c2:
                    return dict(await c2.fetchone())

            await db.execute(
                "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
                (telegram_id, username or "", first_name or ""),
            )
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as c3:
                return dict(await c3.fetchone())


async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    async with await get_connection() as db:
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_user_balance(telegram_id: int, amount: float) -> bool:
    async with await get_connection() as db:
        user = await get_user(telegram_id)
        if not user:
            return False
        new_balance = user["balance"] + amount
        if new_balance < 0:
            return False
        await db.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, telegram_id))
        await db.commit()
        return True


async def get_all_users_count() -> int:
    async with await get_connection() as db:
        async with db.execute("SELECT COUNT(*) as count FROM users") as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0


async def get_recent_users(limit: int = 8) -> List[Dict[str, Any]]:
    async with await get_connection() as db:
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ==============================================================================
# PRODUCT FUNCTIONS
# ==============================================================================

async def get_active_products() -> List[Dict[str, Any]]:
    async with await get_connection() as db:
        async with db.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY sort_order ASC, uc_amount ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_products() -> List[Dict[str, Any]]:
    async with await get_connection() as db:
        async with db.execute("SELECT * FROM products ORDER BY sort_order ASC, uc_amount ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    async with await get_connection() as db:
        async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def add_product(name: str, uc_amount: int, price: float, cost_price: float = 0.0, sort_order: int = 0) -> int:
    async with await get_connection() as db:
        cursor = await db.execute(
            "INSERT INTO products (name, uc_amount, price, cost_price, sort_order) VALUES (?, ?, ?, ?, ?)",
            (name, uc_amount, price, cost_price, sort_order),
        )
        await db.commit()
        return cursor.lastrowid


async def update_product_price(product_id: int, new_price: float) -> bool:
    async with await get_connection() as db:
        await db.execute("UPDATE products SET price = ? WHERE id = ?", (new_price, product_id))
        await db.commit()
        return True


async def toggle_product_status(product_id: int) -> bool:
    async with await get_connection() as db:
        product = await get_product(product_id)
        if not product:
            return False
        new_status = 0 if product["is_active"] == 1 else 1
        await db.execute("UPDATE products SET is_active = ? WHERE id = ?", (new_status, product_id))
        await db.commit()
        return True


async def delete_product(product_id: int) -> bool:
    async with await get_connection() as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()
        return True


# ==============================================================================
# ORDER FUNCTIONS
# ==============================================================================

async def generate_order_id() -> str:
    """Generate sequential PUBG-000001 style order ID."""
    async with await get_connection() as db:
        async with db.execute("SELECT COUNT(*) as count FROM orders") as cursor:
            row = await cursor.fetchone()
            next_num = (row["count"] or 0) + 1
            return f"PUBG-{next_num:06d}"


async def create_order(telegram_id: int, player_id: str, product_id: int, price: float, payment_method: str) -> str:
    order_id = await generate_order_id()
    async with await get_connection() as db:
        await db.execute(
            """INSERT INTO orders (order_id, user_id, player_id, product_id, price, status, payment_method)
               VALUES (?, ?, ?, ?, ?, 'WAITING_PAYMENT', ?)""",
            (order_id, telegram_id, player_id, product_id, price, payment_method),
        )
        await db.commit()
    return order_id


async def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    async with await get_connection() as db:
        query = """
            SELECT o.*, p.name as product_name, p.uc_amount, u.username, u.first_name
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            LEFT JOIN users u ON o.user_id = u.telegram_id
            WHERE o.order_id = ?
        """
        async with db.execute(query, (order_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_orders(telegram_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    async with await get_connection() as db:
        query = """
            SELECT o.*, p.name as product_name, p.uc_amount
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC
            LIMIT ?
        """
        async with db.execute(query, (telegram_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_order_status(order_id: str, status: str) -> bool:
    async with await get_connection() as db:
        await db.execute(
            "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE order_id = ?",
            (status, order_id),
        )
        await db.commit()
        return True


async def attach_order_screenshot(order_id: str, file_id: str) -> bool:
    async with await get_connection() as db:
        await db.execute(
            "UPDATE orders SET screenshot_file_id = ?, status = 'WAITING_PAYMENT', updated_at = CURRENT_TIMESTAMP WHERE order_id = ?",
            (file_id, order_id),
        )
        await db.commit()
        return True


async def get_orders_by_status(status: str, limit: int = 10) -> List[Dict[str, Any]]:
    async with await get_connection() as db:
        query = """
            SELECT o.*, p.name as product_name, p.uc_amount, u.username, u.first_name
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            LEFT JOIN users u ON o.user_id = u.telegram_id
            WHERE o.status = ?
            ORDER BY o.created_at DESC
            LIMIT ?
        """
        async with db.execute(query, (status, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_recent_orders(limit: int = 10) -> List[Dict[str, Any]]:
    async with await get_connection() as db:
        query = """
            SELECT o.*, p.name as product_name, p.uc_amount, u.username, u.first_name
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            LEFT JOIN users u ON o.user_id = u.telegram_id
            ORDER BY o.created_at DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_order_stats() -> Dict[str, Any]:
    today_str = date.today().isoformat()
    async with await get_connection() as db:
        # Today's orders & revenue
        async with db.execute(
            "SELECT COUNT(*) as count, COALESCE(SUM(price), 0.0) as revenue FROM orders WHERE date(created_at) = date(?) AND status = 'COMPLETED'",
            (today_str,),
        ) as c1:
            today_comp = await c1.fetchone()

        async with db.execute(
            "SELECT COUNT(*) as count FROM orders WHERE date(created_at) = date(?)",
            (today_str,),
        ) as c2:
            today_all = await c2.fetchone()

        # All-time stats
        async with db.execute("SELECT COUNT(*) as count, COALESCE(SUM(price), 0.0) as revenue FROM orders WHERE status = 'COMPLETED'") as c3:
            total_comp = await c3.fetchone()

        async with db.execute("SELECT COUNT(*) as count FROM orders") as c4:
            total_all = await c4.fetchone()

        async with db.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'CANCELLED' OR status = 'FAILED'") as c5:
            cancelled = await c5.fetchone()

        return {
            "today_orders": today_all["count"],
            "today_revenue": today_comp["revenue"],
            "total_orders": total_all["count"],
            "total_revenue": total_comp["revenue"],
            "completed_orders": total_comp["count"],
            "cancelled_orders": cancelled["count"],
        }


# ==============================================================================
# PAYMENT FUNCTIONS
# ==============================================================================

async def create_payment(order_id: str, amount: float, payment_method: str, payment_id: str = "") -> int:
    async with await get_connection() as db:
        cursor = await db.execute(
            "INSERT INTO payments (order_id, amount, payment_method, payment_id) VALUES (?, ?, ?, ?)",
            (order_id, amount, payment_method, payment_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_payment_by_order(order_id: str) -> Optional[Dict[str, Any]]:
    async with await get_connection() as db:
        async with db.execute("SELECT * FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1", (order_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_payment_status(order_id: str, status: str, raw_data: str = "") -> bool:
    async with await get_connection() as db:
        await db.execute(
            "UPDATE payments SET status = ?, raw_data = ? WHERE order_id = ?",
            (status, raw_data, order_id),
        )
        await db.commit()
        return True


# ==============================================================================
# SETTINGS FUNCTIONS
# ==============================================================================

async def get_setting(key: str, default: str = "") -> str:
    async with await get_connection() as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else default


async def set_setting(key: str, value: str):
    async with await get_connection() as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()


async def get_all_settings() -> Dict[str, str]:
    async with await get_connection() as db:
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            return {r["key"]: r["value"] for r in rows}
