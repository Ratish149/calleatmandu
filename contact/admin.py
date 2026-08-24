from django.contrib import admin
from unfold.admin import ModelAdmin

from contact.models import Contact


@admin.register(Contact)
class ContactAdmin(ModelAdmin):
    list_display = ["name", "email", "phone_number", "created_at"]
    search_fields = ["name", "email", "phone_number", "message"]
