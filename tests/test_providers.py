import pytest
from decimal import Decimal
from providers.mock.mock_topup import MockTopupProvider
from providers.base import PlayerValidationError, TopupDeliveryResult
from providers.factory import get_topup_provider, get_payment_provider
from providers.tezcheck.provider import TezCheckProvider


@pytest.mark.asyncio
async def test_mock_player_validation_success():
    """Test validating regular player ID with Mock provider."""
    provider = MockTopupProvider()
    info = await provider.validate_player("5123456789")
    assert info.is_valid is True
    assert info.player_id == "5123456789"
    assert info.nickname == "UZB_Sniper_PRO"


@pytest.mark.asyncio
async def test_mock_player_validation_failure():
    """Test invalid player IDs raising PlayerValidationError."""
    provider = MockTopupProvider()

    # Invalid length/format
    with pytest.raises(PlayerValidationError, match="faqat 8 dan 12"):
        await provider.validate_player("123")

    # Special simulated test failure ID
    with pytest.raises(PlayerValidationError, match="topilmadi"):
        await provider.validate_player("999999999")


@pytest.mark.asyncio
async def test_mock_topup_delivery_success():
    """Test simulated topup delivery."""
    provider = MockTopupProvider()
    res: TopupDeliveryResult = await provider.deliver(
        order_id="PUBG-20261005-000001",
        player_id="5123456789",
        uc_amount=660,
    )
    assert res.is_success is True
    assert res.status == "COMPLETED"
    assert res.provider_order_id.startswith("MOCK-MIDAS-")


@pytest.mark.asyncio
async def test_mock_topup_delivery_simulated_failure():
    """Test simulated topup delivery failure on player_id '111111111'."""
    provider = MockTopupProvider()
    res: TopupDeliveryResult = await provider.deliver(
        order_id="PUBG-20261005-000002",
        player_id="111111111",
        uc_amount=660,
    )
    assert res.is_success is False
    assert res.status == "FAILED"
    assert "band" in res.error_message


def test_provider_factory():
    """Test provider factory functions."""
    topup_prov = get_topup_provider("MOCK")
    assert isinstance(topup_prov, MockTopupProvider)

    payment_prov = get_payment_provider("TEZCHECK")
    assert isinstance(payment_prov, TezCheckProvider)
