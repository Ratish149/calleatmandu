from rest_framework import serializers

from customer.models import CustomerFollowUp


class CustomerOrderActivitySerializer(serializers.Serializer):
    """
    Serializer representing customer details, ordering metrics, and activity status.
    """

    id = serializers.CharField(
        help_text="Unique composite customer identifier (e.g., 'user-1' or 'guest-9801451245')."
    )
    customer_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="User ID if customer is registered, else null for guest checkout.",
    )
    customer_name = serializers.CharField(
        allow_blank=True,
        help_text="Customer display name extracted from orders or user profile.",
    )
    phone_number = serializers.CharField(
        allow_null=True,
        allow_blank=True,
        required=False,
        help_text="Cleaned customer contact phone number.",
    )
    email = serializers.EmailField(
        allow_null=True,
        required=False,
        help_text="Customer email if registered account exists.",
    )
    username = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Registered account username if applicable.",
    )
    customer_type = serializers.ChoiceField(
        choices=["registered", "guest"],
        help_text="Whether customer has an authenticated account ('registered') or ordered as guest ('guest').",
    )
    total_orders = serializers.IntegerField(
        help_text="Total number of non-cancelled orders placed by this customer."
    )
    orders_in_range = serializers.IntegerField(
        help_text="Number of orders placed within the specified date/time window."
    )
    reorder_count = serializers.IntegerField(
        help_text="Count of repeat orders after initial purchase (total_orders - 1)."
    )
    is_reorder = serializers.BooleanField(
        help_text="True if customer has placed more than one order."
    )
    first_order_date = serializers.DateTimeField(
        allow_null=True,
        required=False,
        help_text="Timestamp of the customer's first recorded order.",
    )
    last_order_date = serializers.DateTimeField(
        allow_null=True,
        required=False,
        help_text="Timestamp of the customer's most recent order.",
    )
    days_since_last_order = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="Calendar days elapsed since the customer's most recent order.",
    )
    total_spent = serializers.FloatField(
        help_text="Cumulative amount spent across non-cancelled orders."
    )
    is_active = serializers.BooleanField(
        help_text="True if customer ordered/reordered within the specified window (default 7 days)."
    )
    status = serializers.ChoiceField(
        choices=["active", "inactive"],
        help_text="'active' if ordered within window, 'inactive' if no orders in window.",
    )
    latest_followup_at = serializers.DateTimeField(
        allow_null=True,
        required=False,
        help_text="Timestamp of the most recent follow-up recorded for this customer. Null means never followed up.",
    )


class CustomerActivitySummarySerializer(serializers.Serializer):
    """
    Serializer representing aggregate metrics across all customers.
    """

    total_customers = serializers.IntegerField(
        help_text="Total distinct customers found in the Order table."
    )
    active_customers = serializers.IntegerField(
        help_text="Count of customers who ordered within the active window."
    )
    inactive_customers = serializers.IntegerField(
        help_text="Count of customers who have not ordered within the active window."
    )
    registered_customers = serializers.IntegerField(
        help_text="Count of customers with a registered User account."
    )
    guest_customers = serializers.IntegerField(
        help_text="Count of guest customers who ordered via phone without an account."
    )
    window_days = serializers.IntegerField(
        help_text="Number of days in the active window (default: 7)."
    )
    start_date = serializers.CharField(
        help_text="ISO start timestamp of the activity window."
    )
    end_date = serializers.CharField(
        help_text="ISO end timestamp of the activity window."
    )


class GroupedCustomerOrderActivitySerializer(serializers.Serializer):
    """
    Response serializer when clients request separated/grouped lists
    via query parameter `?grouped=true`.
    """

    summary = CustomerActivitySummarySerializer()
    active_customers = CustomerOrderActivitySerializer(many=True)
    inactive_customers = CustomerOrderActivitySerializer(many=True)


class CustomerFollowUpSerializer(serializers.ModelSerializer):
    """
    Serializer for creating, updating, and viewing customer follow-up records.
    Normalizes phone numbers and links customer identity.
    """

    user_username = serializers.CharField(
        source="user.username", read_only=True
    )
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True
    )

    class Meta:
        model = CustomerFollowUp
        fields = [
            "id",
            "phone_number",
            "customer_name",
            "user",
            "user_username",
            "notes",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def validate_phone_number(self, value):
        from customer.services.customer_followup_service import (
            CustomerFollowUpService,
        )

        return CustomerFollowUpService.clean_phone_number(value)

    def create(self, validated_data):
        from customer.services.customer_followup_service import (
            CustomerFollowUpService,
        )

        request = self.context.get("request")
        created_by = (
            getattr(request, "user", None)
            if request and request.user.is_authenticated
            else None
        )
        return CustomerFollowUpService.create_follow_up(
            validated_data, created_by=created_by
        )
