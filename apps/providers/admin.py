from django.contrib import admin
from .models import ProviderTransaction


@admin.register(ProviderTransaction)
class ProviderTransactionAdmin(admin.ModelAdmin):
    list_display = ("provider", "action", "reference_id", "status_code", "is_success", "created_at")
    list_filter = ("provider", "action", "is_success", "created_at")
    search_fields = ("reference_id", "request_payload", "response_payload", "error_message")
    readonly_fields = (
        "provider",
        "action",
        "reference_id",
        "request_payload",
        "response_payload",
        "status_code",
        "is_success",
        "error_message",
        "created_at",
    )
