from django.db.models import Q
from django_filters import rest_framework as filters

from order.models import ActivityLog, Order


class OrderFilter(filters.FilterSet):
    status = filters.CharFilter(method="filter_status")
    order_status = filters.CharFilter(method="filter_status")
    payment_type = filters.ChoiceFilter(choices=Order.PaymentType.choices)
    order_type = filters.ChoiceFilter(choices=Order.OrderType.choices)
    is_paid = filters.BooleanFilter()
    branch = filters.NumberFilter(field_name="branch__id")
    search = filters.CharFilter(method="filter_search")
    is_pos_order = filters.BooleanFilter()
    only_save = filters.BooleanFilter(
        help_text="Filter by only_save flag. True = draft/unconfirmed orders only. False = confirmed orders only.",
    )
    start_date = filters.CharFilter(method="filter_start_date")
    end_date = filters.CharFilter(method="filter_end_date")

    class Meta:
        model = Order
        fields = [
            "status",
            "order_status",
            "payment_type",
            "order_type",
            "is_paid",
            "transaction_id",
            "branch",
            "assigned_to_rider",
            "barcode_number",
            "customer_name",
            "phone_number",
            "search",
            "is_pos_order",
            "only_save",
            "discount_type",
            "start_date",
            "end_date",
        ]

    def filter_status(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip().upper()
        valid_statuses = set(Order.OrderStatus.values)
        if val in valid_statuses:
            return queryset.filter(status=val)
        return queryset.filter(status=value)

    def filter_start_date(self, queryset, name, value):
        if not value:
            return queryset
        from django.utils.dateparse import parse_date, parse_datetime

        parsed_dt = parse_datetime(value)
        if parsed_dt:
            return queryset.filter(created_at__gte=parsed_dt)
        parsed_d = parse_date(value)
        if parsed_d:
            return queryset.filter(created_at__date__gte=parsed_d)
        return queryset.filter(created_at__gte=value)

    def filter_end_date(self, queryset, name, value):
        if not value:
            return queryset
        from django.utils.dateparse import parse_date, parse_datetime

        parsed_dt = parse_datetime(value)
        if parsed_dt:
            return queryset.filter(created_at__lte=parsed_dt)
        parsed_d = parse_date(value)
        if parsed_d:
            return queryset.filter(created_at__date__lte=parsed_d)
        return queryset.filter(created_at__lte=value)

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(customer_name__icontains=value)
            | Q(phone_number__icontains=value)
            | Q(order_number__icontains=value)
            | Q(barcode_number__icontains=value)
            | Q(transaction_id__icontains=value)
        )


class ActivityLogFilter(filters.FilterSet):
    action_type = filters.ChoiceFilter(choices=ActivityLog.ActionType.choices)
    entity_type = filters.ChoiceFilter(choices=ActivityLog.EntityType.choices)
    entity_name = filters.CharFilter(lookup_expr="iexact")
    record_id = filters.CharFilter(lookup_expr="exact")
    order = filters.NumberFilter(field_name="order__id")
    order_number = filters.CharFilter(
        field_name="order__order_number", lookup_expr="iexact"
    )
    user = filters.NumberFilter(field_name="user__id")
    username = filters.CharFilter(field_name="user__username", lookup_expr="icontains")
    start_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    end_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = ActivityLog
        fields = [
            "action_type",
            "entity_type",
            "entity_name",
            "record_id",
            "order",
            "order_number",
            "user",
            "username",
            "start_date",
            "end_date",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(description__icontains=value)
            | Q(record_repr__icontains=value)
            | Q(record_id__icontains=value)
            | Q(entity_name__icontains=value)
            | Q(order__order_number__icontains=value)
            | Q(user__username__icontains=value)
        )
