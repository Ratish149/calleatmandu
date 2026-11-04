from typing import Any, Dict, List, Optional

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from accounting.models import Vendor, VendorTransaction


def get_vendor_transaction_summary(
    queryset: Optional[QuerySet[VendorTransaction]] = None,
    vendor_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculates total billed, total paid, and remaining due for a filtered
    VendorTransaction queryset. Executed in a single aggregation query.
    """
    if queryset is None:
        queryset = VendorTransaction.objects.all()

    if vendor_id:
        queryset = queryset.filter(vendor_id=vendor_id)

    if start_date:
        queryset = queryset.filter(date__gte=start_date)

    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    agg = queryset.aggregate(
        total_billed=Coalesce(
            Sum("amount", filter=Q(transaction_type=VendorTransaction.TransactionType.BILL)),
            0.0,
        ),
        total_paid=Coalesce(
            Sum("amount", filter=Q(transaction_type=VendorTransaction.TransactionType.PAYMENT)),
            0.0,
        ),
        total_entries=Count("id"),
        bill_count=Count("id", filter=Q(transaction_type=VendorTransaction.TransactionType.BILL)),
        payment_count=Count("id", filter=Q(transaction_type=VendorTransaction.TransactionType.PAYMENT)),
    )

    total_billed = round(float(agg["total_billed"] or 0.0), 2)
    total_paid = round(float(agg["total_paid"] or 0.0), 2)
    remaining_due = round(total_billed - total_paid, 2)

    return {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "remaining_due": remaining_due,
        "total_entries": agg["total_entries"],
        "bill_count": agg["bill_count"],
        "payment_count": agg["payment_count"],
        "start_date": start_date,
        "end_date": end_date,
    }


def get_vendor_summary_report(
    vendor_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    user: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Generates a financial summary report:
    - If vendor_id is NOT provided: calculates totals based on all vendors.
    - If vendor_id IS provided: calculates totals for that specific vendor only.
    - Respects branch restrictions for operational staff / branch managers.
    - Executes via an optimized database aggregation query.
    """
    queryset = VendorTransaction.objects.select_related("vendor", "branch").all()

    # Apply branch restrictions based on user permissions or query param
    if (
        user
        and user.is_authenticated
        and not user.is_superuser
        and getattr(user, "role", None) != "admin"
        and getattr(user, "branch_id", None)
    ):
        queryset = queryset.filter(branch_id=user.branch_id)
    elif branch_id:
        queryset = queryset.filter(branch_id=branch_id)

    # Filter by specific vendor if provided
    vendor_obj = None
    if vendor_id:
        queryset = queryset.filter(vendor_id=vendor_id)
        vendor_obj = Vendor.objects.filter(id=vendor_id).first()

    # Filter by date range
    if start_date:
        queryset = queryset.filter(date__gte=start_date)

    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    # Filter by search string
    if search:
        s = str(search).strip()
        queryset = queryset.filter(
            Q(vendor__name__icontains=s)
            | Q(vendor__phone_number__icontains=s)
            | Q(title__icontains=s)
            | Q(notes__icontains=s)
        )

    agg = queryset.aggregate(
        total_billed=Coalesce(
            Sum("amount", filter=Q(transaction_type=VendorTransaction.TransactionType.BILL)),
            0.0,
        ),
        total_paid=Coalesce(
            Sum("amount", filter=Q(transaction_type=VendorTransaction.TransactionType.PAYMENT)),
            0.0,
        ),
        total_entries=Count("id"),
        bill_count=Count("id", filter=Q(transaction_type=VendorTransaction.TransactionType.BILL)),
        payment_count=Count("id", filter=Q(transaction_type=VendorTransaction.TransactionType.PAYMENT)),
        vendor_count=Count("vendor_id", distinct=True),
    )

    total_billed = round(float(agg["total_billed"] or 0.0), 2)
    total_paid = round(float(agg["total_paid"] or 0.0), 2)
    remaining_due = round(total_billed - total_paid, 2)

    return {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "remaining_due": remaining_due,
        "total_entries": agg["total_entries"],
        "bill_count": agg["bill_count"],
        "payment_count": agg["payment_count"],
        "vendor_count": agg["vendor_count"],
        "vendor_id": vendor_id if vendor_id else None,
        "vendor_name": vendor_obj.name if vendor_obj else None,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }

