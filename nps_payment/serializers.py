from rest_framework import serializers

from .models import NPSConfig, NPSTransaction


class NPSConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = NPSConfig
        fields = [
            "id",
            "merchant_id",
            "merchant_name",
            "api_username",
            "api_password",
            "secret_key",
            "is_sandbox",
            "is_enabled",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "api_password": {"write_only": True},
            "secret_key": {"write_only": True},
        }


class NPSInitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True)
    instrument_code = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    response_url = serializers.URLField(required=False, allow_blank=True)


class NPSServiceChargeQuerySerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    instrument_code = serializers.CharField(max_length=100)


class NPSTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NPSTransaction
        fields = "__all__"
