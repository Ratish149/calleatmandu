import django_filters
from django.db import models

from notification.models import Notification


class NotificationFilter(django_filters.FilterSet):
    """
    FilterSet for filtering notifications by read status, type, date range, and search.
    """

    is_read = django_filters.BooleanFilter(field_name="is_read")
    notification_type = django_filters.CharFilter(
        field_name="notification_type", lookup_expr="iexact"
    )
    start_date = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    end_date = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Notification
        fields = ["is_read", "notification_type", "start_date", "end_date"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            models.Q(title__icontains=value) | models.Q(message__icontains=value)
        )
