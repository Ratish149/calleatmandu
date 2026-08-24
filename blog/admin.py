from django.contrib import admin
from unfold.admin import ModelAdmin

from blog.models import Blog


@admin.register(Blog)
class BlogAdmin(ModelAdmin):
    list_display = ["title", "slug", "time_to_read", "created_at"]
    search_fields = ["title", "short_description", "content"]
    prepopulated_fields = {"slug": ("title",)}
