"""Daily compressed MongoDB logical snapshots with retention."""
import asyncio
import gzip
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import json_util

import database as db
from config import ADMIN_IDS, BACKUP_DIR, BACKUP_RETENTION_DAYS

logger = logging.getLogger("services.backup")
COLLECTIONS = ("users", "orders", "payments", "products", "settings", "counters", "supplier_orders", "price_snapshots")


async def create_backup(destination: Path | None = None) -> Path:
    target_dir = destination or (Path(__file__).resolve().parents[1] / BACKUP_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    target = target_dir / f"mongodb-backup-{stamp}.json.gz"
    database = db.get_db()
    archive = {}
    for name in COLLECTIONS:
        archive[name] = [doc async for doc in database[name].find({})]
    payload = json_util.dumps(archive, ensure_ascii=False).encode("utf-8")
    await asyncio.to_thread(_write_gzip, target, payload)
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKUP_RETENTION_DAYS)
    for old in target_dir.glob("mongodb-backup-*.json.gz"):
        try:
            if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < cutoff:
                old.unlink()
        except OSError:
            logger.warning("Could not prune an old MongoDB backup file")
    logger.info("MongoDB snapshot created: %s", target.name)
    return target


def _write_gzip(path: Path, payload: bytes):
    with gzip.open(path, "wb", compresslevel=6) as stream:
        stream.write(payload)


async def backup_loop(bot):
    while True:
        try:
            await create_backup()
        except Exception as exc:
            logger.exception("MongoDB backup failed (%s)", type(exc).__name__)
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, "⚠️ Database backup amalga oshmadi. Server disk joyi va MongoDB ulanishini tekshiring.")
                except Exception:
                    pass
        await asyncio.sleep(24 * 60 * 60)
