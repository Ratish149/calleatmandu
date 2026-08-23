from django.contrib import admin

from blog.models import Blog


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "slug", "time_to_read", "created_at"]
    search_fields = ["title", "short_description", "content"]
    prepopulated_fields = {"slug": ("title",)}
