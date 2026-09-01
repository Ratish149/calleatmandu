from django_filters import rest_framework as django_filters

from .models import NPSTransaction


class NPSTransactionFilterSet(django_filters.FilterSet):
    merchant_txn_id = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(lookup_expr="iexact")
    start_date = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    end_date = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = NPSTransaction
        fields = ["merchant_txn_id", "status", "start_date", "end_date"]
