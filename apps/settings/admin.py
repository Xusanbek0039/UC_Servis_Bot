from django.contrib import admin
from .models import BotSettings


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Bot Holati", {"fields": ("bot_active", "maintenance_mode")}),
        ("Buyurtma Cheklovlari", {"fields": ("min_order_amount", "max_order_amount", "default_delivery_mode", "default_payment_method")}),
        ("Karta Ma'lumotlari (Qo'lda to'lov)", {"fields": ("card_number", "card_owner", "bank_name")}),
        ("Aloqa va Kanallar", {"fields": ("support_username", "channel_username")}),
        ("Referral Sozlamalari", {"fields": ("referral_bonus", "referral_reward_on_first_order")}),
        ("Matnlar", {"fields": ("help_text", "about_text")}),
        ("Meta", {"fields": ("currency", "updated_at")}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Disallow adding multiple settings instances
        return not BotSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
