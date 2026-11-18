import django_filters
from django.db.models import Q

from accounting.models import (
    CashExpenditure,
    CreditEntry,
    CreditOwner,
    Vendor,
    VendorTransaction,
)


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
    credit_owner = django_filters.NumberFilter(
        field_name="credit_entry__credit_owner_id",
        help_text="Filter transactions by credit owner ID.",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Search in notes, credit owner name, and staff username.",
    )

    class Meta:
        model = CashExpenditure
        fields = [
            "start_date",
            "end_date",
            "branch",
            "created_by",
            "credit_owner",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            Q(notes__icontains=val)
            | Q(created_by__username__icontains=val)
            | Q(credit_entry__credit_owner__name__icontains=val)
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
    - receipt_type: filter by VAT or NON_VAT receipt.
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
    receipt_type = django_filters.ChoiceFilter(
        choices=VendorTransaction.ReceiptType.choices,
        help_text="Filter by receipt type: VAT or NON_VAT.",
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
            "receipt_type",
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
    - receipt_type: filter by VAT or NON_VAT receipt.
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
    receipt_type = django_filters.ChoiceFilter(
        choices=VendorTransaction.ReceiptType.choices,
        help_text="Filter by receipt type: VAT or NON_VAT.",
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
        fields = [
            "vendor",
            "branch",
            "receipt_type",
            "start_date",
            "end_date",
            "search",
        ]

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


class CreditOwnerFilter(django_filters.FilterSet):
    """
    FilterSet for CreditOwner records:
    - branch: filter by branch ID.
    - search: search by name, phone_number, address, notes.
    """

    branch = django_filters.NumberFilter(
        field_name="branch_id",
        help_text="Filter credit owners by branch ID.",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Search by name, phone number, address, or notes.",
    )

    class Meta:
        model = CreditOwner
        fields = ["branch", "search"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            Q(name__icontains=val)
            | Q(phone_number__icontains=val)
            | Q(address__icontains=val)
            | Q(notes__icontains=val)
        )


class CreditEntryFilter(django_filters.FilterSet):
    """
    FilterSet for CreditEntry records:
    - status: filter by PENDING or SETTLED.
    - branch: filter by branch ID.
    - credit_owner: filter by CreditOwner ID.
    - start_date / end_date: filter by the linked cash entry's date.
    - search: search by credit owner name, phone, or notes.
    """

    status = django_filters.ChoiceFilter(
        choices=CreditEntry.Status.choices,
        help_text="Filter by credit status: PENDING or SETTLED.",
    )
    branch = django_filters.NumberFilter(
        field_name="branch_id",
        help_text="Filter credit entries by branch ID.",
    )
    credit_owner = django_filters.NumberFilter(
        field_name="credit_owner_id",
        help_text="Filter credit entries by Credit Owner ID.",
    )
    start_date = django_filters.DateFilter(
        method="filter_start_date",
        help_text="Filter credit entries from this date (YYYY-MM-DD).",
    )
    end_date = django_filters.DateFilter(
        method="filter_end_date",
        help_text="Filter credit entries up to this date (YYYY-MM-DD).",
    )
    search = django_filters.CharFilter(
        method="filter_search",
        help_text="Search by credit owner name, phone, or notes.",
    )

    class Meta:
        model = CreditEntry
        fields = [
            "status",
            "branch",
            "credit_owner",
            "start_date",
            "end_date",
            "search",
        ]

    def filter_start_date(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(date__gte=value) | Q(cash_entry__date__gte=value))

    def filter_end_date(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(date__lte=value) | Q(cash_entry__date__lte=value))

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            Q(notes__icontains=val)
            | Q(credit_owner__name__icontains=val)
            | Q(credit_owner__phone_number__icontains=val)
        )
