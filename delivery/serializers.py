from decimal import Decimal

from rest_framework import serializers

from delivery.models import DeliveryPricing


class DeliveryPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPricing
        fields = [
            "id",
            "price_per_km",
            "minimum_charge",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_price_per_km(self, value):
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Price per kilometer cannot be negative.")
        return value

    def validate_minimum_charge(self, value):
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Minimum charge cannot be negative.")
        return value


class DeliveryEstimateRequestSerializer(serializers.Serializer):
    latitude = serializers.FloatField(
        required=True,
        min_value=-90.0,
        max_value=90.0,
        help_text="Customer delivery destination latitude.",
    )
    longitude = serializers.FloatField(
        required=True,
        min_value=-180.0,
        max_value=180.0,
        help_text="Customer delivery destination longitude.",
    )
    branch_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Optional fulfilling branch ID. Defaults to nearest branch if omitted.",
    )


class DeliveryEstimateResponseSerializer(serializers.Serializer):
    branch_id = serializers.IntegerField()
    branch_name = serializers.CharField()
    branch_address = serializers.CharField()
    branch_latitude = serializers.FloatField()
    branch_longitude = serializers.FloatField()
    distance_km = serializers.FloatField()
    duration_minutes = serializers.FloatField()
    delivery_charge = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_deliverable = serializers.BooleanField()
    routing_method = serializers.CharField()
    message = serializers.CharField()
