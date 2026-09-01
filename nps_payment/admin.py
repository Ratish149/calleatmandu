from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import NPSConfig, NPSTransaction


@admin.register(NPSConfig)
class NPSConfigAdmin(ModelAdmin):
    list_display = (
        "merchant_name",
        "merchant_id",
        "is_sandbox",
        "is_enabled",
        "created_at",
    )
    list_filter = ("is_sandbox", "is_enabled")
    search_fields = ("merchant_name", "merchant_id")


@admin.register(NPSTransaction)
class NPSTransactionAdmin(ModelAdmin):
    list_display = (
        "merchant_txn_id",
        "order",
        "amount",
        "service_charge",
        "status",
        "institution",
        "instrument",
        "created_at",
    )
    list_filter = ("status", "created_at", "institution")
    search_fields = ("merchant_txn_id", "gateway_txn_id", "process_id")
    readonly_fields = (
        "raw_response",
        "webhook_received_at",
        "created_at",
        "updated_at",
    )
