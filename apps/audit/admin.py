from django.contrib import admin
from .models import AdminAction


@admin.register(AdminAction)
class AdminActionAdmin(admin.ModelAdmin):
    list_display = ("admin_identifier", "action_type", "target_model", "target_id", "created_at")
    list_filter = ("action_type", "target_model", "created_at")
    search_fields = ("admin_identifier", "target_id", "details")
    readonly_fields = ("admin_identifier", "action_type", "target_model", "target_id", "details", "created_at")
