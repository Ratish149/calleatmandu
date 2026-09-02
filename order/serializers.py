from django.contrib.auth import get_user_model
from rest_framework import serializers

from account.models import Branch
from account.serializers import BranchSerializer
from order.models import Order, OrderItem, OrderItemExtra

User = get_user_model()

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
    payment_type = serializers.ChoiceField(
        choices=Order.PaymentType.choices,
        default=Order.PaymentType.COD,
        required=False,
    )
    transaction_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    is_paid = serializers.BooleanField(required=False, default=False)
    items = OrderItemCreateSerializer(many=True, min_length=1)


class POSOrderCreateSerializer(serializers.Serializer):
    """
    Serializer to create an order via POS counter.
    Does not require customer_name, phone_number, delivery_location, latitude, or longitude.
    Optionally accepts a customer User instance (via user ID) to extract customer details.
    """

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        help_text="Optional customer User ID. Customer name & phone will be extracted from this user.",
    )
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
        help_text="Optional Branch ID. Defaults to staff user's assigned branch if omitted.",
    )
    special_note = serializers.CharField(required=False, allow_blank=True, default="")
    promo_code = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None
    )
    payment_type = serializers.ChoiceField(
        choices=Order.PaymentType.choices,
        default=Order.PaymentType.COD,
        required=False,
    )
    transaction_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    is_paid = serializers.BooleanField(required=False, default=False)
    items = OrderItemCreateSerializer(many=True, min_length=1)


class OrderResponseSerializer(serializers.ModelSerializer):
    """
    Dedicated response serializer returned when listing, retrieving, or creating orders.
    """

    items = OrderItemSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch = BranchSerializer(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    assigned_to_rider_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "order_number",
            "barcode_number",
            "branch",
            "branch_name",
            "customer_name",
            "phone_number",
            "delivery_location",
            "latitude",
            "longitude",
            "subtotal",
            "delivery_fee",
            "total_amount",
            "discount_amount",
            "payment_type",
            "transaction_id",
            "is_paid",
            "status",
            "is_pos_order",
            "created_by",
            "created_by_name",
            "assigned_to_rider",
            "assigned_to_rider_name",
            "items",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            full_name = obj.created_by.get_full_name().strip()
            return full_name if full_name else obj.created_by.username
        return None

    def get_assigned_to_rider_name(self, obj):
        if obj.assigned_to_rider:
            full_name = obj.assigned_to_rider.get_full_name().strip()
            return full_name if full_name else obj.assigned_to_rider.username
        return None


# Alias for backward compatibility if referenced elsewhere
OrderCreateResponseSerializer = OrderResponseSerializer


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    assigned_to_rider_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "barcode_number",
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
            "payment_type",
            "transaction_id",
            "is_paid",
            "is_pos_order",
            "status",
            "created_by",
            "created_by_name",
            "assigned_to_rider",
            "assigned_to_rider_name",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "barcode_number",
            "user",
            "branch",
            "subtotal",
            "discount_amount",
            "delivery_fee",
            "total_amount",
            "is_pos_order",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            full_name = obj.created_by.get_full_name().strip()
            return full_name if full_name else obj.created_by.username
        return None

    def get_assigned_to_rider_name(self, obj):
        if obj.assigned_to_rider:
            full_name = obj.assigned_to_rider.get_full_name().strip()
            return full_name if full_name else obj.assigned_to_rider.username
        return None


class AssignRiderSerializer(serializers.Serializer):
    """
    Unified serializer for assigning an order to a rider.
    Accepts either `barcode_number` or `order_number` to identify the order.
    Optionally accepts `rider` (User ID) if staff/admin is assigning a specific rider.
    If `rider` is omitted, the order is assigned to the requesting user.
    """

    barcode_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        help_text="Barcode number of the order.",
    )
    order_number = serializers.CharField(
        max_length=12,
        required=False,
        allow_blank=True,
        help_text="Order number (e.g. EAT_482931).",
    )
    rider = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="rider"),
        required=False,
        allow_null=True,
        help_text="Optional rider User ID. If omitted, assigns to requesting user.",
    )

    def validate(self, attrs):
        barcode_number = attrs.get("barcode_number")
        order_number = attrs.get("order_number")

        if not barcode_number and not order_number:
            raise serializers.ValidationError(
                "Either 'barcode_number' or 'order_number' must be provided."
            )
        return attrs


