from django.contrib import admin
from unfold.admin import ModelAdmin

from faq.models import Faq


@admin.register(Faq)
class FaqAdmin(ModelAdmin):
    list_display = ["question", "created_at"]
    search_fields = ["question", "answer"]
