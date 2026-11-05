from django.contrib import admin
from unfold.admin import ModelAdmin

from stats.models import BillPrintConfig


@admin.register(BillPrintConfig)
class BillPrintConfigAdmin(ModelAdmin):
    list_display = ["bill_title", "branch"]
    list_select_related = ["branch"]
