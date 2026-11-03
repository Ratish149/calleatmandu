from django.contrib import admin
from unfold.admin import ModelAdmin

from accounting.models import CashExpenditure


@admin.register(CashExpenditure)
class CashExpenditureAdmin(ModelAdmin):
    list_display = (
        "title",
        "date",
        "entry_type",
        "cash_amount",
        "expenditure_amount",
        "net_amount",
        "payment_method",
        "branch",
        "created_by",
        "created_at",
    )
    list_filter = (
        "entry_type",
        "payment_method",
        "branch",
        "date",
        "created_at",
    )
    search_fields = (
        "title",
        "notes",
        "created_by__username",
    )
    ordering = ("-date", "-created_at")
    readonly_fields = ("created_at", "updated_at", "net_amount")
