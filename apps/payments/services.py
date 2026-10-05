import json
import logging
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from django.db import transaction
from django.utils import timezone
from .models import Payment, ManualPayment
from apps.orders.models import Order
from apps.orders.services import OrderService
from apps.settings.models import BotSettings
from apps.audit.models import AdminAction
from apps.notifications.services import NotificationService
from apps.providers.models import ProviderTransaction
from providers.factory import get_payment_provider
from providers.base import PaymentError, InvalidWebhookError

logger = logging.getLogger("apps.payments")


class PaymentService:
    @classmethod
    async def create_tezcheck_payment(cls, order: Order, return_url: Optional[str] = None) -> Tuple[bool, str, str]:
        """Initiate online payment with TezCheck."""
        provider = get_payment_provider("TEZCHECK")
        description = f"PUBG UC: {order.product.name} ({order.order_id})"

        try:
            res = await provider.create_payment(
                order_id=order.order_id,
                amount=order.final_amount,
                description=description,
                return_url=return_url,
            )

            # Persist Payment record
            payment, _ = Payment.objects.update_or_create(
                order=order,
                defaults={
                    "payment_id": f"PAY-{order.order_id}",
                    "user": order.user,
                    "payment_method": Payment.PaymentMethod.TEZCHECK,
                    "status": Payment.PaymentStatus.PENDING,
                    "amount": order.final_amount,
                    "provider_transaction_id": res.provider_transaction_id,
                    "payment_url": res.payment_url,
                    "raw_response": json.dumps(res.raw_response),
                    "idempotency_key": f"tezcheck_{res.provider_transaction_id or order.order_id}",
                },
            )

            ProviderTransaction.objects.create(
                provider=ProviderTransaction.ProviderName.TEZCHECK,
                action="CREATE_PAYMENT",
                reference_id=order.order_id,
                response_payload=json.dumps(res.raw_response),
                is_success=True,
            )
            return True, res.payment_url, ""
        except PaymentError as pe:
            logger.error(f"TezCheck payment initiation failed: {pe}")
            ProviderTransaction.objects.create(
                provider=ProviderTransaction.ProviderName.TEZCHECK,
                action="CREATE_PAYMENT",
                reference_id=order.order_id,
                is_success=False,
                error_message=str(pe),
            )
            return False, "", pe.message
        except Exception as e:
            logger.exception("Unexpected error creating TezCheck payment")
            return False, "", "To'lov tizimida nosozlik yuz berdi."

    @classmethod
    def process_tezcheck_webhook(
        cls, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Processes TezCheck payment notification with signature verification and strict idempotency.
        """
        provider = get_payment_provider("TEZCHECK")

        try:
            ver_res = provider.verify_webhook(payload, signature=signature)
        except InvalidWebhookError as e:
            logger.warning(f"TezCheck signature verification failed: {e}")
            ProviderTransaction.objects.create(
                provider=ProviderTransaction.ProviderName.TEZCHECK,
                action="VERIFY_WEBHOOK",
                request_payload=json.dumps(payload),
                is_success=False,
                error_message=str(e),
            )
            return False, "Invalid signature"

        order_id = ver_res.order_id
        if not order_id:
            return False, "Missing order_id in webhook"

        # Handle within atomic transaction with select_for_update
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(order__order_id=order_id, payment_method=Payment.PaymentMethod.TEZCHECK)
                .first()
            )

            if not payment:
                # If payment record doesn't exist yet, search order
                order = Order.objects.select_for_update().filter(order_id=order_id).first()
                if not order:
                    logger.error(f"Webhook received for unknown order: {order_id}")
                    return False, "Order not found"

                payment = Payment.objects.create(
                    payment_id=f"PAY-{order.order_id}",
                    user=order.user,
                    order=order,
                    payment_method=Payment.PaymentMethod.TEZCHECK,
                    status=Payment.PaymentStatus.PENDING,
                    amount=ver_res.amount or order.final_amount,
                    provider_transaction_id=ver_res.provider_transaction_id,
                    idempotency_key=f"tezcheck_{ver_res.provider_transaction_id or order_id}",
                )

            # Strict Idempotency Check: if already paid, safely return OK
            if payment.status == Payment.PaymentStatus.PAID:
                logger.info(f"Idempotency: Payment for order {order_id} already marked PAID. Ignoring duplicate.")
                return True, "Already processed"

            payment.provider_transaction_id = ver_res.provider_transaction_id
            payment.raw_response = json.dumps(payload)

            if ver_res.status == "PAID":
                payment.status = Payment.PaymentStatus.PAID
                payment.paid_at = timezone.now()
                payment.save(update_fields=["status", "paid_at", "provider_transaction_id", "raw_response", "updated_at"])

                # Trigger order paid flow
                OrderService.mark_order_paid(payment.order, provider_tx_id=ver_res.provider_transaction_id)
                logger.info(f"Payment marked PAID for order {order_id}")
            elif ver_res.status == "FAILED":
                payment.status = Payment.PaymentStatus.FAILED
                payment.save(update_fields=["status", "raw_response", "updated_at"])

            ProviderTransaction.objects.create(
                provider=ProviderTransaction.ProviderName.TEZCHECK,
                action="PROCESS_WEBHOOK",
                reference_id=order_id,
                request_payload=json.dumps(payload),
                is_success=True,
            )

        return True, "Success"

    @classmethod
    @transaction.atomic
    def create_manual_card_payment(
        cls,
        order: Order,
        screenshot=None,
        telegram_file_id: str = "",
    ) -> ManualPayment:
        """Create manual card payment record awaiting admin review."""
        settings_obj = BotSettings.load()

        payment, _ = Payment.objects.update_or_create(
            order=order,
            defaults={
                "payment_id": f"PAY-{order.order_id}",
                "user": order.user,
                "payment_method": Payment.PaymentMethod.MANUAL_CARD,
                "status": Payment.PaymentStatus.PENDING,
                "amount": order.final_amount,
            },
        )

        manual_entry, _ = ManualPayment.objects.update_or_create(
            payment=payment,
            defaults={
                "card_number": settings_obj.card_number,
                "card_owner": settings_obj.card_owner,
                "screenshot": screenshot,
                "telegram_file_id": telegram_file_id,
                "status": ManualPayment.ManualStatus.PENDING,
            },
        )

        # Notify admins about pending payment verification
        admin_alert = (
            f"🟡 <b>YANGI TO'LOV CHEKI (SKRINSHOT)!</b>\n\n"
            f"📦 Buyurtma: <code>{order.order_id}</code>\n"
            f"👤 Foydalanuvchi: {order.user.display_name} (ID: {order.user.telegram_id})\n"
            f"💰 Summa: <b>{order.final_amount:,.0f} UZS</b>\n"
            f"💳 Karta: {settings_obj.card_number} ({settings_obj.card_owner})\n"
            f"🎮 PUBG: {order.player_nickname} (ID: <code>{order.player_id}</code>)\n"
            f"💎 Paket: {order.product.name}\n\n"
            f"<i>Chekni tekshiring va tasdiqlang yoki rad eting.</i>"
        )
        transaction.on_commit(lambda: NotificationService.dispatch_admin_alert(admin_alert))
        return manual_entry

    @classmethod
    @transaction.atomic
    def admin_approve_manual_payment(cls, manual_payment_id: int, admin_identifier: str) -> Tuple[bool, str]:
        """Admin approves manual check screenshot."""
        manual_entry = (
            ManualPayment.objects.select_for_update()
            .filter(id=manual_payment_id)
            .select_related("payment", "payment__order")
            .first()
        )
        if not manual_entry:
            return False, "To'lov cheki topilmadi."

        if manual_entry.status == ManualPayment.ManualStatus.APPROVED:
            return False, "Ushbu to'lov allaqachon tasdiqlangan."

        manual_entry.status = ManualPayment.ManualStatus.APPROVED
        manual_entry.reviewed_by = admin_identifier
        manual_entry.reviewed_at = timezone.now()
        manual_entry.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        payment = manual_entry.payment
        payment.status = Payment.PaymentStatus.PAID
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at", "updated_at"])

        # Audit log
        AdminAction.objects.create(
            admin_identifier=admin_identifier,
            action_type=AdminAction.ActionType.APPROVE_PAYMENT,
            target_model="ManualPayment",
            target_id=str(manual_payment_id),
            details=f"Admin to'lovni tasdiqladi: {payment.payment_id}, summa: {payment.amount} UZS",
        )

        # Mark order paid & trigger delivery
        if payment.order:
            OrderService.mark_order_paid(payment.order)

        return True, "To'lov muvaffaqiyatli tasdiqlandi!"

    @classmethod
    @transaction.atomic
    def admin_reject_manual_payment(
        cls, manual_payment_id: int, admin_identifier: str, reason: str = ""
    ) -> Tuple[bool, str]:
        """Admin rejects manual check screenshot."""
        manual_entry = (
            ManualPayment.objects.select_for_update()
            .filter(id=manual_payment_id)
            .select_related("payment", "payment__order")
            .first()
        )
        if not manual_entry:
            return False, "To'lov cheki topilmadi."

        manual_entry.status = ManualPayment.ManualStatus.REJECTED
        manual_entry.reviewed_by = admin_identifier
        manual_entry.rejection_reason = reason
        manual_entry.reviewed_at = timezone.now()
        manual_entry.save(update_fields=["status", "reviewed_by", "rejection_reason", "reviewed_at"])

        payment = manual_entry.payment
        payment.status = Payment.PaymentStatus.FAILED
        payment.save(update_fields=["status", "updated_at"])

        AdminAction.objects.create(
            admin_identifier=admin_identifier,
            action_type=AdminAction.ActionType.REJECT_PAYMENT,
            target_model="ManualPayment",
            target_id=str(manual_payment_id),
            details=f"To'lov rad etildi. Sabab: {reason}",
        )

        if payment.order:
            payment.order.status = Order.Status.FAILED
            payment.order.error_message = f"To'lov rad etildi: {reason or 'Chek tasdiqlanmadi'}"
            payment.order.save(update_fields=["status", "error_message", "updated_at"])
            transaction.on_commit(lambda: NotificationService.dispatch_order_status_change(payment.order))

        return True, "To'lov rad etildi."
