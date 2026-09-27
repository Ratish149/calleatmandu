from django.contrib import admin
from unfold.admin import ModelAdmin

from delivery.models import DeliveryPricing


@admin.register(DeliveryPricing)
class DeliveryPricingAdmin(ModelAdmin):
    list_display = (
        "__str__",
        "price_per_km",
        "minimum_charge",
        "is_active",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        # Prevent adding multiple instances; only allow add if no record exists yet
        return not DeliveryPricing.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the singleton configuration
        return False
