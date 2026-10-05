import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Tuple

import httpx

from config import TEZCHECK_API_KEY, TEZCHECK_BASE_URL, TEZCHECK_CASH_DESK_CODE

logger = logging.getLogger("services.tezcheck")
API_PATH = "/api/merchant/v1"


class TezCheckService:
    @staticmethod
    def _headers(method: str, path: str, body: bytes, idempotency_key: str = "") -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {TEZCHECK_API_KEY}",
            "X-Cash-Desk-Code": TEZCHECK_CASH_DESK_CODE,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timestamp = str(int(time.time()))
        digest = hashlib.sha256(body).hexdigest()
        signature = hmac.new(
            TEZCHECK_API_KEY.encode("utf-8"),
            f"{timestamp}.{method}.{path}.{digest}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers["X-TezCheck-Timestamp"] = timestamp
        headers["X-TezCheck-Signature"] = f"v1={signature}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:128]
        return headers

    @classmethod
    async def create_payment_bill(
        cls, order_id: str, amount: float, description: str, return_url: str = ""
    ) -> Tuple[bool, str, str, str]:
        """Create one fixed-amount TezCheck bill; amount is in UZS."""
        if not TEZCHECK_API_KEY or not TEZCHECK_CASH_DESK_CODE:
            return False, "", "", "TezCheck API kaliti yoki kassa kodi sozlanmagan."

        path = f"{API_PATH}/bills"
        payload: Dict[str, Any] = {
            "amount_minor": int(round(float(amount) * 100)),
            "title": description[:191],
            "external_reference": order_id,
        }
        if return_url:
            payload["return_url"] = return_url
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = cls._headers("POST", path, body, f"bill-{order_id}")

        try:
            async with httpx.AsyncClient(base_url=TEZCHECK_BASE_URL, timeout=20.0) as client:
            response = await client.post(path, content=body, headers=headers)
            if response.status_code >= 400:
                logger.error("TezCheck bill creation failed (%s): %s", response.status_code, response.text[:1000])
                if response.status_code == 401:
                    return (
                        False,
                        "",
                        "",
                        "TezCheck API kaliti qabul qilinmadi. Render Environment’da TEZCHECK_API_KEY qiymatini "
                        "TezCheck kabinetidagi faol Merchant API tokeni bilan almashtiring va servisni redeploy qiling.",
                    )
                if response.status_code == 403:
                    return (
                        False,
                        "",
                        "",
                        "TezCheck so‘rovni rad etdi. Kassa IP ruxsat ro‘yxati va API token ruxsatlarini tekshiring.",
                    )
                return False, "", "", f"TezCheck xatosi ({response.status_code}): {response.text[:300]}"

            result = response.json().get("data", {})
            payment_url = result.get("payment_url", "")
            bill_id = str((result.get("bill") or {}).get("id", ""))
            if not payment_url or not bill_id:
                logger.error("TezCheck response missing bill id or payment_url")
                return False, "", "", "TezCheck javobida to‘lov havolasi topilmadi."
            return True, payment_url, bill_id, ""
        except Exception as exc:
            logger.exception("TezCheck bill creation request failed")
            return False, "", "", f"To‘lov tizimiga ulanib bo‘lmadi: {exc}"

    @classmethod
    async def get_bill(cls, bill_id: str) -> Tuple[bool, Dict[str, Any], str]:
        """Fetch bill/payment status from TezCheck (no webhook required)."""
        if not TEZCHECK_API_KEY or not TEZCHECK_CASH_DESK_CODE:
            return False, {}, "TezCheck API kaliti yoki kassa kodi sozlanmagan."

        path = f"{API_PATH}/bills/{bill_id}"
        body = b""
        headers = cls._headers("POST", path, body)
        try:
            async with httpx.AsyncClient(base_url=TEZCHECK_BASE_URL, timeout=15.0) as client:
                response = await client.post(path, content=body, headers=headers)
            if response.status_code >= 400:
                logger.warning("TezCheck status lookup failed (%s): %s", response.status_code, response.text[:500])
                return False, {}, f"TezCheck holatni qaytara olmadi ({response.status_code})."
            return True, response.json().get("data", {}), ""
        except Exception as exc:
            logger.exception("TezCheck status request failed for bill %s", bill_id)
            return False, {}, f"To‘lov holatini tekshirib bo‘lmadi: {exc}"
