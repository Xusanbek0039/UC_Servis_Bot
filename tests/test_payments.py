import pytest
import hmac
import hashlib
import json
from decimal import Decimal
from apps.users.services import UserService
from apps.products.models import Product
from apps.orders.models import Order
from apps.orders.services import OrderService
from apps.payments.models import Payment, ManualPayment
from apps.payments.services import PaymentService
from providers.tezcheck.provider import TezCheckProvider
from providers.base import InvalidWebhookError


@pytest.fixture
def payment_setup():
    user, _ = UserService.get_or_create_user(telegram_id=666777, username="pay_tester")
    product = Product.objects.create(
        name="325 UC",
        uc_amount=325,
        price=Decimal("70000.00"),
        cost_price=Decimal("58000.00"),
        provider=Product.ProviderType.MOCK,
        delivery_method=Product.DeliveryMethod.AUTO,
    )
    order = OrderService.create_order(
        user=user,
        product=product,
        player_id="5123456789",
        player_nickname="UZB_Sniper_PRO",
        payment_method=Order.PaymentMethod.TEZCHECK,
    )
    return user, product, order


def test_tezcheck_webhook_signature_verification():
    """Test HMAC-SHA256 signature verification logic."""
    secret = "my_secret_key"
    provider = TezCheckProvider(
        base_url="https://api.tezcheck.uz",
        api_key="test_api_key",
        cash_desk_code="desk1",
        secret_key=secret,
    )

    payload = {
        "bill_id": "123456",
        "external_id": "PUBG-20261005-000001",
        "amount": 70000,
        "status": "PAID",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    correct_sig = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    # Valid signature
    res = provider.verify_webhook(payload, signature=correct_sig)
    assert res.is_valid is True
    assert res.order_id == "PUBG-20261005-000001"
    assert res.status == "PAID"

    # Invalid signature should raise InvalidWebhookError
    with pytest.raises(InvalidWebhookError):
        provider.verify_webhook(payload, signature="fraudulent_tampered_sig")


@pytest.mark.django_db(transaction=True)
def test_tezcheck_webhook_processing_and_idempotency(payment_setup):
    """
    Test processing payment via webhook and verify strict idempotency.
    Sending the same webhook twice must not duplicate actions.
    """
    from apps.settings.models import BotSettings
    bot_settings = BotSettings.load()
    bot_settings.default_delivery_mode = BotSettings.DeliveryMode.AUTO
    bot_settings.save()

    user, product, order = payment_setup

    webhook_payload = {
        "bill_id": "TEZ-BILL-9999",
        "external_id": order.order_id,
        "amount": 70000,
        "status": "PAID",
    }

    # 1. First webhook delivery
    success, msg = PaymentService.process_tezcheck_webhook(webhook_payload)
    assert success is True

    order.refresh_from_db()
    payment = Payment.objects.filter(order=order).first()
    assert payment is not None
    assert payment.status == Payment.PaymentStatus.PAID
    assert payment.provider_transaction_id == "TEZ-BILL-9999"
    # Auto delivery with Mock succeeds
    assert order.status == Order.Status.COMPLETED

    # 2. Duplicate webhook delivery (Idempotency test)
    success_dup, msg_dup = PaymentService.process_tezcheck_webhook(webhook_payload)
    assert success_dup is True
    assert "Already processed" in msg_dup

    # Count of payments for this order must remain exactly 1
    assert Payment.objects.filter(order=order).count() == 1


@pytest.mark.django_db
def test_manual_card_payment_flow_and_admin_approval(payment_setup):
    """Test manual card payment check submission and admin approval."""
    user, product, order = payment_setup
    order.payment_method = Order.PaymentMethod.MANUAL_CARD
    order.save(update_fields=["payment_method"])

    # 1. User submits check screenshot
    manual_entry = PaymentService.create_manual_card_payment(
        order=order,
        telegram_file_id="AgACAgIAAxkBAAE...",
    )
    assert manual_entry.status == ManualPayment.ManualStatus.PENDING
    assert manual_entry.payment.status == Payment.PaymentStatus.PENDING

    # 2. Admin approves payment
    approved, msg = PaymentService.admin_approve_manual_payment(
        manual_payment_id=manual_entry.id,
        admin_identifier="admin_bekzod",
    )
    assert approved is True

    manual_entry.refresh_from_db()
    assert manual_entry.status == ManualPayment.ManualStatus.APPROVED
    assert manual_entry.reviewed_by == "admin_bekzod"
    assert manual_entry.payment.status == Payment.PaymentStatus.PAID

    order.refresh_from_db()
    # Order marked paid and delivered
    assert order.status in [Order.Status.PAID, Order.Status.COMPLETED, Order.Status.MANUAL_REVIEW]


@pytest.mark.django_db
def test_manual_card_payment_rejection(payment_setup):
    """Test manual card payment check rejection by admin."""
    user, product, order = payment_setup
    manual_entry = PaymentService.create_manual_card_payment(
        order=order,
        telegram_file_id="AgACAgIAAxkBAAEFAKE...",
    )

    rejected, msg = PaymentService.admin_reject_manual_payment(
        manual_payment_id=manual_entry.id,
        admin_identifier="admin_bekzod",
        reason="Chek soxta",
    )
    assert rejected is True

    manual_entry.refresh_from_db()
    assert manual_entry.status == ManualPayment.ManualStatus.REJECTED
    assert manual_entry.rejection_reason == "Chek soxta"
    assert manual_entry.payment.status == Payment.PaymentStatus.FAILED

    order.refresh_from_db()
    assert order.status == Order.Status.FAILED
    assert "soxta" in order.error_message
