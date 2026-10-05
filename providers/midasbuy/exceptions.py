from providers.base import TopupError, PlayerValidationError, DeliveryError

class MidasbuyApiError(TopupError):
    """General error from Midasbuy partner API."""
    def __init__(self, message: str, code: str = None, raw_data: any = None):
        super().__init__(message, provider="Midasbuy", raw_data=raw_data)
        self.code = code


class MidasbuyPlayerNotFoundError(PlayerValidationError):
    """Raised when PUBG player ID does not exist on Midasbuy servers."""
    def __init__(self, player_id: str, raw_data: any = None):
        super().__init__(f"PUBG Player ID ({player_id}) topilmadi yoki xato.", provider="Midasbuy", raw_data=raw_data)
        self.player_id = player_id


class MidasbuyDeliveryError(DeliveryError):
    """Raised when UC delivery to player fails."""
    def __init__(self, message: str, order_id: str = None, raw_data: any = None):
        super().__init__(message, provider="Midasbuy", raw_data=raw_data)
        self.order_id = order_id
