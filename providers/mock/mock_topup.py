import re
import uuid
import logging
from typing import List, Optional
from decimal import Decimal
from providers.base import (
    TopupProvider,
    PlayerInfo,
    ProviderProduct,
    TopupDeliveryResult,
    PlayerValidationError,
    DeliveryError,
)

logger = logging.getLogger("providers.mock")


class MockTopupProvider(TopupProvider):
    """
    Mock Top-Up Provider for local development, automated testing,
    and staging environments where Midasbuy credentials are not yet available.
    """

    MOCK_NICKNAMES = {
        "5123456789": "UZB_Sniper_PRO",
        "5234567890": "Tashkent_Warrior",
        "5345678901": "PUBG_Killer_01",
        "5456789012": "Samarkand_Eagle",
        "5567890123": "Fergana_King",
    }

    async def validate_player(self, player_id: str) -> PlayerInfo:
        """
        Validate PUBG Mobile Player ID.
        Standard PUBG IDs are 8 to 12 digits.
        Special test ID '999999999' intentionally triggers PlayerValidationError.
        """
        player_id = str(player_id).strip()

        # Simulate invalid ID for testing
        if player_id in ("999999999", "000000000"):
            raise PlayerValidationError(
                f"PUBG Player ID ({player_id}) topilmadi! Iltimos, o'yin ichidagi IDingizni tekshirib qaytadan kiriting.",
                provider="MockTopupProvider",
            )

        if not re.match(r"^\d{8,12}$", player_id):
            raise PlayerValidationError(
                "Player ID faqat 8 dan 12 gacha raqamlardan iborat bo'lishi kerak.",
                provider="MockTopupProvider",
            )

        nickname = self.MOCK_NICKNAMES.get(player_id, f"Player_{player_id[-4:]}")
        return PlayerInfo(
            player_id=player_id,
            nickname=nickname,
            region="Global",
            is_valid=True,
            level=56,
        )

    async def get_products(self) -> List[ProviderProduct]:
        """Return standard PUBG UC product list."""
        return [
            ProviderProduct(product_id="mock_60uc", name="60 UC", uc_amount=60, cost_price=Decimal("12000.00")),
            ProviderProduct(product_id="mock_325uc", name="325 UC", uc_amount=325, cost_price=Decimal("58000.00")),
            ProviderProduct(product_id="mock_660uc", name="660 UC", uc_amount=660, cost_price=Decimal("115000.00")),
            ProviderProduct(product_id="mock_1800uc", name="1800 UC", uc_amount=1800, cost_price=Decimal("300000.00")),
            ProviderProduct(product_id="mock_3850uc", name="3850 UC", uc_amount=3850, cost_price=Decimal("600000.00")),
            ProviderProduct(product_id="mock_8100uc", name="8100 UC", uc_amount=8100, cost_price=Decimal("1200000.00")),
        ]

    async def deliver(
        self,
        order_id: str,
        player_id: str,
        uc_amount: int,
        provider_product_id: Optional[str] = None,
    ) -> TopupDeliveryResult:
        """
        Simulate instant UC delivery.
        Special test player_id '111111111' triggers a simulated delivery error.
        """
        logger.info(f"[MOCK TOPUP] Delivering {uc_amount} UC to player {player_id} for order {order_id}")

        if player_id == "111111111":
            return TopupDeliveryResult(
                is_success=False,
                provider_order_id="",
                status="FAILED",
                error_message="Mock topup xatosi: Server vaqtincha band (Error code: 503)",
                raw_response={"status": "error", "code": 503},
            )

        mock_midas_id = f"MOCK-MIDAS-{uuid.uuid4().hex[:12].upper()}"
        return TopupDeliveryResult(
            is_success=True,
            provider_order_id=mock_midas_id,
            status="COMPLETED",
            raw_response={
                "status": "success",
                "order_id": order_id,
                "provider_tx_id": mock_midas_id,
                "delivered_amount": uc_amount,
            },
        )

    async def check_order(self, provider_order_id: str) -> TopupDeliveryResult:
        """Simulate order query."""
        return TopupDeliveryResult(
            is_success=True,
            provider_order_id=provider_order_id,
            status="COMPLETED",
            raw_response={"status": "success", "provider_order_id": provider_order_id},
        )
