from django.contrib import admin
from unfold.admin import ModelAdmin

from tracking.models import RiderLocation, RiderLocationHistory


@admin.register(RiderLocation)
class RiderLocationAdmin(ModelAdmin):
    list_display = (
        "id",
        "rider",
        "latitude",
        "longitude",
        "is_online",
        "last_updated_at",
    )
    list_filter = ("is_online", "last_updated_at")
    search_fields = (
        "rider__username",
        "rider__first_name",
        "rider__last_name",
        "rider__phone_number",
    )
    ordering = ("-last_updated_at",)


@admin.register(RiderLocationHistory)
class RiderLocationHistoryAdmin(ModelAdmin):
    list_display = ("id", "rider", "latitude", "longitude", "created_at")
    list_filter = ("created_at",)
    search_fields = ("rider__username", "rider__phone_number")
    ordering = ("-created_at",)
