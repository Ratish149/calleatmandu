from django.db.models import Q
import django_filters

from accounting.models import CashExpenditure


class CashExpenditureFilter(django_filters.FilterSet):
    """
    FilterSet for Cash & Expenditure records:
    - start_date / end_date: filter by transaction date range.
    - entry_type: filter by CASH_IN, EXPENDITURE, or BOTH.
    - payment_method: filter by PaymentMethod choices.
    - branch: filter by branch ID.
    - created_by: filter by staff user ID.
    - search: search across title, notes, and staff username.
    """

    start_date = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        help_text="Filter transactions starting from date (YYYY-MM-DD).",
    )
    end_date = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        help_text="Filter transactions up to date (YYYY-MM-DD).",
    )
    entry_type = django_filters.ChoiceFilter(
        choices=CashExpenditure.EntryType.choices,
        help_text="Filter by entry type (CASH_IN, EXPENDITURE, BOTH).",
    )
    payment_method = django_filters.ChoiceFilter(
        choices=CashExpenditure.PaymentMethod.choices,
        help_text="Filter by payment method.",
    )
    branch = django_filters.NumberFilter(
        field_name="branch_id",
        help_text="Filter transactions by branch ID.",
    )
    created_by = django_filters.NumberFilter(
        field_name="created_by_id",
        help_text="Filter transactions by the user who created the record.",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Search in title, notes, and staff username.",
    )

    class Meta:
        model = CashExpenditure
        fields = [
            "start_date",
            "end_date",
            "entry_type",
            "payment_method",
            "branch",
            "created_by",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            Q(title__icontains=val)
            | Q(notes__icontains=val)
            | Q(created_by__username__icontains=val)
        )
