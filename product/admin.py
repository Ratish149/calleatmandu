from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from product.models import (
    Category,
    KitchenInventoryItem,
    KitchenInventoryLog,
    Product,
    ProductExtra,
    ProductImage,
    Subcategory,
)


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
        "cost_price",
        "stock",
        "type",
        "category",
        "sub_category",
        "is_best_seller",
        "prepare_time",
        "created_at",
    ]
    list_editable = ["cost_price"]
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


# ---------------------------------------------------------------------------
# Kitchen Inventory Admin
# ---------------------------------------------------------------------------


class KitchenInventoryLogInline(TabularInline):
    model = KitchenInventoryLog
    extra = 0
    readonly_fields = [
        "consumed_quantity",
        "received_quantity",
        "net_change",
        "updated_by",
        "date",
        "notes",
    ]
    fields = [
        "date",
        "received_quantity",
        "consumed_quantity",
        "net_change",
        "updated_by",
        "notes",
    ]
    ordering = ["-date"]
    can_delete = False

    def net_change(self, obj):
        return obj.net_change

    net_change.short_description = "Net Change"


@admin.register(KitchenInventoryItem)
class KitchenInventoryItemAdmin(ModelAdmin):
    list_display = [
        "name",
        "unit",
        "total_quantity",
        "benchmark_quantity",
        "is_below_benchmark",
        "created_at",
        "updated_at",
    ]
    list_filter = ["unit"]
    search_fields = ["name"]
    ordering = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [KitchenInventoryLogInline]

    @admin.display(boolean=True, description="Below Benchmark?")
    def is_below_benchmark(self, obj):
        return obj.is_below_benchmark


@admin.register(KitchenInventoryLog)
class KitchenInventoryLogAdmin(ModelAdmin):
    list_display = [
        "item",
        "date",
        "received_quantity",
        "consumed_quantity",
        "net_change",
        "updated_by",
        "created_at",
    ]
    list_filter = ["date", "item"]
    search_fields = ["item__name", "notes", "updated_by__username"]
    ordering = ["-date", "item__name"]
    readonly_fields = ["net_change", "updated_by", "created_at", "updated_at"]
    autocomplete_fields = ["item"]

    @admin.display(description="Net Change")
    def net_change(self, obj):
        return obj.net_change
