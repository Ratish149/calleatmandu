from django.db.models import Q
from django_filters import rest_framework as filters

from order.models import ActivityLog, Order


class OrderFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Order.OrderStatus.choices)
    payment_type = filters.ChoiceFilter(choices=Order.PaymentType.choices)
    order_type = filters.ChoiceFilter(choices=Order.OrderType.choices)
    is_paid = filters.BooleanFilter()
    transaction_id = filters.CharFilter(lookup_expr="exact")
    branch = filters.NumberFilter(field_name="branch__id")
    assigned_to_rider = filters.NumberFilter(field_name="assigned_to_rider__id")
    barcode_number = filters.CharFilter(lookup_expr="exact")
    customer_name = filters.CharFilter(lookup_expr="icontains")
    phone_number = filters.CharFilter(lookup_expr="icontains")
    search = filters.CharFilter(method="filter_search")
    is_pos_order = filters.BooleanFilter()

    class Meta:
        model = Order
        fields = [
            "status",
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
        ]

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
    order_number = filters.CharFilter(field_name="order__order_number", lookup_expr="iexact")
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
