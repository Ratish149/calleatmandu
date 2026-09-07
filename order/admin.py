from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from order.models import Order, OrderItem, OrderItemExtra, OrderStatusHistory


class OrderItemExtraInline(TabularInline):
    model = OrderItemExtra
    extra = 0
    readonly_fields = ["extra_name", "additional_price"]


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "quantity", "unit_price", "extras_price", "subtotal"]


class OrderStatusHistoryInline(TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ["old_status", "status", "comment", "changed_by", "created_at"]


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = [
        "order_number",
        "customer_name",
        "phone_number",
        "branch",
        "payment_type",
        "is_paid",
        "status",
        "total_amount",
        "transaction_id",
        "barcode_number",
        "created_at",
    ]
    list_filter = ["status", "payment_type", "is_paid", "branch", "created_at"]
    search_fields = [
        "order_number",
        "transaction_id",
        "customer_name",
        "phone_number",
        "delivery_location",
    ]
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    ordering = ["-created_at"]


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(ModelAdmin):
    list_display = ["order", "old_status", "status", "comment", "changed_by", "created_at"]
    list_filter = ["status", "old_status", "created_at"]
    search_fields = ["order__order_number", "comment"]
    ordering = ["-created_at"]


@admin.register(OrderItem)
class OrderItemAdmin(ModelAdmin):
    list_display = [
        "order",
        "product",
        "quantity",
        "unit_price",
        "extras_price",
        "subtotal",
        "created_at",
    ]
    search_fields = ["order__order_number", "product__name"]
    inlines = [OrderItemExtraInline]
    ordering = ["-created_at"]


@admin.register(OrderItemExtra)
class OrderItemExtraAdmin(ModelAdmin):
    list_display = ["order_item", "extra_name", "additional_price", "created_at"]
    search_fields = ["extra_name", "order_item__order__order_number"]
    ordering = ["-created_at"]
