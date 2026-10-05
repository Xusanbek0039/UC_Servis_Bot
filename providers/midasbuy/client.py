import time
import hmac
import hashlib
import json
import logging
import httpx
from typing import Dict, Any, Optional
from .exceptions import MidasbuyApiError, MidasbuyPlayerNotFoundError, MidasbuyDeliveryError

logger = logging.getLogger("providers.midasbuy")


class MidasbuyClient:
    """
    HTTP Client for Midasbuy (Tencent/PUBG Mobile Partner API).
    Implements standard partner authentication (HMAC-SHA256 signature).
    """

    def __init__(self, base_url: str, api_key: str, secret_key: str, app_id: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.secret_key = secret_key
        self.app_id = app_id
        self.timeout = 25.0

    def generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC-SHA256 signature according to partner API specifications:
        1. Sort keys alphabetically
        2. Format as key1=val1&key2=val2...
        3. HMAC with secret_key
        """
        filtered_params = {k: v for k, v in params.items() if v is not None and v != "" and k != "sign"}
        sorted_keys = sorted(filtered_params.keys())
        query_string = "&".join(f"{k}={filtered_params[k]}" for k in sorted_keys)
        
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    async def get_player_info(self, player_id: str) -> Dict[str, Any]:
        """
        Verify PUBG Mobile Player ID on Midasbuy.
        Note: Exact enterprise endpoint depends on partner agreement.
        TODO: Set endpoint path according to official Midasbuy Partner API contract.
        """
        url = f"{self.base_url}/api/v1/pubgm/player/check"
        params = {
            "app_id": self.app_id,
            "api_key": self.api_key,
            "player_id": player_id,
            "timestamp": int(time.time()),
        }
        params["sign"] = self.generate_signature(params)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=params)
                
                if response.status_code == 404:
                    raise MidasbuyPlayerNotFoundError(player_id, raw_data=response.text)
                
                if response.status_code != 200:
                    logger.error(f"Midasbuy player check error: {response.status_code} {response.text}")
                    raise MidasbuyApiError(f"Midasbuy server xatosi: {response.status_code}", raw_data=response.text)

                data = response.json()
                # Check return code
                if data.get("return_code") != 0 and data.get("code") not in (0, 200, "0"):
                    msg = data.get("return_msg") or data.get("message") or "Player not found"
                    raise MidasbuyPlayerNotFoundError(player_id, raw_data=data)

                return data
        except httpx.RequestError as exc:
            logger.error(f"Midasbuy connection error: {exc}")
            raise MidasbuyApiError("Midasbuy serveriga ulanishda xatolik yuz berdi", raw_data=str(exc)) from exc

    async def create_topup_order(
        self,
        partner_order_id: str,
        player_id: str,
        product_id: str,
        amount: int,
    ) -> Dict[str, Any]:
        """
        Direct top-up delivery to PUBG player account.
        TODO: Confirm endpoint path and parameters with Midasbuy contract.
        """
        url = f"{self.base_url}/api/v1/pubgm/order/topup"
        params = {
            "app_id": self.app_id,
            "api_key": self.api_key,
            "partner_order_id": partner_order_id,
            "player_id": player_id,
            "product_id": product_id,
            "amount": amount,
            "timestamp": int(time.time()),
        }
        params["sign"] = self.generate_signature(params)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=params)
                if response.status_code != 200:
                    raise MidasbuyDeliveryError(
                        f"Midasbuy topup delivery error: {response.status_code}",
                        order_id=partner_order_id,
                        raw_data=response.text,
                    )
                data = response.json()
                if data.get("return_code") != 0 and data.get("code") not in (0, 200, "0"):
                    raise MidasbuyDeliveryError(
                        data.get("return_msg") or "Delivery failed on provider",
                        order_id=partner_order_id,
                        raw_data=data,
                    )
                return data
        except httpx.RequestError as exc:
            logger.error(f"Midasbuy topup connection error: {exc}")
            raise MidasbuyDeliveryError(
                "Midasbuy bilan bog'lanishda xatolik",
                order_id=partner_order_id,
                raw_data=str(exc),
            ) from exc

    async def query_order(self, partner_order_id: str) -> Dict[str, Any]:
        """Query top-up order status on Midasbuy."""
        url = f"{self.base_url}/api/v1/pubgm/order/query"
        params = {
            "app_id": self.app_id,
            "partner_order_id": partner_order_id,
            "timestamp": int(time.time()),
        }
        params["sign"] = self.generate_signature(params)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    raise MidasbuyApiError(f"Query order failed: {response.status_code}", raw_data=response.text)
                return response.json()
        except httpx.RequestError as exc:
            raise MidasbuyApiError("Midasbuy ulanish xatosi", raw_data=str(exc)) from exc
