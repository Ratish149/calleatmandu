from django.contrib import admin
from unfold.admin import ModelAdmin

from accounting.models import CashExpenditure


@admin.register(CashExpenditure)
class CashExpenditureAdmin(ModelAdmin):
    list_display = (
        "date",
        "cash_amount",
        "online_amount",
        "delivery_charge",
        "available_balance",
        "branch",
        "created_by",
        "created_at",
    )
    list_filter = (
        "branch",
        "date",
        "created_at",
    )
    search_fields = (
        "notes",
        "created_by__username",
    )
    ordering = ("-date", "-created_at")
    readonly_fields = ("created_at", "updated_at", "available_balance", "net_amount")
