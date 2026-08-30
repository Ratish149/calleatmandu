from rest_framework import serializers

from account.serializers import BranchSerializer
from order.models import Order, OrderItem, OrderItemExtra

# ---------------------------------------------------------------------------
# Extras
# ---------------------------------------------------------------------------


class OrderItemExtraCreateSerializer(serializers.Serializer):
    """Used when submitting an order — reference the extra by its id."""

    extra_id = serializers.IntegerField()


class OrderItemExtraSerializer(serializers.ModelSerializer):
    """Read-only representation of a selected extra on an order item."""

    class Meta:
        model = OrderItemExtra
        fields = ["id", "extra", "extra_name", "additional_price"]


# ---------------------------------------------------------------------------
# Order Item
# ---------------------------------------------------------------------------


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    extras = OrderItemExtraCreateSerializer(many=True, required=False, default=list)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    selected_extras = OrderItemExtraSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "extras_price",
            "subtotal",
            "selected_extras",
        ]


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------


class OrderCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20)
    delivery_location = serializers.CharField(max_length=255)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    special_note = serializers.CharField(required=False, allow_blank=True)
    promo_code = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    items = OrderItemCreateSerializer(many=True, min_length=1)


class OrderResponseSerializer(serializers.ModelSerializer):
    """
    Dedicated response serializer returned when listing, retrieving, or creating orders.
    """

    items = OrderItemSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch = BranchSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number",
            "branch",
            "branch_name",
            "customer_name",
            "phone_number",
            "delivery_location",
            "total_amount",
            "discount_amount",
            "status",
            "items",
        ]


# Alias for backward compatibility if referenced elsewhere
OrderCreateResponseSerializer = OrderResponseSerializer


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "user",
            "branch",
            "branch_name",
            "customer_name",
            "phone_number",
            "delivery_location",
            "latitude",
            "longitude",
            "special_note",
            "subtotal",
            "discount_amount",
            "delivery_fee",
            "total_amount",
            "promo_code",
            "offer",
            "status",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "user",
            "branch",
            "subtotal",
            "discount_amount",
            "delivery_fee",
            "total_amount",
            "created_at",
            "updated_at",
        ]
