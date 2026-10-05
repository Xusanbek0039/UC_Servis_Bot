from django.contrib import admin
from .models import ReferralRelationship, ReferralReward


@admin.register(ReferralRelationship)
class ReferralRelationshipAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referred_user", "is_active", "created_at")
    search_fields = ("referrer__telegram_id", "referrer__username", "referred_user__telegram_id", "referred_user__username")
    list_filter = ("is_active", "created_at")


@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referred_user", "bonus_amount", "order_id", "is_paid", "created_at")
    search_fields = ("referrer__telegram_id", "referred_user__telegram_id", "order_id")
    list_filter = ("is_paid", "created_at")
