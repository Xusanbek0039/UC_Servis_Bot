import httpx
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from providers.base import PaymentError

logger = logging.getLogger("providers.tezcheck")


class TezCheckClient:
    """HTTP Client for TezCheck Payment Gateway."""

    def __init__(self, base_url: str, api_key: str, cash_desk_code: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.cash_desk_code = cash_desk_code
        self.timeout = 20.0

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def create_bill(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call TezCheck API to create an invoice/bill."""
        url = f"{self.base_url}/api/v1/bills/create"
        payload = {
            "cash_desk_code": self.cash_desk_code,
            "external_id": order_id,
            "amount": int(amount),  # TezCheck expects integer in UZS tiyin or UZS
            "description": description,
            "return_url": return_url or "",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._headers())
                
                # Check for HTTP errors
                if response.status_code >= 400:
                    logger.error(
                        f"TezCheck API error: {response.status_code} - {response.text}"
                    )
                    raise PaymentError(
                        f"TezCheck to'lov tizimida xatolik: {response.status_code}",
                        provider="TezCheck",
                        raw_data=response.text,
                    )
                return response.json()
        except httpx.RequestError as exc:
            logger.error(f"TezCheck connection error: {exc}")
            raise PaymentError(
                "TezCheck to'lov serveri bilan ulanishda xatolik yuz berdi.",
                provider="TezCheck",
                raw_data=str(exc),
            ) from exc
