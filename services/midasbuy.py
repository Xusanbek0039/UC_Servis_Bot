import re
import uuid
import logging
import httpx
from typing import Tuple
from config import MIDASBUY_BASE_URL, MIDASBUY_API_KEY, MIDASBUY_SECRET

logger = logging.getLogger("services.midasbuy")


class MidasbuyService:
    """Midasbuy API client with Mock fallback for development and testing."""

    @staticmethod
    async def validate_player(player_id: str) -> Tuple[bool, str, str]:
        """
        Validates PUBG Player ID.
        Returns: (is_valid, nickname, error_message)
        """
        player_id = str(player_id).strip()
        if not re.match(r"^\d{8,12}$", player_id):
            return False, "", "Player ID faqat 8 dan 12 gacha raqamlardan iborat bo'lishi kerak."

        # If real Midasbuy credentials are provided in .env
        if MIDASBUY_API_KEY and MIDASBUY_SECRET:
            try:
                # TODO: Connect to official partner endpoint according to your Midasbuy contract
                url = f"{MIDASBUY_BASE_URL}/api/v1/pubgm/player/check"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json={"player_id": player_id, "api_key": MIDASBUY_API_KEY})
                    if resp.status_code == 200:
                        data = resp.json()
                        nickname = data.get("nickname") or f"Player_{player_id[-4:]}"
                        return True, nickname, ""
                    return False, "", "Midasbuy serverida Player ID topilmadi."
            except Exception as e:
                logger.error(f"Midasbuy validation error: {e}")
                return False, "", f"Midasbuy ulanish xatosi: {e}"

        # Mock simulation
        mock_nicknames = {
            "5123456789": "UZB_Sniper_PRO",
            "5234567890": "Tashkent_Warrior",
            "5345678901": "PUBG_Champion",
        }
        nickname = mock_nicknames.get(player_id, f"Player_{player_id[-4:]}")
        return True, nickname, ""

    @staticmethod
    async def deliver_uc(order_id: str, player_id: str, uc_amount: int) -> Tuple[bool, str, str]:
        """
        Delivers UC to player.
        Returns: (is_success, provider_transaction_id, error_message)
        """
        logger.info(f"Delivering {uc_amount} UC to player {player_id} for order {order_id}")

        if MIDASBUY_API_KEY and MIDASBUY_SECRET:
            try:
                # TODO: Official Midasbuy topup delivery endpoint
                url = f"{MIDASBUY_BASE_URL}/api/v1/pubgm/order/topup"
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(
                        url,
                        json={
                            "order_id": order_id,
                            "player_id": player_id,
                            "uc_amount": uc_amount,
                            "api_key": MIDASBUY_API_KEY,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        tx_id = data.get("transaction_id") or order_id
                        return True, tx_id, ""
                    return False, "", f"Midasbuy xatoligi: {resp.text}"
            except Exception as e:
                logger.exception("Midasbuy delivery exception")
                return False, "", str(e)

        # Mock delivery simulation
        mock_tx_id = f"MOCK-MB-{uuid.uuid4().hex[:10].upper()}"
        return True, mock_tx_id, ""
