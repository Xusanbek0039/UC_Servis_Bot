import os
from django.conf import settings
from .base import PaymentProvider, TopupProvider
from .tezcheck.provider import TezCheckProvider
from .midasbuy.provider import MidasbuyProvider
from .mock.mock_topup import MockTopupProvider


def get_payment_provider(provider_name: str = "TEZCHECK") -> PaymentProvider:
    """Factory to retrieve configured payment provider instance."""
    provider_name = (provider_name or "TEZCHECK").upper()

    if provider_name == "TEZCHECK":
        return TezCheckProvider(
            base_url=getattr(settings, "TEZCHECK_BASE_URL", "https://api.tezcheck.uz"),
            api_key=getattr(settings, "TEZCHECK_API_KEY", ""),
            cash_desk_code=getattr(settings, "TEZCHECK_CASH_DESK_CODE", ""),
            secret_key=getattr(settings, "TEZCHECK_SECRET_KEY", ""),
        )
    raise ValueError(f"Noma'lum to'lov provayderi: {provider_name}")


def get_topup_provider(provider_name: str = None) -> TopupProvider:
    """Factory to retrieve configured top-up provider instance."""
    if not provider_name:
        provider_name = getattr(settings, "DEFAULT_TOPUP_PROVIDER", "MOCK")

    provider_name = provider_name.upper()

    if provider_name == "MIDASBUY":
        # If API key is present, use real Midasbuy, otherwise fallback to mock
        api_key = getattr(settings, "MIDASBUY_API_KEY", "")
        if api_key:
            return MidasbuyProvider(
                base_url=getattr(settings, "MIDASBUY_BASE_URL", "https://api.midasbuy.com"),
                api_key=api_key,
                secret_key=getattr(settings, "MIDASBUY_SECRET", ""),
                app_id=getattr(settings, "MIDASBUY_APP_ID", ""),
            )
        return MockTopupProvider()

    if provider_name in ("MOCK", "MANUAL"):
        return MockTopupProvider()

    return MockTopupProvider()
