from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from product.models import Category, Product, ProductExtra, ProductImage, Subcategory


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "created_at", "updated_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["-created_at"]


@admin.register(Subcategory)
class SubcategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "category", "created_at", "updated_at"]
    list_filter = ["category"]
    search_fields = ["name", "slug", "category__name"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["-created_at"]


class ProductExtraInline(TabularInline):
    model = ProductExtra
    extra = 1


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = [
        "name",
        "price",
        "type",
        "category",
        "sub_category",
        "is_best_seller",
        "prepare_time",
        "created_at",
    ]
    list_filter = ["type", "is_best_seller", "category", "sub_category"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductExtraInline, ProductImageInline]
    ordering = ["-created_at"]


@admin.register(ProductExtra)
class ProductExtraAdmin(ModelAdmin):
    list_display = ["product", "name", "additional_price", "created_at"]
    list_filter = ["product__category"]
    search_fields = ["name", "product__name"]
    ordering = ["-created_at"]


@admin.register(ProductImage)
class ProductImageAdmin(ModelAdmin):
    list_display = ["product", "image", "created_at"]
    search_fields = ["product__name"]
    ordering = ["-created_at"]
