import logging
from decimal import Decimal
from typing import Optional, Tuple
from django.db import transaction
from django.utils import timezone
from .models import Order
from apps.users.models import TelegramUser, BalanceLedger
from apps.users.services import UserService
from apps.products.models import Product
from apps.promo.models import PromoCode
from apps.promo.services import PromoService
from apps.settings.models import BotSettings
from apps.referrals.services import ReferralService
from apps.audit.models import AdminAction
from apps.notifications.services import NotificationService
from providers.factory import get_topup_provider
from providers.base import TopupDeliveryResult, DeliveryError

logger = logging.getLogger("apps.orders")


class OrderService:
    @classmethod
    @transaction.atomic
    def create_order(
        cls,
        user: TelegramUser,
        product: Product,
        player_id: str,
        player_nickname: str,
        payment_method: str,
        promo_code_str: Optional[str] = None,
    ) -> Order:
        """Create a new order with unique sequential order number."""
        order_id = Order.generate_order_id()
        amount = product.price
        discount_amount = Decimal("0.00")
        applied_promo = None

        if promo_code_str:
            applied_promo, discount_amount, _ = PromoService.validate_promo(
                code=promo_code_str,
                order_amount=amount,
                user=user,
            )

        final_amount = max(Decimal("0.00"), amount - discount_amount)

        order = Order.objects.create(
            order_id=order_id,
            user=user,
            player_id=player_id,
            player_nickname=player_nickname,
            product=product,
            amount=amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            promo_code=applied_promo,
            payment_method=payment_method,
            status=Order.Status.WAITING_PAYMENT,
            provider=product.provider,
            idempotency_key=f"order_{order_id}",
        )

        logger.info(f"Order created: {order.order_id} for user {user.telegram_id}, total: {final_amount} UZS")
        return order

    @classmethod
    @transaction.atomic
    def pay_with_balance(cls, order: Order) -> Tuple[bool, str]:
        """Pay order directly from user's internal balance."""
        user = order.user

        if user.balance < order.final_amount:
            return False, f"Balansingizda yetarli mablag' mavjud emas. Balans: {user.balance:,.0f} UZS"

        # Deduct from balance atomically
        UserService.update_balance(
            user=user,
            amount=-order.final_amount,
            transaction_type=BalanceLedger.TransactionType.ORDER_PAYMENT,
            description=f"Buyurtma to'lovi ({order.order_id}) - {order.product.name}",
            reference_id=order.order_id,
        )

        cls.mark_order_paid(order)
        return True, "To'lov balansingizdan muvaffaqiyatli yechildi!"

    @classmethod
    @transaction.atomic
    def mark_order_paid(cls, order: Order, provider_tx_id: str = "") -> None:
        """
        Mark order as PAID and trigger UC delivery.
        Guarantees idempotency via atomic row lock.
        """
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        # Idempotency guard: if already paid or further along, return
        if locked_order.is_paid and locked_order.status != Order.Status.WAITING_PAYMENT:
            logger.warning(f"Order {order.order_id} is already in paid/processing state: {locked_order.status}")
            return

        locked_order.status = Order.Status.PAID
        locked_order.save(update_fields=["status", "updated_at"])

        # Record promo code usage if applicable
        if locked_order.promo_code:
            PromoService.record_usage(
                promo=locked_order.promo_code,
                user=locked_order.user,
                order_id=locked_order.order_id,
                discount_amount=locked_order.discount_amount,
            )

        # Determine delivery route
        bot_settings = BotSettings.load()
        delivery_mode = bot_settings.default_delivery_mode

        # If product is set to MANUAL or global setting is MANUAL
        if (
            delivery_mode == BotSettings.DeliveryMode.MANUAL
            or locked_order.product.delivery_method == Product.DeliveryMethod.MANUAL
            or locked_order.provider == Order.ProviderChoice.MANUAL
        ):
            locked_order.status = Order.Status.MANUAL_REVIEW
            locked_order.save(update_fields=["status", "updated_at"])
            # Notify admins of pending manual delivery
            admin_msg = (
                f"🚨 <b>YANGI MANUAL BUYURTMA!</b>\n\n"
                f"📦 Buyurtma: <code>{locked_order.order_id}</code>\n"
                f"👤 Foydalanuvchi: {locked_order.user.display_name} (ID: {locked_order.user.telegram_id})\n"
                f"🆔 Player ID: <code>{locked_order.player_id}</code>\n"
                f"🎮 Player Nickname: <b>{locked_order.player_nickname}</b>\n"
                f"💎 Paket: <b>{locked_order.product.name}</b>\n"
                f"💰 Summa: {locked_order.final_amount:,.0f} UZS\n"
                f"💳 To'lov turi: {locked_order.payment_method}\n\n"
                f"<i>Iltimos, PUBG akkauntiga UC yuboring va quyidagi tugma orqali tasdiqlang.</i>"
            )
            transaction.on_commit(lambda: NotificationService.notify_admins(admin_msg))
            transaction.on_commit(lambda: NotificationService.notify_order_status_change(locked_order))
        else:
            # AUTO delivery route: trigger celery or sync deliver
            locked_order.status = Order.Status.PROCESSING
            locked_order.save(update_fields=["status", "updated_at"])
            transaction.on_commit(lambda: cls._dispatch_auto_delivery(locked_order.order_id))

    @classmethod
    def _dispatch_auto_delivery(cls, order_id: str):
        """Dispatches automated delivery via Celery or directly."""
        try:
            from apps.orders.tasks import process_topup_delivery_task
            process_topup_delivery_task.delay(order_id)
        except Exception:
            # Fallback to direct synchronous execution if Celery broker is offline
            cls.execute_topup_delivery(order_id)

    @classmethod
    def execute_topup_delivery(cls, order_id: str) -> bool:
        """
        Delivers UC via the configured TopupProvider (Midasbuy or Mock).
        Protected by database row lock.
        """
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(order_id=order_id).first()
            if not order:
                logger.error(f"Order not found for delivery: {order_id}")
                return False

            if order.status == Order.Status.COMPLETED:
                logger.info(f"Order {order_id} already COMPLETED. Skipping duplicate delivery.")
                return True

            order.status = Order.Status.DELIVERING
            order.save(update_fields=["status", "updated_at"])

        # Fetch provider outside lock to avoid prolonged DB row hold
        provider = get_topup_provider(order.provider)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            delivery_res: TopupDeliveryResult = loop.run_until_complete(
                provider.deliver(
                    order_id=order.order_id,
                    player_id=order.player_id,
                    uc_amount=order.product.uc_amount,
                    provider_product_id=order.product.provider_product_id,
                )
            )
            loop.close()
        except Exception as exc:
            logger.exception(f"Exception during provider delivery for {order_id}")
            delivery_res = TopupDeliveryResult(
                is_success=False,
                provider_order_id="",
                status="FAILED",
                error_message=str(exc),
            )

        with transaction.atomic():
            order = Order.objects.select_for_update().get(order_id=order_id)

            if delivery_res.is_success:
                order.status = Order.Status.COMPLETED
                order.provider_order_id = delivery_res.provider_order_id
                order.completed_at = timezone.now()
                order.save(update_fields=["status", "provider_order_id", "completed_at", "updated_at"])

                # Trigger referral reward if applicable
                ReferralService.process_referral_reward_for_order(order)
                # Send celebratory receipt
                transaction.on_commit(lambda: NotificationService.notify_order_status_change(order))
                return True
            else:
                order.retry_count += 1
                order.error_message = delivery_res.error_message or "Provider delivery failed"
                if order.retry_count >= 3:
                    order.status = Order.Status.MANUAL_REVIEW
                    order.save(update_fields=["status", "retry_count", "error_message", "updated_at"])
                    # Alert admin that auto-delivery failed 3 times
                    fail_msg = (
                        f"⚠️ <b>AUTO YETKAZISHDA XATOLIK!</b>\n"
                        f"Buyurtma: <code>{order.order_id}</code>\n"
                        f"Xatolik: {order.error_message}\n"
                        f"Status: MANUAL_REVIEW ga o'tkazildi."
                    )
                    transaction.on_commit(lambda: NotificationService.notify_admins(fail_msg))
                else:
                    order.status = Order.Status.PROCESSING
                    order.save(update_fields=["status", "retry_count", "error_message", "updated_at"])

                transaction.on_commit(lambda: NotificationService.notify_order_status_change(order))
                return False

    @classmethod
    @transaction.atomic
    def manual_deliver(cls, order_id: str, admin_identifier: str) -> Tuple[bool, str]:
        """Admin marks order manually delivered."""
        order = Order.objects.select_for_update().filter(order_id=order_id).first()
        if not order:
            return False, "Buyurtma topilmadi."

        if order.status == Order.Status.COMPLETED:
            return False, "Ushbu buyurtma allaqachon yakunlangan."

        order.status = Order.Status.COMPLETED
        order.completed_at = timezone.now()
        order.save(update_fields=["status", "completed_at", "updated_at"])

        AdminAction.objects.create(
            admin_identifier=admin_identifier,
            action_type=AdminAction.ActionType.COMPLETE_ORDER,
            target_model="Order",
            target_id=order_id,
            details=f"Admin tomonidan UC yuborildi deb tasdiqlandi. ({order.product.name} -> {order.player_id})",
        )

        ReferralService.process_referral_reward_for_order(order)
        transaction.on_commit(lambda: NotificationService.notify_order_status_change(order))
        return True, "Buyurtma muvaffaqiyatli yakunlandi va foydalanuvchiga xabar yuborildi!"

    @classmethod
    @transaction.atomic
    def cancel_order(
        cls, order_id: str, reason: str, admin_identifier: Optional[str] = None, refund: bool = True
    ) -> Tuple[bool, str]:
        """Cancel order and optionally refund paid amount back to user's balance."""
        order = Order.objects.select_for_update().filter(order_id=order_id).first()
        if not order:
            return False, "Buyurtma topilmadi."

        if order.status == Order.Status.COMPLETED:
            return False, "Yakunlangan buyurtmani bekor qilib bo'lmaydi."

        was_paid = order.is_paid
        order.status = Order.Status.CANCELLED
        order.error_message = reason
        order.save(update_fields=["status", "error_message", "updated_at"])

        if was_paid and refund and order.final_amount > Decimal("0.00"):
            UserService.update_balance(
                user=order.user,
                amount=order.final_amount,
                transaction_type=BalanceLedger.TransactionType.ORDER_REFUND,
                description=f"Bekor qilingan buyurtma uchun pul qaytarildi ({order.order_id})",
                reference_id=order.order_id,
            )

        if admin_identifier:
            AdminAction.objects.create(
                admin_identifier=admin_identifier,
                action_type=AdminAction.ActionType.CANCEL_ORDER,
                target_model="Order",
                target_id=order_id,
                details=f"Buyurtma bekor qilindi. Sabab: {reason}. Refund: {refund}",
            )

        transaction.on_commit(lambda: NotificationService.notify_order_status_change(order))
        return True, "Buyurtma bekor qilindi."
