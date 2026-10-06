"""Deprecated compatibility shim; mock Midasbuy success was unsafe in production."""
from services.liogames import LioGamesService


class MidasbuyService:
    @staticmethod
    async def validate_player(player_id: str):
        return await LioGamesService.verify_player(player_id)

    @staticmethod
    async def deliver_uc(order_id: str, player_id: str, uc_amount: int):
        # The caller must use the mapped LioGames product and variation IDs.
        return False, "", "Midasbuy mock delivery o'chirilgan; LioGames product/variation mapping kerak."
