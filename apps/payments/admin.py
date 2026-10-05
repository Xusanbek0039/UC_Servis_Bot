from django.contrib import admin, messages
from .models import Payment, ManualPayment
from .services import PaymentService


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_id",
        "user",
        "order",
        "payment_method",
        "amount",
        "status",
        "provider_transaction_id",
        "created_at",
    )
    list_filter = ("payment_method", "status", "created_at")
    search_fields = ("payment_id", "order__order_id", "user__telegram_id", "user__username")
    readonly_fields = (
        "payment_id",
        "user",
        "order",
        "payment_method",
        "amount",
        "provider_transaction_id",
        "payment_url",
        "idempotency_key",
        "raw_response",
        "paid_at",
        "created_at",
        "updated_at",
    )


@admin.register(ManualPayment)
class ManualPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment",
        "get_amount",
        "card_number",
        "status",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("payment__payment_id", "payment__order__order_id", "payment__user__telegram_id", "reviewed_by")
    readonly_fields = ("payment", "card_number", "card_owner", "telegram_file_id", "reviewed_by", "reviewed_at", "created_at")
    actions = ["approve_payments", "reject_payments"]

    @admin.display(description="Summa (UZS)")
    def get_amount(self, obj):
        return f"{obj.payment.amount:,.0f} UZS"

    @admin.action(description="✅ Tanlangan to'lovlarni tasdiqlash")
    def approve_payments(self, request, queryset):
        success_count = 0
        for item in queryset:
            success, msg = PaymentService.admin_approve_manual_payment(
                manual_payment_id=item.id,
                admin_identifier=request.user.username or "django_admin",
            )
            if success:
                success_count += 1
            else:
                self.message_user(request, f"Xato (#{item.id}): {msg}", level=messages.ERROR)
        if success_count:
            self.message_user(request, f"{success_count} ta to'lov muvaffaqiyatli tasdiqlandi.", level=messages.SUCCESS)

    @admin.action(description="❌ Tanlangan to'lovlarni rad etish")
    def reject_payments(self, request, queryset):
        success_count = 0
        for item in queryset:
            success, msg = PaymentService.admin_reject_manual_payment(
                manual_payment_id=item.id,
                admin_identifier=request.user.username or "django_admin",
                reason="Admin panel orqali rad etildi",
            )
            if success:
                success_count += 1
        self.message_user(request, f"{success_count} ta to'lov rad etildi.", level=messages.WARNING)
