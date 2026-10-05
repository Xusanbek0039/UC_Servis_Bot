from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "uc_amount",
        "price",
        "cost_price",
        "profit_display",
        "is_active",
        "sort_order",
        "provider",
        "delivery_method",
    )
    list_filter = ("is_active", "provider", "delivery_method")
    list_editable = ("price", "cost_price", "is_active", "sort_order")
    search_fields = ("name", "provider_product_id")
    ordering = ("sort_order", "uc_amount")

    @admin.display(description="Foyda (Profit)")
    def profit_display(self, obj):
        return f"{obj.profit:,.0f} UZS"
