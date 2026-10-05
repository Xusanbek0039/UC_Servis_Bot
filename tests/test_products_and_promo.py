import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from apps.products.models import Product
from apps.products.services import ProductService
from apps.promo.models import PromoCode
from apps.promo.services import PromoService
from apps.users.services import UserService


@pytest.mark.django_db
def test_product_seeding_and_profit_calculation():
    """Test product creation and profit calculation."""
    ProductService.seed_default_products()
    products = ProductService.get_active_products()
    assert products.count() == 6

    p60 = products.filter(uc_amount=60).first()
    assert p60 is not None
    assert p60.price == Decimal("15000.00")
    assert p60.cost_price == Decimal("12000.00")
    assert p60.profit == Decimal("3000.00")


@pytest.mark.django_db
def test_promo_code_percentage_discount():
    """Test percentage promo code validation and discount calculation."""
    user, _ = UserService.get_or_create_user(telegram_id=888888, username="promo_tester")
    promo = PromoCode.objects.create(
        code="WELCOME10",
        discount_type=PromoCode.DiscountType.PERCENTAGE,
        discount_value=Decimal("10.00"),  # 10%
        max_uses=5,
        min_order_amount=Decimal("10000.00"),
    )

    # 100,000 order -> 10% discount is 10,000
    valid_promo, discount, msg = PromoService.validate_promo(
        code="WELCOME10",
        order_amount=Decimal("100000.00"),
        user=user,
    )
    assert valid_promo == promo
    assert discount == Decimal("10000.00")

    # Below min_order_amount
    invalid_promo, disc, err = PromoService.validate_promo(
        code="WELCOME10",
        order_amount=Decimal("5000.00"),
        user=user,
    )
    assert invalid_promo is None
    assert "Minimal buyurtma" in err


@pytest.mark.django_db
def test_promo_code_fixed_discount_and_expiry():
    """Test fixed discount and expired promo code behavior."""
    user, _ = UserService.get_or_create_user(telegram_id=999999, username="promo_user2")
    expired_promo = PromoCode.objects.create(
        code="EXPIRED50",
        discount_type=PromoCode.DiscountType.FIXED,
        discount_value=Decimal("5000.00"),
        expires_at=timezone.now() - timedelta(days=1),
    )

    valid_promo, _, err = PromoService.validate_promo(
        code="EXPIRED50",
        order_amount=Decimal("50000.00"),
        user=user,
    )
    assert valid_promo is None
    assert "muddati tugagan" in err


@pytest.mark.django_db
def test_promo_code_usage_limit_and_user_duplicate():
    """Test that a user cannot use the same promo code twice."""
    user, _ = UserService.get_or_create_user(telegram_id=121212, username="greedy_user")
    promo = PromoCode.objects.create(
        code="BONUS5K",
        discount_type=PromoCode.DiscountType.FIXED,
        discount_value=Decimal("5000.00"),
        max_uses=2,
    )

    # First use
    PromoService.record_usage(promo, user, "PUBG-TEST-1", Decimal("5000.00"))
    promo.refresh_from_db()
    assert promo.used_count == 1

    # Attempt to use again with same user
    p, _, err = PromoService.validate_promo("BONUS5K", Decimal("50000.00"), user)
    assert p is None
    assert "avval foydalangansiz" in err
