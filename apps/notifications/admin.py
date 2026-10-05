from django.contrib import admin
from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "notification_type", "is_sent", "created_at")
    list_filter = ("notification_type", "is_sent", "created_at")
    search_fields = ("telegram_id", "text", "error_message")
    readonly_fields = ("user", "telegram_id", "notification_type", "text", "is_sent", "error_message", "created_at")
