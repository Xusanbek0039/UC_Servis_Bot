from decimal import Decimal
from django.contrib import admin, messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from .models import Order
from .services import OrderService


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "get_user_display",
        "player_id",
        "player_nickname",
        "product",
        "final_amount",
        "payment_method",
        "status",
        "provider",
        "created_at",
    )
    list_filter = ("status", "payment_method", "created_at", "product", "provider")
    search_fields = (
        "order_id",
        "user__telegram_id",
        "user__username",
        "user__first_name",
        "player_id",
        "player_nickname",
    )
    readonly_fields = (
        "order_id",
        "user",
        "player_id",
        "player_nickname",
        "product",
        "amount",
        "discount_amount",
        "final_amount",
        "promo_code",
        "payment_method",
        "provider_order_id",
        "retry_count",
        "idempotency_key",
        "created_at",
        "updated_at",
        "completed_at",
    )
    ordering = ("-created_at",)
    actions = ["mark_delivered_action", "retry_delivery_action", "cancel_order_action"]

    @admin.display(description="Foydalanuvchi")
    def get_user_display(self, obj):
        return obj.user.display_name

    def changelist_view(self, request, extra_context=None):
        """Inject dashboard metrics at top of changelist."""
        extra_context = extra_context or {}
        today = timezone.now().date()

        today_orders_qs = Order.objects.filter(created_at__date=today)
        all_completed = Order.objects.filter(status=Order.Status.COMPLETED)

        today_revenue = (
            today_orders_qs.filter(status=Order.Status.COMPLETED).aggregate(s=Sum("final_amount"))["s"]
            or Decimal("0.00")
        )
        total_revenue = all_completed.aggregate(s=Sum("final_amount"))["s"] or Decimal("0.00")

        # Total estimated profit
        total_profit = (
            all_completed.aggregate(
                profit=Sum(models_expr := (Order.objects.filter(status=Order.Status.COMPLETED).annotate(
                    p=models.F("final_amount") - models.F("product__cost_price")
                ).values("p")))
            ) if False else Decimal("0.00")
        )
        # Calculate profit cleanly
        total_profit_val = Decimal("0.00")
        for ord_item in all_completed.select_related("product"):
            total_profit_val += max(Decimal("0.00"), ord_item.final_amount - ord_item.product.cost_price)

        extra_context["stats"] = {
            "today_revenue": today_revenue,
            "today_orders": today_orders_qs.count(),
            "successful_orders": all_completed.count(),
            "pending_payments": Order.objects.filter(status=Order.Status.WAITING_PAYMENT).count(),
            "manual_orders": Order.objects.filter(status__in=[Order.Status.MANUAL_REVIEW, Order.Status.PROCESSING]).count(),
            "failed_orders": Order.objects.filter(status=Order.Status.FAILED).count(),
            "total_revenue": total_revenue,
            "total_profit": total_profit_val,
        }

        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description="🎮 UC Yuborildi deb tasdiqlash (COMPLETED)")
    def mark_delivered_action(self, request, queryset):
        success_count = 0
        for order in queryset:
            success, msg = OrderService.manual_deliver(
                order_id=order.order_id,
                admin_identifier=request.user.username or "django_admin",
            )
            if success:
                success_count += 1
            else:
                self.message_user(request, f"{order.order_id}: {msg}", level=messages.ERROR)
        if success_count:
            self.message_user(request, f"{success_count} ta buyurtma yetkazildi deb belgilandi.", level=messages.SUCCESS)

    @admin.action(description="🔄 Qayta yetkazish (Retry Delivery)")
    def retry_delivery_action(self, request, queryset):
        success_count = 0
        for order in queryset:
            if OrderService.execute_topup_delivery(order.order_id):
                success_count += 1
        self.message_user(request, f"{success_count} ta buyurtma qayta yetkazildi.", level=messages.INFO)

    @admin.action(description="❌ Bekor qilish va to'lovni qaytarish (Refund)")
    def cancel_order_action(self, request, queryset):
        success_count = 0
        for order in queryset:
            success, msg = OrderService.cancel_order(
                order_id=order.order_id,
                reason="Admin panel orqali bekor qilindi",
                admin_identifier=request.user.username or "django_admin",
                refund=True,
            )
            if success:
                success_count += 1
        self.message_user(request, f"{success_count} ta buyurtma bekor qilindi.", level=messages.WARNING)
