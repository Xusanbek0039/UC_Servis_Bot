from django.contrib import admin
from .models import TelegramUser, BalanceLedger, Player


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "display_name", "balance", "is_admin", "is_banned", "created_at")
    list_filter = ("is_admin", "is_banned", "created_at")
    search_fields = ("telegram_id", "username", "first_name", "last_name")
    readonly_fields = ("telegram_id", "created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(BalanceLedger)
class BalanceLedgerAdmin(admin.ModelAdmin):
    list_display = ("user", "transaction_type", "amount", "balance_before", "balance_after", "reference_id", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("user__telegram_id", "user__username", "reference_id")
    readonly_fields = ("user", "transaction_type", "amount", "balance_before", "balance_after", "description", "reference_id", "created_at")
    ordering = ("-created_at",)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("player_id", "nickname", "user", "region", "is_validated", "last_used_at")
    search_fields = ("player_id", "nickname", "user__telegram_id")
    list_filter = ("is_validated", "region")
