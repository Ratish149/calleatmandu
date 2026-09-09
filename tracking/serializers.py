from rest_framework import serializers

from order.models import Order
from tracking.models import RiderLocation


class RiderLocationUpdateSerializer(serializers.Serializer):
    """
    Serializer for rider location updates via REST API or WebSocket payloads.
    """

    latitude = serializers.FloatField(
        min_value=-90.0,
        max_value=90.0,
        help_text="Current latitude (-90.0 to 90.0)",
    )
    longitude = serializers.FloatField(
        min_value=-180.0,
        max_value=180.0,
        help_text="Current longitude (-180.0 to 180.0)",
    )


class RiderToggleOnlineSerializer(serializers.Serializer):
    """
    Serializer to switch a rider's online/offline status.
    """

    is_online = serializers.BooleanField(help_text="True for online, False for offline")


class RiderLocationSerializer(serializers.ModelSerializer):
    """
    Standard serializer for RiderLocation model instance.
    """

    class Meta:
        model = RiderLocation
        fields = [
            "id",
            "latitude",
            "longitude",
            "is_online",
            "last_updated_at",
        ]


class AdminRiderTrackingSerializer(serializers.ModelSerializer):
    """
    Comprehensive rider tracking details tailored for the Admin map dashboard.
    """

    rider_id = serializers.IntegerField(source="rider.id", read_only=True)
    username = serializers.CharField(source="rider.username", read_only=True)
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.CharField(source="rider.phone_number", read_only=True)
    branch_id = serializers.IntegerField(source="rider.branch.id", read_only=True, allow_null=True)
    branch_name = serializers.CharField(source="rider.branch.name", read_only=True, allow_null=True)
    active_orders_count = serializers.SerializerMethodField()

    class Meta:
        model = RiderLocation
        fields = [
            "id",
            "rider_id",
            "username",
            "full_name",
            "phone_number",
            "branch_id",
            "branch_name",
            "latitude",
            "longitude",
            "is_online",
            "last_updated_at",
            "active_orders_count",
        ]

    def get_full_name(self, obj) -> str:
        rider = obj.rider
        full_name = f"{rider.first_name} {rider.last_name}".strip()
        return full_name or rider.username

    def get_active_orders_count(self, obj) -> int:
        return Order.objects.filter(
            assigned_to_rider=obj.rider,
            status__in=[Order.OrderStatus.PREPARING, Order.OrderStatus.OUT_FOR_DELIVERY],
        ).count()


class CustomerOrderTrackingSerializer(serializers.Serializer):
    """
    Serializer providing clean, secure order live tracking data for customers.
    """

    order_number = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    customer_name = serializers.CharField(read_only=True)
    delivery_location = serializers.CharField(read_only=True)
    delivery_latitude = serializers.FloatField(source="latitude", read_only=True)
    delivery_longitude = serializers.FloatField(source="longitude", read_only=True)

    branch = serializers.SerializerMethodField()
    rider = serializers.SerializerMethodField()

    def get_branch(self, obj) -> dict:
        if not obj.branch:
            return None
        return {
            "id": obj.branch.id,
            "name": obj.branch.name,
            "latitude": obj.branch.latitude,
            "longitude": obj.branch.longitude,
        }

    def get_rider(self, obj) -> dict:
        rider = obj.assigned_to_rider
        if not rider:
            return None

        location = getattr(rider, "location", None)
        full_name = f"{rider.first_name} {rider.last_name}".strip() or rider.username

        return {
            "id": rider.id,
            "name": full_name,
            "phone_number": rider.phone_number,
            "latitude": location.latitude if location else None,
            "longitude": location.longitude if location else None,
            "is_online": location.is_online if location else False,
            "last_updated_at": location.last_updated_at.isoformat() if location else None,
        }
