import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from providers.base import (
    PaymentProvider,
    PaymentInitResult,
    WebhookVerificationResult,
    PaymentError,
    InvalidWebhookError,
)
from .client import TezCheckClient

logger = logging.getLogger("providers.tezcheck")


class TezCheckProvider(PaymentProvider):
    """TezCheck payment provider implementation."""

    def __init__(self, base_url: str, api_key: str, cash_desk_code: str, secret_key: str = ""):
        self.client = TezCheckClient(base_url=base_url, api_key=api_key, cash_desk_code=cash_desk_code)
        self.secret_key = secret_key

    async def create_payment(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: Optional[str] = None,
    ) -> PaymentInitResult:
        try:
            resp_data = await self.client.create_bill(
                order_id=order_id,
                amount=amount,
                description=description,
                return_url=return_url,
            )
            # Response parsing
            pay_url = resp_data.get("pay_url") or resp_data.get("payment_url") or resp_data.get("url")
            bill_id = str(resp_data.get("bill_id") or resp_data.get("id") or "")

            if not pay_url:
                raise PaymentError("TezCheck to'lov havolasi qaytarmadi", provider="TezCheck", raw_data=resp_data)

            return PaymentInitResult(
                is_success=True,
                payment_url=pay_url,
                provider_transaction_id=bill_id,
                raw_response=resp_data,
            )
        except PaymentError:
            raise
        except Exception as e:
            logger.exception("Unexpected error in TezCheck create_payment")
            raise PaymentError(f"TezCheck to'lov yaratishda kutilmagan xatolik: {e}", provider="TezCheck") from e

    def verify_webhook(
        self,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> WebhookVerificationResult:
        """
        Verify TezCheck webhook authenticity and idempotency parameters.
        Supports HMAC-SHA256 signature verification if secret_key is configured.
        """
        # Signature verification if secret_key is provided
        if self.secret_key and signature:
            # Sorted payload canonical string
            payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            expected_sig = hmac.new(
                self.secret_key.encode("utf-8"),
                payload_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(expected_sig, signature):
                logger.warning(f"Invalid webhook signature. Expected: {expected_sig}, got: {signature}")
                raise InvalidWebhookError("TezCheck webhook imzo tekshiruvidan o'tmadi!", provider="TezCheck")

        order_id = str(payload.get("external_id") or payload.get("order_id") or "")
        bill_id = str(payload.get("bill_id") or payload.get("transaction_id") or payload.get("id") or "")
        raw_status = str(payload.get("status", "")).upper()
        amount_val = payload.get("amount", 0)

        try:
            amount = Decimal(str(amount_val))
        except Exception:
            amount = Decimal("0.00")

        # Normalize status
        if raw_status in ("PAID", "SUCCESS", "COMPLETED"):
            status = "PAID"
        elif raw_status in ("FAILED", "REJECTED", "ERROR"):
            status = "FAILED"
        else:
            status = "PENDING"

        return WebhookVerificationResult(
            is_valid=True,
            order_id=order_id,
            provider_transaction_id=bill_id,
            amount=amount,
            status=status,
            raw_payload=payload,
        )
