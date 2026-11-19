from django.contrib import admin
from unfold.admin import ModelAdmin

from sms_management.models import SMSLog, SMSSettings


@admin.register(SMSSettings)
class SMSSettingsAdmin(ModelAdmin):
    list_display = (
        "branch",
        "is_enabled",
        "delay_minutes",
        "updated_at",
    )
    list_filter = ("is_enabled",)
    search_fields = ("branch__name", "message_template")
    raw_id_fields = ("branch",)
    fields = (
        "branch",
        "is_enabled",
        "delay_minutes",
        "message_template",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(SMSLog)
class SMSLogAdmin(ModelAdmin):
    list_display = (
        "phone_number",
        "status",
        "branch",
        "order",
        "job_id",
        "scheduled_at",
        "sent_at",
        "created_at",
    )
    list_filter = ("status", "branch")
    search_fields = (
        "phone_number",
        "job_id",
        "message",
        "order__order_number",
        "branch__name",
    )
    readonly_fields = (
        "job_id",
        "cost",
        "sent_at",
        "response_payload",
        "error_message",
        "created_at",
        "updated_at",
    )
    raw_id_fields = ("order", "branch", "created_by")
    ordering = ("-created_at",)
