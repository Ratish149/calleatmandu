from django.db.models import Q
from django_filters import rest_framework as filters

from order.models import Order


class OrderFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Order.OrderStatus.choices)
    branch = filters.NumberFilter(field_name="branch__id")
    assigned_to_rider = filters.NumberFilter(field_name="assigned_to_rider__id")
    barcode_number = filters.CharFilter(lookup_expr="exact")
    customer_name = filters.CharFilter(lookup_expr="icontains")
    phone_number = filters.CharFilter(lookup_expr="icontains")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Order
        fields = [
            "status",
            "branch",
            "assigned_to_rider",
            "barcode_number",
            "customer_name",
            "phone_number",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(customer_name__icontains=value)
            | Q(phone_number__icontains=value)
            | Q(order_number__icontains=value)
            | Q(barcode_number__icontains=value)
        )
