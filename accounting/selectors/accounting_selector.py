from typing import Any, Dict, Optional

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from accounting.models import (
    CashExpenditure,
    CreditEntry,
    CreditSettlement,
    VendorTransaction,
)


def get_cash_balance_summary(
    queryset: Optional[QuerySet[CashExpenditure]] = None,
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vendor_transaction_queryset: Optional[QuerySet[VendorTransaction]] = None,
) -> Dict[str, Any]:
    """
    Balance summary selector.

    Formulas:
      total_cash_amount             = SUM(cash_expenditure.cash_amount)  [full cash collected]
      total_online_amount           = SUM(cash_expenditure.online_amount)  [full online collected]
      total_vendor_cash_paid        = SUM(vendor_transaction.amount WHERE payment_method=CASH)
      total_vendor_online_paid      = SUM(vendor_transaction.amount WHERE payment_method=ONLINE)
      total_cash_available_amount   = total_cash_amount + credit_settled_cash - total_vendor_cash_paid
      total_online_available_amount = total_online_amount + credit_settled_online - total_vendor_online_paid
      total_credit_amount           = SUM(cash_expenditure.credit_amount)
      total_delivery_charge         = SUM(cash_expenditure.delivery_charge)
      total_vendor_paid_amount      = total_vendor_cash_paid + total_vendor_online_paid
      available_balance             = total_cash_available_amount + total_online_available_amount - total_delivery_charge
    """
    if queryset is None:
        queryset = CashExpenditure.objects.all()

    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)

    if start_date:
        queryset = queryset.filter(date__gte=start_date)

    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    # --- Cash entry aggregation ---
    agg = queryset.aggregate(
        base_cash_amount=Coalesce(Sum("cash_amount"), 0.0),
        base_online_amount=Coalesce(Sum("online_amount"), 0.0),
        total_credit_amount=Coalesce(Sum("credit_amount"), 0.0),
        total_delivery_charge=Coalesce(Sum("delivery_charge"), 0.0),
        total_entries=Count("id"),
    )

    # --- Vendor payments ---
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
        total_vendor_paid_amount=Coalesce(Sum("amount"), 0.0),
        total_vendor_cash_paid=Coalesce(
            Sum(
                "amount",
                filter=Q(
                    payment_method__iexact=VendorTransaction.PaymentMethod.CASH
                ),
            ),
            0.0,
        ),
        total_vendor_online_paid=Coalesce(
            Sum(
                "amount",
                filter=Q(
                    payment_method__iexact=VendorTransaction.PaymentMethod.ONLINE
                ),
            ),
            0.0,
        ),
    )

    # --- Credit settlements scoped to this period's cash entries ---
    # Settled cash/online counts towards collected totals
    credit_entry_ids = CreditEntry.objects.filter(
        cash_entry__in=queryset
    ).values_list("id", flat=True)

    settlement_agg = CreditSettlement.objects.filter(
        credit_entry_id__in=credit_entry_ids
    ).aggregate(
        settled_cash=Coalesce(Sum("cash_settled"), 0.0),
        settled_online=Coalesce(Sum("online_settled"), 0.0),
    )

    # --- Compute final values ---
    base_cash = round(float(agg["base_cash_amount"] or 0.0), 2)
    base_online = round(float(agg["base_online_amount"] or 0.0), 2)
    settled_cash = round(float(settlement_agg["settled_cash"] or 0.0), 2)
    settled_online = round(float(settlement_agg["settled_online"] or 0.0), 2)

    total_vendor_paid_amount = round(
        float(vendor_agg["total_vendor_paid_amount"] or 0.0), 2
    )
    total_vendor_cash_paid = round(
        float(vendor_agg["total_vendor_cash_paid"] or 0.0), 2
    )
    total_vendor_online_paid = round(
        float(vendor_agg["total_vendor_online_paid"] or 0.0), 2
    )

    # Ensure any non-cash payments not yet updated to ONLINE are safely included in online total
    remaining_non_cash = round(
        total_vendor_paid_amount - (total_vendor_cash_paid + total_vendor_online_paid),
        2,
    )
    if remaining_non_cash > 0:
        total_vendor_online_paid = round(
            total_vendor_online_paid + remaining_non_cash, 2
        )

    # Full gross amounts collected from entries
    total_cash_amount = base_cash
    total_online_amount = base_online

    # Available amounts after adding credit settlements and deducting vendor payments in their respective modes
    total_cash_available_amount = round(
        base_cash + settled_cash - total_vendor_cash_paid, 2
    )
    total_online_available_amount = round(
        base_online + settled_online - total_vendor_online_paid, 2
    )

    total_credit_amount = round(float(agg["total_credit_amount"] or 0.0), 2)
    total_delivery_charge = round(float(agg["total_delivery_charge"] or 0.0), 2)

    total_available_balance = round(
        total_cash_available_amount
        + total_online_available_amount
        - total_delivery_charge,
        2,
    )

    return {
        "total_cash_amount": total_cash_amount,
        "total_online_amount": total_online_amount,
        "total_cash_available_amount": total_cash_available_amount,
        "total_online_available_amount": total_online_available_amount,
        "total_credit_amount": total_credit_amount,
        "total_delivery_charge": total_delivery_charge,
        "total_vendor_paid_amount": total_vendor_paid_amount,
        "total_vendor_cash_paid": total_vendor_cash_paid,
        "total_vendor_online_paid": total_vendor_online_paid,
        "total_available_balance": total_available_balance,
        "available_balance": total_available_balance,
        "total_entries": agg["total_entries"],
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }


def get_credit_stats(
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dedicated credit statistics selector.

    Returns:
      total_credit_amount   = sum of all credit amounts given in period
      total_credit_settled  = sum of all settled amounts (cash + online)
      total_credit_remaining = total_credit_amount - total_credit_settled
      settled_count         = number of fully SETTLED credit entries
      pending_count         = number of PENDING credit entries
      total_entries         = total credit entries in period
    """
    queryset = CreditEntry.objects.filter(
        cash_entry__isnull=False,
    ).select_related("cash_entry", "settlement")

    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)

    if start_date:
        queryset = queryset.filter(cash_entry__date__gte=start_date)

    if end_date:
        queryset = queryset.filter(cash_entry__date__lte=end_date)

    entry_agg = queryset.aggregate(
        total_credit_amount=Coalesce(Sum("credit_amount"), 0.0),
        total_entries=Count("id"),
        settled_count=Count("id", filter=Q(status=CreditEntry.Status.SETTLED)),
        pending_count=Count("id", filter=Q(status=CreditEntry.Status.PENDING)),
    )

    settlement_agg = CreditSettlement.objects.filter(
        credit_entry__in=queryset
    ).aggregate(
        settled_cash=Coalesce(Sum("cash_settled"), 0.0),
        settled_online=Coalesce(Sum("online_settled"), 0.0),
    )

    total_credit_amount = round(float(entry_agg["total_credit_amount"] or 0.0), 2)
    total_credit_settled = round(
        float(settlement_agg["settled_cash"] or 0.0)
        + float(settlement_agg["settled_online"] or 0.0),
        2,
    )
    total_credit_remaining = round(total_credit_amount - total_credit_settled, 2)

    return {
        "total_credit_amount": total_credit_amount,
        "total_credit_settled": total_credit_settled,
        "total_credit_remaining": total_credit_remaining,
        "settled_count": entry_agg["settled_count"],
        "pending_count": entry_agg["pending_count"],
        "total_entries": entry_agg["total_entries"],
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }

