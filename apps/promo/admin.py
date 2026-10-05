from django.contrib import admin
from .models import PromoCode, PromoCodeUsage


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "max_uses",
        "used_count",
        "min_order_amount",
        "expires_at",
        "is_active",
    )
    list_filter = ("is_active", "discount_type", "expires_at")
    search_fields = ("code",)
    list_editable = ("is_active",)


@admin.register(PromoCodeUsage)
class PromoCodeUsageAdmin(admin.ModelAdmin):
    list_display = ("promo", "user", "order_id", "discount_amount", "used_at")
    search_fields = ("promo__code", "user__telegram_id", "order_id")
    readonly_fields = ("promo", "user", "order_id", "discount_amount", "used_at")
