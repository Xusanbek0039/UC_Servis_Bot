import hmac
import hashlib
import json
import logging
import httpx
from typing import Dict, Any, Tuple
from config import (
    TEZCHECK_BASE_URL,
    TEZCHECK_API_KEY,
    TEZCHECK_CASH_DESK_CODE,
    TEZCHECK_WEBHOOK_SECRET,
)

logger = logging.getLogger("services.tezcheck")


class TezCheckService:
    @staticmethod
    async def create_payment_bill(
        order_id: str, amount: float, description: str, return_url: str = ""
    ) -> Tuple[bool, str, str]:
        """
        Creates an invoice on TezCheck gateway and returns checkout URL.
        Returns: (is_success, payment_url, error_message)
        """
        if not TEZCHECK_API_KEY or TEZCHECK_API_KEY == "test_tezcheck_api_key":
            logger.info(f"[MOCK TEZCHECK] Generated mock payment URL for order {order_id}")
            # Mock payment checkout URL for dev testing
            mock_url = f"https://checkout.tezcheck.uz/pay/mock_{order_id}"
            return True, mock_url, ""

        url = f"{TEZCHECK_BASE_URL}/api/v1/bills/create"
        headers = {
            "Authorization": f"Bearer {TEZCHECK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "cash_desk_code": TEZCHECK_CASH_DESK_CODE,
            "external_id": order_id,
            "amount": int(amount),
            "description": description,
            "return_url": return_url,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code >= 400:
                    logger.error(f"TezCheck error: {resp.status_code} - {resp.text}")
                    return False, "", f"To'lov tizimi xatosi: {resp.status_code}"
                
                data = resp.json()
                pay_url = data.get("pay_url") or data.get("payment_url")
                if not pay_url:
                    return False, "", "To'lov havolasi olinmadi."
                return True, pay_url, ""
        except Exception as e:
            logger.exception("TezCheck connection failed")
            return False, "", f"To'lov serveriga ulanishda xatolik: {e}"

    @staticmethod
    def verify_webhook_signature(payload: Dict[str, Any], signature: str) -> bool:
        """Verify HMAC-SHA256 signature for incoming TezCheck webhook."""
        if not TEZCHECK_WEBHOOK_SECRET:
            return True

        if not signature:
            return False

        try:
            payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            expected_sig = hmac.new(
                TEZCHECK_WEBHOOK_SECRET.encode("utf-8"),
                payload_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected_sig, signature)
        except Exception as e:
            logger.error(f"Signature check error: {e}")
            return False
