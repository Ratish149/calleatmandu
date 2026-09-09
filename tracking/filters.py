import django_filters
from django.db.models import Q

from tracking.models import RiderLocation


class RiderLocationFilter(django_filters.FilterSet):
    """
    Filter set for querying rider locations in the Admin API.
    """

    is_online = django_filters.BooleanFilter(field_name="is_online")
    branch = django_filters.NumberFilter(field_name="rider__branch__id")
    search = django_filters.CharFilter(method="filter_by_search")

    class Meta:
        model = RiderLocation
        fields = ["is_online", "branch", "search"]

    def filter_by_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(rider__username__icontains=value)
            | Q(rider__first_name__icontains=value)
            | Q(rider__last_name__icontains=value)
            | Q(rider__phone_number__icontains=value)
        )
