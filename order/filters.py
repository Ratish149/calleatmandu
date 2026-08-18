from django_filters import rest_framework as filters

from order.models import Order


class OrderFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Order.OrderStatus.choices)
    branch = filters.NumberFilter(field_name="branch__id")
    customer_name = filters.CharFilter(lookup_expr="icontains")
    phone_number = filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Order
        fields = ["status", "branch", "customer_name", "phone_number"]
