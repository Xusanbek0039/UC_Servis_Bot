import asyncio
import gzip
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

from services.pricing import calculate_price, product_sellable
from services.liogames import LioGamesError, LioGamesService
from services.price_monitor import _find_variation_price
from services.order_service import OrderService
from services.price_monitor import update_usd_rate
from services.backup import create_backup
import database as database_module


class PricingTests(unittest.TestCase):
    def test_formula_and_100_uzs_rounding(self):
        quote = calculate_price("0.88", "12000", "30", "14000")
        self.assertEqual(quote.cost_uzs, Decimal("10560.00"))
        self.assertEqual(quote.sale_price, Decimal("13800"))
        self.assertEqual(quote.blocked_reason, "")

    def test_max_price_blocks_then_recovers(self):
        blocked = calculate_price("0.88", "12000", 30, 13500)
        recovered = calculate_price("0.88", "12000", 25, 13500)
        self.assertEqual(blocked.blocked_reason, "MAX_PRICE_EXCEEDED")
        self.assertEqual(recovered.blocked_reason, "")

    def test_manual_block_is_independent(self):
        item = {"is_active": 1, "manual_block": True, "supplier_price_usd": 1,
                "supplier_product_id": "1", "supplier_variation_id": "2", "max_price": 10, "price": 5}
        self.assertFalse(product_sellable(item))

    def test_supplier_mapping_and_maximum_required(self):
        item = {"is_active": 1, "manual_block": False, "supplier_price_usd": 1,
                "supplier_product_id": "1", "supplier_variation_id": "2", "max_price": 0, "price": 5}
        self.assertFalse(product_sellable(item))
        item["max_price"] = 6
        self.assertTrue(product_sellable(item))

    def test_catalogue_price_parser_finds_tier(self):
        data = {"data": [{"variation_id": 533766, "gold_price": "0.88", "available": True}]}
        self.assertEqual(_find_variation_price(data, "533766", "GOLD"), 0.88)

    def test_catalogue_parser_rejects_unavailable_variation(self):
        data = [{"variation_id": 533766, "gold": 0.88, "available": False}]
        self.assertIsNone(_find_variation_price(data, "533766", "GOLD"))

    def test_product_specific_block_does_not_change_another_package(self):
        blocked = {"is_active": 1, "manual_block": True, "supplier_price_usd": 1, "supplier_product_id": "1", "supplier_variation_id": "2", "max_price": 10, "price": 5}
        active = {**blocked, "manual_block": False}
        self.assertFalse(product_sellable(blocked))
        self.assertTrue(product_sellable(active))

    def test_emergency_sales_switch_reads_database_state(self):
        async def run():
            with patch("database.get_setting", new=AsyncMock(return_value="false")):
                self.assertFalse(await database_module.global_sales_enabled())
        asyncio.run(run())


class LioGamesSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_order_timeout_reconciles_by_client_ref_without_blind_retry(self):
        timeout = LioGamesError("timeout", retryable=True)
        with patch("services.liogames.LIOGAMES_MEMBER_CODE", "member"), \
             patch("services.liogames.LIOGAMES_SECRET", "secret"), \
             patch.object(LioGamesService, "_request", new=AsyncMock(side_effect=[timeout])), \
             patch.object(LioGamesService, "get_order_status", new=AsyncMock(return_value={"order_id": "supplier-1"})) as status:
            result = await LioGamesService.create_order(order_id="PUBG-1", product_id="66719", variation_id="533766", player_id="12345678")
        self.assertEqual(result["order_id"], "supplier-1")
        status.assert_awaited_once_with(client_ref="PUBG-1")

    async def test_bad_supplier_response_does_not_claim_success(self):
        with patch("services.liogames.LIOGAMES_MEMBER_CODE", "member"), \
             patch("services.liogames.LIOGAMES_SECRET", "secret"), \
             patch.object(LioGamesService, "_request", new=AsyncMock(side_effect=LioGamesError("400", status_code=400))):
            with self.assertRaises(LioGamesError):
                await LioGamesService.create_order(order_id="PUBG-2", product_id="66719", variation_id="533766", player_id="12345678")

    async def test_429_respects_retry_after_and_then_succeeds(self):
        class Response:
            def __init__(self, status, payload=None):
                self.status_code, self.headers, self._payload = status, {"Retry-After": "0"}, payload or {}
            def json(self):
                return self._payload
        class Client:
            calls = 0
            def __init__(self, *args, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def request(self, *args, **kwargs):
                Client.calls += 1
                return Response(429) if Client.calls == 1 else Response(200, {"ok": True, "data": {"ok": True}})
        with patch("services.liogames.httpx.AsyncClient", Client), patch("services.liogames.LIOGAMES_MAX_RETRIES", 1), patch("services.liogames.asyncio.sleep", new=AsyncMock()):
            result = await LioGamesService._request("GET", "products")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(Client.calls, 2)


class OrderStateTests(unittest.IsolatedAsyncioTestCase):
    def _patch_db(self, order):
        return patch.multiple(
            "services.order_service.db",
            get_order=AsyncMock(return_value=order),
            mark_order_payment_success=AsyncMock(return_value=True),
            update_payment_status=AsyncMock(return_value=True),
            claim_delivery=AsyncMock(return_value=True),
            get_setting=AsyncMock(return_value="AUTO"),
            store_supplier_order=AsyncMock(),
            complete_delivery_once=AsyncMock(return_value=True),
            set_delivery_status=AsyncMock(return_value=True),
            mark_supplier_submission_started=AsyncMock(),
            update_order_status=AsyncMock(return_value=True),
        )

    async def test_normal_supplier_success_is_completed_only_on_terminal_success(self):
        order = {"order_id": "PUBG-3", "user_id": 42, "status": "WAITING_PAYMENT", "payment_status": "PENDING",
                 "delivery_status": "NOT_STARTED", "supplier_product_id": "66719", "supplier_variation_id": "533766", "player_id": "12345678"}
        with self._patch_db(order), patch("services.order_service.LIOGAMES_AUTO_DELIVERY", True), \
             patch.object(LioGamesService, "create_order", new=AsyncMock(return_value={"order": {"id": "LIO-1", "status": "COMPLETED"}})), \
             patch.object(LioGamesService, "get_balance", new=AsyncMock(return_value={"balance": 100})), \
             patch.object(OrderService, "_notify_completed", new=AsyncMock()), \
             patch("services.order_service.ProofChannelService.send_or_update_proof", new=AsyncMock(return_value=True)):
            result = await OrderService.handle_payment_success(AsyncMock(), "PUBG-3", "tx-1")
        self.assertTrue(result)

    async def test_duplicate_callback_for_completed_order_does_not_claim_delivery(self):
        order = {"order_id": "PUBG-4", "user_id": 42, "status": "COMPLETED", "payment_status": "SUCCESS", "delivery_status": "COMPLETED"}
        with patch("services.order_service.db.get_order", new=AsyncMock(return_value=order)), \
             patch("services.order_service.db.update_payment_status", new=AsyncMock()), \
             patch("services.order_service.db.claim_delivery", new=AsyncMock()) as claim:
            self.assertTrue(await OrderService.handle_payment_success(AsyncMock(), "PUBG-4", "tx-1"))
        claim.assert_not_awaited()

    async def test_refunded_payment_never_claims_delivery(self):
        order = {"order_id": "PUBG-5", "user_id": 42, "status": "REFUNDED", "payment_status": "REFUNDED", "delivery_status": "NOT_STARTED"}
        with patch("services.order_service.db.get_order", new=AsyncMock(return_value=order)), \
             patch("services.order_service.db.update_payment_status", new=AsyncMock()), \
             patch("services.order_service.db.claim_delivery", new=AsyncMock()) as claim, \
             patch.object(OrderService, "notify_admins", new=AsyncMock()):
            self.assertFalse(await OrderService.handle_payment_success(AsyncMock(), "PUBG-5", "tx-1"))
        claim.assert_not_awaited()

    async def test_expired_order_late_payment_never_claims_delivery(self):
        order = {"order_id": "PUBG-LATE", "user_id": 42, "status": "EXPIRED", "payment_status": "EXPIRED", "delivery_status": "NOT_STARTED"}
        with patch("services.order_service.db.get_order", new=AsyncMock(return_value=order)), \
             patch("services.order_service.db.update_payment_status", new=AsyncMock()), \
             patch("services.order_service.db.claim_delivery", new=AsyncMock()) as claim, \
             patch.object(OrderService, "notify_admins", new=AsyncMock()):
            self.assertFalse(await OrderService.handle_payment_success(AsyncMock(), "PUBG-LATE", "late-tx"))
        claim.assert_not_awaited()

    async def test_low_supplier_balance_stops_automatic_order_creation(self):
        order = {"order_id": "PUBG-LOW", "user_id": 42, "status": "WAITING_PAYMENT", "payment_status": "PENDING", "delivery_status": "NOT_STARTED",
                 "supplier_product_id": "66719", "supplier_variation_id": "533766", "player_id": "12345678"}
        with self._patch_db(order), patch("services.order_service.LIOGAMES_AUTO_DELIVERY", True), \
             patch("services.order_service.LIOGAMES_STOP_ON_LOW_BALANCE", True), \
             patch.object(LioGamesService, "get_balance", new=AsyncMock(return_value={"balance": 0})), \
             patch.object(LioGamesService, "create_order", new=AsyncMock()) as create, \
             patch.object(OrderService, "notify_admins", new=AsyncMock()):
            self.assertFalse(await OrderService.handle_payment_success(AsyncMock(), "PUBG-LOW", "tx-low"))
        create.assert_not_awaited()

    async def test_proof_failure_does_not_roll_back_completed_delivery(self):
        order = {"order_id": "PUBG-PROOF", "user_id": 42, "status": "COMPLETED", "payment_status": "SUCCESS", "delivery_status": "COMPLETED"}
        with patch("services.order_service.db.get_order", new=AsyncMock(return_value=order)), \
             patch("services.order_service.db.store_supplier_order", new=AsyncMock()), \
             patch("services.order_service.db.complete_delivery_once", new=AsyncMock(return_value=True)), \
             patch("services.order_service.ProofChannelService.send_or_update_proof", new=AsyncMock(return_value=False)), \
             patch.object(OrderService, "_notify_completed", new=AsyncMock()):
            self.assertEqual(await OrderService.apply_supplier_status(AsyncMock(), "PUBG-PROOF", {"status": "COMPLETED"}), "COMPLETED")


class BackupTests(unittest.IsolatedAsyncioTestCase):
    async def test_mongodb_backup_contains_logical_collections(self):
        class Cursor:
            def __aiter__(self):
                async def values():
                    yield {"sample": "ok"}
                return values()
        class Collection:
            def find(self, query): return Cursor()
        class FakeDb:
            def __getitem__(self, name): return Collection()
        with tempfile.TemporaryDirectory() as directory, patch("services.backup.db.get_db", return_value=FakeDb()):
            path = await create_backup(Path(directory))
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                contents = stream.read()
        self.assertIn("price_snapshots", contents)
        self.assertIn("supplier_orders", contents)


class MoreOrderStateTests(unittest.IsolatedAsyncioTestCase):
    def _patch_db(self, order):
        return patch.multiple(
            "services.order_service.db",
            get_order=AsyncMock(return_value=order),
            mark_order_payment_success=AsyncMock(return_value=True),
            update_payment_status=AsyncMock(return_value=True),
            claim_delivery=AsyncMock(return_value=True),
            get_setting=AsyncMock(return_value="AUTO"),
            store_supplier_order=AsyncMock(),
            complete_delivery_once=AsyncMock(return_value=True),
            set_delivery_status=AsyncMock(return_value=True),
            mark_supplier_submission_started=AsyncMock(),
            update_order_status=AsyncMock(return_value=True),
        )

    async def test_supplier_timeout_keeps_order_processing_for_reconciliation(self):
        order = {"order_id": "PUBG-6", "user_id": 42, "status": "WAITING_PAYMENT", "payment_status": "PENDING", "delivery_status": "NOT_STARTED",
                 "supplier_product_id": "66719", "supplier_variation_id": "533766", "player_id": "12345678"}
        error = LioGamesError("ambiguous", retryable=True)
        with self._patch_db(order), patch("services.order_service.LIOGAMES_AUTO_DELIVERY", True), \
             patch.object(LioGamesService, "create_order", new=AsyncMock(side_effect=error)), \
             patch.object(OrderService, "notify_admins", new=AsyncMock()):
            result = await OrderService.handle_payment_success(AsyncMock(), "PUBG-6", "tx-1")
        self.assertFalse(result)

    async def test_pending_supplier_status_never_marks_completed(self):
        with patch("services.order_service.db.get_order", new=AsyncMock(return_value={"order_id": "PUBG-7", "payment_status": "SUCCESS", "delivery_status": "PROCESSING"})), \
             patch("services.order_service.db.store_supplier_order", new=AsyncMock()), \
             patch("services.order_service.db.set_delivery_status", new=AsyncMock()), \
             patch("services.order_service.db.update_order_status", new=AsyncMock()), \
             patch("services.order_service.db.complete_delivery_once", new=AsyncMock()) as complete:
            status = await OrderService.apply_supplier_status(AsyncMock(), "PUBG-7", {"order": {"id": "LIO-7", "status": "PROCESSING"}})
        self.assertEqual(status, "PROCESSING")
        complete.assert_not_awaited()

    async def test_supplier_failure_goes_to_manual_review(self):
        with patch("services.order_service.db.get_order", new=AsyncMock(return_value={"order_id": "PUBG-8", "payment_status": "SUCCESS", "delivery_status": "PROCESSING", "user_id": 42})), \
             patch("services.order_service.db.store_supplier_order", new=AsyncMock()), \
             patch("services.order_service.db.set_delivery_status", new=AsyncMock()), \
             patch("services.order_service.db.update_order_status", new=AsyncMock()) as update, \
             patch.object(OrderService, "notify_admins", new=AsyncMock()):
            status = await OrderService.apply_supplier_status(AsyncMock(), "PUBG-8", {"order": {"status": "FAILED"}})
        self.assertEqual(status, "FAILED")
        update.assert_awaited_once_with("PUBG-8", "MANUAL_REVIEW")


if __name__ == "__main__":
    unittest.main()
