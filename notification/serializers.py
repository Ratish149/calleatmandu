from rest_framework import serializers

from notification.models import Notification
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


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model endpoints (list, retrieve, create).
    """

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "data",
            "is_read",
            "read_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "read_at"]


class MarkNotificationReadSerializer(serializers.Serializer):
    """
    Unified serializer that accepts single notification_id, multiple notification_ids,
    or mark_all flag to mark notifications as read.
    """

    notification_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Single notification ID to mark as read",
    )
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="List of notification IDs to mark as read",
    )
    mark_all = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Set to True to mark all notifications as read",
    )

    def validate(self, attrs):
        notification_id = attrs.get("notification_id")
        notification_ids = attrs.get("notification_ids")
        mark_all = attrs.get("mark_all")

        if not mark_all and notification_id is None and not notification_ids:
            raise serializers.ValidationError(
                "Must provide notification_id, notification_ids list, or mark_all=True."
            )

        return attrs
