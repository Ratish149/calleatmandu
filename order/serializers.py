from rest_framework import serializers

from order.models import Order, OrderItem


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "subtotal",
        ]


class OrderCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20)
    delivery_location = serializers.CharField(max_length=255)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    special_note = serializers.CharField(required=False, allow_blank=True)
    promo_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items = OrderItemCreateSerializer(many=True, min_length=1)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
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
            "user",
            "branch",
            "subtotal",
            "discount_amount",
            "delivery_fee",
            "total_amount",
            "created_at",
            "updated_at",
        ]
