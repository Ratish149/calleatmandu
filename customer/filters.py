from django.db.models import Q
from django_filters import rest_framework as filters

from customer.models import CustomerFollowUp
from order.models import Order


class CustomerOrderActivityFilter(filters.FilterSet):
    """
    FilterSet for customer order activity and engagement:
    - is_active / active: boolean filter (true: active, false: inactive).
    - status: 'active' (ordered/reordered within window) or 'inactive' (no orders in window).
    - customer_type: 'registered' (has account) or 'guest' (phone-only).
    - days: rolling activity window in days (default: 7).
    - start_date / end_date: custom date range boundaries.
    - search: search across customer name, phone number, username, or email.
    - branch: filter orders by branch ID.
    - is_reorder: boolean flag for repeat customers (total_orders > 1).
    - grouped: return grouped payload separating active and inactive customers.
    """

    is_active = filters.BooleanFilter(
        help_text="Filter whether customer is active (true) or inactive (false).",
    )
    active = filters.BooleanFilter(
        help_text="Alias for is_active (true: active, false: inactive).",
    )
    status = filters.ChoiceFilter(
        choices=(
            ("active", "Active (ordered within window)"),
            ("inactive", "Inactive (no orders within window)"),
        ),
        help_text="Filter by customer activity status.",
    )
    customer_type = filters.ChoiceFilter(
        choices=(
            ("registered", "Registered Account"),
            ("guest", "Guest (Phone-only)"),
            ("all", "All Customers"),
        ),
        help_text="Filter by customer registration type.",
    )
    days = filters.NumberFilter(
        help_text="Number of rolling days to evaluate activity (default: 7)."
    )
    start_date = filters.CharFilter(
        help_text="Activity window start date (YYYY-MM-DD or ISO timestamp)."
    )
    end_date = filters.CharFilter(
        help_text="Activity window end date (YYYY-MM-DD or ISO timestamp)."
    )
    search = filters.CharFilter(
        help_text="Search by customer name, phone number, username, or email."
    )
    branch = filters.NumberFilter(
        field_name="branch_id",
        help_text="Filter customer orders by branch ID.",
    )
    is_reorder = filters.BooleanFilter(
        help_text="Filter customers who have reordered (total_orders > 1)."
    )
    grouped = filters.BooleanFilter(
        help_text="If true, returns active and inactive customers grouped separately."
    )

    class Meta:
        model = Order
        fields = [
            "is_active",
            "active",
            "status",
            "customer_type",
            "days",
            "start_date",
            "end_date",
            "search",
            "branch",
            "is_reorder",
            "grouped",
        ]


class CustomerFollowUpFilter(filters.FilterSet):
    """
    FilterSet for customer follow-up records:
    - phone_number: search/filter by customer phone number.
    - branch: filter by branch ID.
    - created_by: filter by staff user ID.
    - start_date / end_date: filter by creation datetime.
    - search: search across phone_number, customer_name, notes, created_by username.
    """

    phone_number = filters.CharFilter(lookup_expr="icontains")
    branch = filters.NumberFilter(field_name="branch_id")
    created_by = filters.NumberFilter(field_name="created_by_id")
    start_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    end_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = CustomerFollowUp
        fields = [
            "phone_number",
            "branch",
            "created_by",
            "start_date",
            "end_date",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            Q(phone_number__icontains=val)
            | Q(customer_name__icontains=val)
            | Q(notes__icontains=val)
            | Q(created_by__username__icontains=val)
        )
