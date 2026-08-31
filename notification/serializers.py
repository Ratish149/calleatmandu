from rest_framework import serializers

from order.models import Order, OrderItem


class OrderItemNotificationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "product_name",
            "quantity",
            "subtotal",
        ]


class OrderNotificationSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for WebSocket real-time order notifications.
    Includes customer details, order number, total amount, and concise item summaries.
    """

    items = OrderItemNotificationSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number",
            "customer_name",
            "phone_number",
            "delivery_location",
            "total_amount",
            "items",
            "created_at",
        ]
