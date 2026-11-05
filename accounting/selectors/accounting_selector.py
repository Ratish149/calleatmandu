from typing import Any, Dict, Optional

from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import Coalesce

from accounting.models import CashExpenditure, VendorTransaction


def get_cash_balance_summary(
    queryset: Optional[QuerySet[CashExpenditure]] = None,
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vendor_transaction_queryset: Optional[QuerySet[VendorTransaction]] = None,
) -> Dict[str, Any]:
    """
    Optimized selector to calculate total cash amount, online amount,
    delivery charge, vendor payment amount, and net available balance:
    available_balance = cash_amount + online_amount - delivery_charge - vendor_payment_amount.
    Executes database aggregation queries efficiently.
    """
    if queryset is None:
        queryset = CashExpenditure.objects.all()

    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)

    if start_date:
        queryset = queryset.filter(date__gte=start_date)

    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    agg = queryset.aggregate(
        total_cash_amount=Coalesce(Sum("cash_amount"), 0.0),
        total_online_amount=Coalesce(Sum("online_amount"), 0.0),
        total_delivery_charge=Coalesce(Sum("delivery_charge"), 0.0),
        total_entries=Count("id"),
    )

    if vendor_transaction_queryset is None:
        vendor_transaction_queryset = VendorTransaction.objects.filter(
            transaction_type=VendorTransaction.TransactionType.PAYMENT
        )
        if branch_id:
            vendor_transaction_queryset = vendor_transaction_queryset.filter(
                branch_id=branch_id
            )
        if start_date:
            vendor_transaction_queryset = vendor_transaction_queryset.filter(
                date__gte=start_date
            )
        if end_date:
            vendor_transaction_queryset = vendor_transaction_queryset.filter(
                date__lte=end_date
            )
    else:
        vendor_transaction_queryset = vendor_transaction_queryset.filter(
            transaction_type=VendorTransaction.TransactionType.PAYMENT
        )

    vendor_agg = vendor_transaction_queryset.aggregate(
        total_vendor_paid_amount=Coalesce(Sum("amount"), 0.0)
    )

    total_cash_amount = round(float(agg["total_cash_amount"] or 0.0), 2)
    total_online_amount = round(float(agg["total_online_amount"] or 0.0), 2)
    total_delivery_charge = round(float(agg["total_delivery_charge"] or 0.0), 2)
    total_vendor_paid_amount = round(
        float(vendor_agg["total_vendor_paid_amount"] or 0.0), 2
    )

    total_available_balance = round(
        total_cash_amount
        + total_online_amount
        - total_delivery_charge
        - total_vendor_paid_amount,
        2,
    )

    return {
        "total_cash_amount": total_cash_amount,
        "total_online_amount": total_online_amount,
        "total_delivery_charge": total_delivery_charge,
        "total_vendor_paid_amount": total_vendor_paid_amount,
        "total_available_balance": total_available_balance,
        "available_balance": total_available_balance,
        "total_entries": agg["total_entries"],
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }
