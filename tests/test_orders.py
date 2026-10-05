import pytest
from decimal import Decimal
from apps.users.services import UserService
from apps.products.models import Product
from apps.promo.models import PromoCode
from apps.orders.models import Order
from apps.orders.services import OrderService
from apps.settings.models import BotSettings


@pytest.fixture
def test_setup():
    user, _ = UserService.get_or_create_user(telegram_id=333444, username="order_tester")
    product = Product.objects.create(
        name="660 UC",
        uc_amount=660,
        price=Decimal("135000.00"),
        cost_price=Decimal("115000.00"),
        provider=Product.ProviderType.MOCK,
        delivery_method=Product.DeliveryMethod.AUTO,
    )
    return user, product


@pytest.mark.django_db
def test_order_id_generation_and_order_creation(test_setup):
    """Test generating sequential order numbers and initial WAITING_PAYMENT status."""
    user, product = test_setup

    order1 = OrderService.create_order(
        user=user,
        product=product,
        player_id="5123456789",
        player_nickname="UZB_Sniper_PRO",
        payment_method=Order.PaymentMethod.TEZCHECK,
    )

    assert order1.order_id.startswith("PUBG-")
    assert order1.order_id.endswith("-000001")
    assert order1.status == Order.Status.WAITING_PAYMENT
    assert order1.final_amount == Decimal("135000.00")

    # Second order should have sequence 000002
    order2 = OrderService.create_order(
        user=user,
        product=product,
        player_id="5123456789",
        player_nickname="UZB_Sniper_PRO",
        payment_method=Order.PaymentMethod.MANUAL_CARD,
    )
    assert order2.order_id.endswith("-000002")


@pytest.mark.django_db
def test_order_creation_with_promo_code(test_setup):
    """Test price reduction when valid promo code is applied."""
    user, product = test_setup
    promo = PromoCode.objects.create(
        code="SAVE15K",
        discount_type=PromoCode.DiscountType.FIXED,
        discount_value=Decimal("15000.00"),
    )

    order = OrderService.create_order(
        user=user,
        product=product,
        player_id="5123456789",
        player_nickname="UZB_Sniper_PRO",
        payment_method=Order.PaymentMethod.TEZCHECK,
        promo_code_str="SAVE15K",
    )
    assert order.amount == Decimal("135000.00")
    assert order.discount_amount == Decimal("15000.00")
    assert order.final_amount == Decimal("120000.00")
    assert order.promo_code == promo


@pytest.mark.django_db(transaction=True)
def test_pay_with_internal_balance(test_setup):
    """Test full checkout flow using internal balance."""
    bot_settings = BotSettings.load()
    bot_settings.default_delivery_mode = BotSettings.DeliveryMode.AUTO
    bot_settings.save()

    user, product = test_setup

    # Deposit funds to user balance
    from apps.users.models import BalanceLedger
    UserService.update_balance(
        user=user,
        amount=Decimal("150000.00"),
        transaction_type=BalanceLedger.TransactionType.DEPOSIT,
    )
    assert user.balance == Decimal("150000.00")

    order = OrderService.create_order(
        user=user,
        product=product,
        player_id="5123456789",
        player_nickname="UZB_Sniper_PRO",
        payment_method=Order.PaymentMethod.BALANCE,
    )

    success, msg = OrderService.pay_with_balance(order)
    assert success is True

    # User balance should be reduced: 150000 - 135000 = 15000
    user.refresh_from_db()
    assert user.balance == Decimal("15000.00")

    order.refresh_from_db()
    # Mock delivery succeeds
    assert order.status in [Order.Status.PAID, Order.Status.PROCESSING, Order.Status.COMPLETED]


@pytest.mark.django_db
def test_order_cancellation_and_balance_refund(test_setup):
    """Test cancelling a paid order and automatically refunding user balance."""
    user, product = test_setup
    order = OrderService.create_order(
        user=user,
        product=product,
        player_id="5123456789",
        player_nickname="UZB_Sniper_PRO",
        payment_method=Order.PaymentMethod.BALANCE,
    )
    # Simulate order being marked PAID
    order.status = Order.Status.PAID
    order.save(update_fields=["status"])

    assert user.balance == Decimal("0.00")

    # Cancel and refund
    success, msg = OrderService.cancel_order(
        order_id=order.order_id,
        reason="Admin test cancellation",
        admin_identifier="superadmin",
        refund=True,
    )
    assert success is True

    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED

    # User balance should be refunded the full final_amount
    user.refresh_from_db()
    assert user.balance == Decimal("135000.00")


@pytest.mark.django_db
def test_admin_manual_delivery(test_setup):
    """Test admin manual deliver button ("UC yuborildi")."""
    user, product = test_setup
    order = OrderService.create_order(
        user=user,
        product=product,
        player_id="5123456789",
        player_nickname="UZB_Sniper_PRO",
        payment_method=Order.PaymentMethod.MANUAL_CARD,
    )
    order.status = Order.Status.MANUAL_REVIEW
    order.save(update_fields=["status"])

    success, msg = OrderService.manual_deliver(order.order_id, admin_identifier="admin_azamat")
    assert success is True

    order.refresh_from_db()
    assert order.status == Order.Status.COMPLETED
    assert order.completed_at is not None
