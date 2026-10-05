import pytest
from decimal import Decimal
from apps.users.models import TelegramUser, BalanceLedger, Player
from apps.users.services import UserService
from apps.referrals.models import ReferralRelationship


@pytest.mark.django_db
def test_user_registration_and_update():
    """Test registering a new user and updating user profile."""
    user, created = UserService.get_or_create_user(
        telegram_id=12345678,
        username="test_gamer",
        first_name="Jasur",
        last_name="Aliyev",
    )
    assert created is True
    assert user.telegram_id == 12345678
    assert user.username == "test_gamer"
    assert user.balance == Decimal("0.00")

    # Update profile on next interaction
    updated_user, created_again = UserService.get_or_create_user(
        telegram_id=12345678,
        username="pro_sniper_uz",
        first_name="Jasurbek",
    )
    assert created_again is False
    assert updated_user.username == "pro_sniper_uz"
    assert updated_user.first_name == "Jasurbek"


@pytest.mark.django_db
def test_referral_link_registration():
    """Test referral linking when registering with referrer_telegram_id."""
    referrer, _ = UserService.get_or_create_user(telegram_id=111111, username="first_inviter")
    
    # New user registers via referral link
    invited_user, _ = UserService.get_or_create_user(
        telegram_id=222222,
        username="invited_friend",
        referrer_telegram_id=referrer.telegram_id,
    )
    assert invited_user.referrer == referrer
    assert ReferralRelationship.objects.filter(referrer=referrer, referred_user=invited_user).exists()


@pytest.mark.django_db
def test_balance_transaction_and_ledger():
    """Test atomic balance deposits, withdrawals, and ledger record integrity."""
    user, _ = UserService.get_or_create_user(telegram_id=555555, username="rich_player")
    assert user.balance == Decimal("0.00")

    # 1. Deposit 100,000 UZS
    ledger1 = UserService.update_balance(
        user=user,
        amount=Decimal("100000.00"),
        transaction_type=BalanceLedger.TransactionType.DEPOSIT,
        description="Hisobni to'ldirish",
        reference_id="DEP-001",
    )
    assert user.balance == Decimal("100000.00")
    assert ledger1.balance_before == Decimal("0.00")
    assert ledger1.balance_after == Decimal("100000.00")

    # 2. Spend 35,000 UZS
    ledger2 = UserService.update_balance(
        user=user,
        amount=Decimal("-35000.00"),
        transaction_type=BalanceLedger.TransactionType.ORDER_PAYMENT,
        description="UC xaridi",
        reference_id="PUBG-001",
    )
    assert user.balance == Decimal("65000.00")
    assert ledger2.balance_before == Decimal("100000.00")
    assert ledger2.balance_after == Decimal("65000.00")

    # 3. Insufficient balance test - should raise ValueError and NOT change balance
    with pytest.raises(ValueError, match="yetarli emas"):
        UserService.update_balance(
            user=user,
            amount=Decimal("-100000.00"),
            transaction_type=BalanceLedger.TransactionType.ORDER_PAYMENT,
        )

    # Balance must remain exactly 65,000 UZS
    user.refresh_from_db()
    assert user.balance == Decimal("65000.00")


@pytest.mark.django_db
def test_save_player_profile():
    """Test saving PUBG player profile."""
    user, _ = UserService.get_or_create_user(telegram_id=777777, username="pubg_pro")
    player = UserService.save_player(
        user=user,
        player_id="5123456789",
        nickname="UZB_Sniper_PRO",
        region="Global",
    )
    assert player.player_id == "5123456789"
    assert player.nickname == "UZB_Sniper_PRO"
    assert player.user == user
