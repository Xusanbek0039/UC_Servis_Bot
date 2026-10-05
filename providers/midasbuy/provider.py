import logging
from typing import List, Optional
from decimal import Decimal
from providers.base import (
    TopupProvider,
    PlayerInfo,
    ProviderProduct,
    TopupDeliveryResult,
    TopupError,
    PlayerValidationError,
    DeliveryError,
)
from .client import MidasbuyClient
from .exceptions import MidasbuyPlayerNotFoundError, MidasbuyDeliveryError

logger = logging.getLogger("providers.midasbuy")


class MidasbuyProvider(TopupProvider):
    """Midasbuy Top-Up Provider implementation."""

    def __init__(self, base_url: str, api_key: str, secret_key: str, app_id: str = ""):
        self.client = MidasbuyClient(
            base_url=base_url,
            api_key=api_key,
            secret_key=secret_key,
            app_id=app_id,
        )

    async def validate_player(self, player_id: str) -> PlayerInfo:
        """Validate player via Midasbuy."""
        try:
            data = await self.client.get_player_info(player_id)
            nickname = data.get("nickname") or data.get("user_name") or f"Player_{player_id}"
            region = data.get("zone_id") or "Global"
            return PlayerInfo(
                player_id=player_id,
                nickname=nickname,
                region=region,
                is_valid=True,
            )
        except PlayerValidationError:
            raise
        except Exception as e:
            logger.exception("Error in Midasbuy validate_player")
            raise PlayerValidationError(
                f"Midasbuy orqali tekshirishda xatolik yuz berdi: {e}",
                provider="Midasbuy",
            ) from e

    async def get_products(self) -> List[ProviderProduct]:
        """Fetch available products from Midasbuy."""
        # Standard default Midasbuy UC tiers
        return [
            ProviderProduct(product_id="pubg_60uc", name="60 UC", uc_amount=60, cost_price=Decimal("12000.00")),
            ProviderProduct(product_id="pubg_325uc", name="325 UC", uc_amount=325, cost_price=Decimal("58000.00")),
            ProviderProduct(product_id="pubg_660uc", name="660 UC", uc_amount=660, cost_price=Decimal("115000.00")),
            ProviderProduct(product_id="pubg_1800uc", name="1800 UC", uc_amount=1800, cost_price=Decimal("300000.00")),
            ProviderProduct(product_id="pubg_3850uc", name="3850 UC", uc_amount=3850, cost_price=Decimal("600000.00")),
            ProviderProduct(product_id="pubg_8100uc", name="8100 UC", uc_amount=8100, cost_price=Decimal("1200000.00")),
        ]

    async def deliver(
        self,
        order_id: str,
        player_id: str,
        uc_amount: int,
        provider_product_id: Optional[str] = None,
    ) -> TopupDeliveryResult:
        """Deliver UC via Midasbuy API."""
        prod_id = provider_product_id or f"pubg_{uc_amount}uc"
        try:
            resp = await self.client.create_topup_order(
                partner_order_id=order_id,
                player_id=player_id,
                product_id=prod_id,
                amount=uc_amount,
            )
            midas_id = str(resp.get("midasbuy_order_id") or resp.get("order_id") or order_id)
            return TopupDeliveryResult(
                is_success=True,
                provider_order_id=midas_id,
                status="COMPLETED",
                raw_response=resp,
            )
        except DeliveryError as de:
            return TopupDeliveryResult(
                is_success=False,
                provider_order_id="",
                status="FAILED",
                error_message=str(de),
                raw_response=de.raw_data if isinstance(de.raw_data, dict) else {},
            )
        except Exception as e:
            logger.exception("Unexpected error in Midasbuy deliver")
            return TopupDeliveryResult(
                is_success=False,
                provider_order_id="",
                status="FAILED",
                error_message=str(e),
            )

    async def check_order(self, provider_order_id: str) -> TopupDeliveryResult:
        """Check order status on Midasbuy."""
        try:
            resp = await self.client.query_order(provider_order_id)
            status = resp.get("status", "SUCCESS")
            return TopupDeliveryResult(
                is_success=(status == "SUCCESS"),
                provider_order_id=provider_order_id,
                status="COMPLETED" if status == "SUCCESS" else "PROCESSING",
                raw_response=resp,
            )
        except Exception as e:
            return TopupDeliveryResult(
                is_success=False,
                provider_order_id=provider_order_id,
                status="FAILED",
                error_message=str(e),
            )
