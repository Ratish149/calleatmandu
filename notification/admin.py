from django.contrib import admin
from unfold.admin import ModelAdmin

from notification.models import Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = [
        "title",
        "notification_type",
        "is_read",
        "read_at",
        "created_at",
    ]
    list_filter = ["is_read", "notification_type", "created_at"]
    search_fields = ["title", "message"]
    readonly_fields = ["created_at", "updated_at", "read_at"]
    ordering = ["-created_at"]
