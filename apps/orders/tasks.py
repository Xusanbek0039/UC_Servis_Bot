import logging
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from .models import Order
from .services import OrderService

logger = logging.getLogger("apps.orders.tasks")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 min default
)
def process_topup_delivery_task(self, order_id: str):
    """
    Background worker task to deliver PUBG UC.
    Automatically retries on transient errors with backoff: 1m, 5m, 15m.
    """
    logger.info(f"Executing topup delivery task for order {order_id} (Attempt {self.request.retries + 1})")

    success = OrderService.execute_topup_delivery(order_id)
    if not success:
        # Retry with exponential backoff: 1m -> 5m -> 15m
        retry_delays = [60, 300, 900]
        delay = retry_delays[min(self.request.retries, len(retry_delays) - 1)]
        logger.warning(f"Delivery failed for {order_id}. Scheduling retry in {delay}s...")
        raise self.retry(countdown=delay)

    return f"Order {order_id} delivered successfully."


@shared_task
def cancel_expired_orders():
    """Cancel pending orders that were not paid within 1 hour."""
    cutoff = timezone.now() - timedelta(minutes=60)
    expired_orders = Order.objects.filter(
        status=Order.Status.WAITING_PAYMENT,
        created_at__lt=cutoff,
    )
    count = 0
    for order in expired_orders:
        OrderService.cancel_order(order.order_id, reason="To'lov muddati tugadi (Avtomatik bekor qilindi)", refund=False)
        count += 1
    logger.info(f"Cancelled {count} expired unpaid orders.")
    return count


@shared_task
def retry_failed_topups():
    """Find orders stuck in PROCESSING and retry delivery."""
    pending_topups = Order.objects.filter(
        status=Order.Status.PROCESSING,
        retry_count__lt=3,
    )
    for order in pending_topups:
        process_topup_delivery_task.delay(order.order_id)
    return pending_topups.count()
