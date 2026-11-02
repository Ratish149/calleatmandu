from django.contrib import admin

from customer.models import CustomerFollowUp


@admin.register(CustomerFollowUp)
class CustomerFollowUpAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "customer_name",
        "user",
        "created_by",
        "branch",
        "created_at",
    )
    list_filter = (
        "branch",
        "created_at",
    )
    search_fields = (
        "phone_number",
        "customer_name",
        "notes",
        "created_by__username",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
