import django_filters
from django.db.models import Q

from accounting.models import CashExpenditure, Vendor, VendorTransaction


class CashExpenditureFilter(django_filters.FilterSet):
    """
    FilterSet for Cash & Expenditure records:
    - start_date / end_date: filter by transaction date range.
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


class VendorFilter(django_filters.FilterSet):
    """
    FilterSet for Vendor records:
    - branch: filter by branch ID.
    - search: search by vendor name or phone number.
    """

    branch = django_filters.NumberFilter(
        field_name="branch_id",
        help_text="Filter vendors by branch ID.",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Search by vendor name or phone number.",
    )

    class Meta:
        model = Vendor
        fields = ["branch", "search"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(Q(name__icontains=val) | Q(phone_number__icontains=val))


class VendorTransactionFilter(django_filters.FilterSet):
    """
    FilterSet for VendorTransaction records:
    - vendor: filter by vendor ID.
    - transaction_type: filter by BILL or PAYMENT.
    - payment_method: filter by payment method.
    - start_date / end_date: filter by transaction date range.
    - branch: filter by branch ID.
    - search: search by title or notes.
    """

    vendor = django_filters.NumberFilter(
        field_name="vendor_id",
        help_text="Filter transactions by vendor ID.",
    )
    transaction_type = django_filters.ChoiceFilter(
        choices=VendorTransaction.TransactionType.choices,
        help_text="Filter by transaction type: BILL (amount owed) or PAYMENT (amount paid).",
    )
    payment_method = django_filters.ChoiceFilter(
        choices=VendorTransaction.PaymentMethod.choices,
        help_text="Filter by payment method.",
    )
    start_date = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        help_text="Filter transactions from this date (YYYY-MM-DD).",
    )
    end_date = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        help_text="Filter transactions up to this date (YYYY-MM-DD).",
    )
    branch = django_filters.NumberFilter(
        field_name="branch_id",
        help_text="Filter transactions by branch ID.",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Search by transaction title or notes.",
    )

    class Meta:
        model = VendorTransaction
        fields = [
            "vendor",
            "transaction_type",
            "payment_method",
            "start_date",
            "end_date",
            "branch",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(Q(title__icontains=val) | Q(notes__icontains=val))


class VendorSummaryFilter(django_filters.FilterSet):
    """
    FilterSet for Vendor Financial Summary:
    - vendor: filter summary by specific vendor ID.
    - branch: filter summary by branch ID.
    - start_date / end_date: filter transactions by date range.
    - search: search by vendor name, phone number, title, or notes.
    """

    vendor = django_filters.NumberFilter(
        field_name="vendor_id",
        help_text="Filter summary for a specific vendor ID.",
    )
    branch = django_filters.NumberFilter(
        field_name="branch_id",
        help_text="Filter summary by branch ID.",
    )
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
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Search by vendor name, phone number, title, or notes.",
    )

    class Meta:
        model = VendorTransaction
        fields = ["vendor", "branch", "start_date", "end_date", "search"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            Q(vendor__name__icontains=val)
            | Q(vendor__phone_number__icontains=val)
            | Q(title__icontains=val)
            | Q(notes__icontains=val)
        )
