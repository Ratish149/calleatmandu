from datetime import timedelta

import django_filters
from django.utils import timezone

from order.models import Order


class SalesStatsFilter(django_filters.FilterSet):
    period = django_filters.ChoiceFilter(
        choices=[
            ("daily", "Current Month Daily"),
            ("weekly", "Weekly (Last 7 Days)"),
            ("monthly", "Monthly (Last 30 Days)"),
        ],
        method="filter_by_period",
        help_text="Preset period filter: 'daily' (current month), 'weekly' (last 7 days), 'monthly' (last 30 days).",
    )
    start_date = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="gte",
        help_text="Filter sales starting from date (YYYY-MM-DD).",
    )
    end_date = django_filters.DateFilter(
        field_name="created_at__date",
        lookup_expr="lte",
        help_text="Filter sales up to date (YYYY-MM-DD).",
    )

    class Meta:
        model = Order
        fields = ["period", "start_date", "end_date"]

    def filter_by_period(self, queryset, name, value):
        today = timezone.localtime(timezone.now()).date()
        if value == "daily":
            start = today.replace(day=1)
            return queryset.filter(
                created_at__date__gte=start, created_at__date__lte=today
            )
        elif value == "weekly":
            start = today - timedelta(days=6)
            return queryset.filter(
                created_at__date__gte=start, created_at__date__lte=today
            )
        elif value == "monthly":
            start = today - timedelta(days=29)
            return queryset.filter(
                created_at__date__gte=start, created_at__date__lte=today
            )
        return queryset

    @property
    def qs(self):
        parent_qs = super().qs
        data = self.data
        # If no explicit period or date filter is supplied, default to current month daily stats
        if not data.get("period") and not data.get("start_date") and not data.get("end_date"):
            today = timezone.localtime(timezone.now()).date()
            start = today.replace(day=1)
            return parent_qs.filter(
                created_at__date__gte=start, created_at__date__lte=today
            )
        return parent_qs


class PeakHoursFilter(SalesStatsFilter):
    """
    Filter for Peak Order Hours API.
    Defaults to this week's data (last 7 days) if no filter parameter is passed.
    """

    @property
    def qs(self):
        parent_qs = super(SalesStatsFilter, self).qs
        data = self.data
        # Default to this week's data (last 7 days) if no explicit filter parameters are supplied
        if not data.get("period") and not data.get("start_date") and not data.get("end_date"):
            today = timezone.localtime(timezone.now()).date()
            start = today - timedelta(days=6)
            return parent_qs.filter(
                created_at__date__gte=start, created_at__date__lte=today
            )
        return parent_qs
