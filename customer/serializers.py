from rest_framework import serializers


class CustomerOrderActivitySerializer(serializers.Serializer):
    """
    Serializer representing customer details, ordering metrics, and activity status.
    """

    id = serializers.CharField(
        help_text="Unique composite customer identifier (e.g., 'user-1' or 'guest-9801451245')."
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
