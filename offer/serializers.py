from rest_framework import serializers

from offer.models import Offer, OfferRedemption, PromoCode


class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = [
            "id",
            "code",
            "description",
            "offer",
            "max_total_usage",
            "max_usage_per_user",
            "current_usage_count",
            "start_datetime",
            "end_datetime",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "current_usage_count", "created_at", "updated_at"]

    def validate_code(self, value):
        return value.upper().strip()


class OfferSerializer(serializers.ModelSerializer):
    promo_codes = PromoCodeSerializer(many=True, read_only=True)

    class Meta:
        model = Offer
        fields = [
            "id",
            "title",
            "description",
            "banner_image",
            "offer_type",
            "scope",
            "category",
            "subcategory",
            "products",
            "discount_percentage",
            "discount_amount",
            "max_discount_amount",
            "buy_product",
            "buy_quantity",
            "get_product",
            "get_quantity",
            "get_discount_percentage",
            "min_order_amount",
            "min_item_quantity",
            "max_total_usage",
            "max_usage_per_user",
            "current_usage_count",
            "start_datetime",
            "end_datetime",
            "start_time",
            "end_time",
            "is_active",
            "promo_codes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "current_usage_count", "created_at", "updated_at"]

    def validate(self, attrs):
        offer_type = attrs.get("offer_type", getattr(self.instance, "offer_type", None))
        if offer_type == Offer.OfferType.PERCENTAGE:
            discount_pct = attrs.get(
                "discount_percentage",
                getattr(self.instance, "discount_percentage", 0.0),
            )
            if discount_pct <= 0 or discount_pct > 100:
                raise serializers.ValidationError({
                    "discount_percentage": "Discount percentage must be between 0 and 100."
                })

        if offer_type == Offer.OfferType.FLAT:
            discount_amt = attrs.get(
                "discount_amount", getattr(self.instance, "discount_amount", 0.0)
            )
            if discount_amt <= 0:
                raise serializers.ValidationError({
                    "discount_amount": "Discount amount must be greater than 0."
                })

        return attrs


class CartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    category_id = serializers.IntegerField(required=False, allow_null=True)
    subcategory_id = serializers.IntegerField(required=False, allow_null=True)
    price = serializers.FloatField(min_value=0.0)
    quantity = serializers.IntegerField(min_value=1)


class OfferCheckSerializer(serializers.Serializer):
    promo_code = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    cart_total = serializers.FloatField(min_value=0.0)
    cart_items = CartItemSerializer(many=True, required=False, default=list)


class OfferRedemptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferRedemption
        fields = [
            "id",
            "offer",
            "promo_code",
            "user",
            "order_id",
            "discount_applied",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]
