"""LioGames signed reseller API client (https://distribution.liogames.com/developers/)."""
import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from config import LIOGAMES_BASE_URL, LIOGAMES_MEMBER_CODE, LIOGAMES_SECRET, LIOGAMES_KEY_ID, LIOGAMES_MAX_RETRIES

logger = logging.getLogger("services.liogames")


class LioGamesError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, status_code: int = 0):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class LioGamesService:
    @staticmethod
    def configured() -> bool:
        return bool(LIOGAMES_MEMBER_CODE and LIOGAMES_SECRET)

    @staticmethod
    def _signed_headers(body: bytes) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        headers["x-liog-sign"] = hmac.new(LIOGAMES_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if LIOGAMES_KEY_ID:
            headers["X-LIOG-KEY-ID"] = LIOGAMES_KEY_ID
        return headers

    @classmethod
    async def _request(cls, method: str, path: str, payload: dict | None = None, *, signed: bool = False, retry: bool = True) -> dict[str, Any]:
        body = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")).encode()
        headers = cls._signed_headers(body) if signed else {"Accept": "application/json"}
        attempts = LIOGAMES_MAX_RETRIES + 1 if retry else 1
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
                    response = await client.request(method, f"{LIOGAMES_BASE_URL}/{path.lstrip('/')}", content=body if method != "GET" else None, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        delay = min(30, max(int(response.headers.get("Retry-After", 0) or 0), 2 ** attempt))
                        await asyncio.sleep(delay)
                        continue
                if response.status_code >= 400:
                    # Do not log response body: supplier responses can contain sensitive details.
                    raise LioGamesError(f"LioGames HTTP {response.status_code}", retryable=response.status_code in (429, 500, 502, 503, 504), status_code=response.status_code)
                data = response.json()
                if data.get("ok") is False:
                    raise LioGamesError(str(data.get("message") or data.get("code") or "LioGames request rejected"), retryable=data.get("code") in ("PROCESSING", "RATE_LIMIT"))
                return data.get("data", data)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise LioGamesError(f"LioGames network timeout: {type(exc).__name__}", retryable=True) from exc
        raise LioGamesError("LioGames request retries exhausted", retryable=True)

    @classmethod
    async def get_products(cls) -> dict[str, Any]:
        return await cls._request("GET", "products")

    @classmethod
    async def get_product_price(cls, product_id: str) -> dict[str, Any]:
        return await cls._request("GET", f"products/{product_id}/price-matrix")

    @classmethod
    async def get_variations(cls, product_id: str) -> dict[str, Any]:
        return await cls._request("GET", f"products/{product_id}/variations")

    @classmethod
    async def verify_player(cls, player_id: str) -> tuple[bool, str, str]:
        if not cls.configured():
            return False, "", "LioGames API sozlanmagan. Player ma'lumotini tasdiqlab bo'lmadi."
        try:
            result = await cls._request("POST", "username-check", {"member_code": LIOGAMES_MEMBER_CODE, "game": "pubg-mobile-global", "user_id": str(player_id)}, signed=True, retry=False)
            found = bool(result.get("found"))
            return found, str(result.get("username") or ""), "" if found else "LioGames bu Player ID'ni topmadi."
        except LioGamesError as exc:
            return False, "", str(exc)

    @classmethod
    async def get_balance(cls) -> dict[str, Any]:
        return await cls._request("POST", "balance", {"member_code": LIOGAMES_MEMBER_CODE}, signed=True)

    @classmethod
    async def create_order(cls, *, order_id: str, product_id: str, variation_id: str, player_id: str) -> dict[str, Any]:
        if not cls.configured() or not product_id or not variation_id:
            raise LioGamesError("LioGames credentials yoki PUBG product/variation mapping sozlanmagan")
        payload = {"member_code": LIOGAMES_MEMBER_CODE, "product_id": int(product_id), "variation_id": int(variation_id), "user_id": str(player_id), "client_ref": order_id}
        # A create timeout is ambiguous: first reconcile by the same client_ref. Never blind retry.
        try:
            return await cls._request("POST", "order-create", payload, signed=True, retry=False)
        except LioGamesError as exc:
            if not exc.retryable:
                raise
            try:
                status = await cls.get_order_status(client_ref=order_id)
                if status:
                    return status
            except LioGamesError:
                pass
            raise LioGamesError("LioGames create order natijasi noaniq; client_ref orqali qayta tekshirish kerak", retryable=True) from exc

    @classmethod
    async def get_order_status(cls, *, supplier_order_id: str = "", client_ref: str = "") -> dict[str, Any]:
        payload = {"member_code": LIOGAMES_MEMBER_CODE}
        if supplier_order_id:
            payload["order_id"] = supplier_order_id
        else:
            payload["client_ref"] = client_ref
        return await cls._request("POST", "order-status", payload, signed=True)
