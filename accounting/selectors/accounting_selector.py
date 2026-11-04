from typing import Any, Dict, Optional

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from accounting.models import CashExpenditure


def get_cash_balance_summary(
    queryset: Optional[QuerySet[CashExpenditure]] = None,
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Optimized selector to calculate physical cash additions, online receipts,
    expenditures, and net available balances across cash and digital channels.
    Executes in a single database aggregation query.
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
        total_cash_in=Coalesce(
            Sum(
                "cash_amount",
                filter=Q(entry_type=CashExpenditure.EntryType.CASH_IN),
            ),
            0.0,
        ),
        total_online_in=Coalesce(
            Sum(
                "cash_amount",
                filter=Q(entry_type=CashExpenditure.EntryType.ONLINE_IN),
            ),
            0.0,
        ),
        total_expenditure=Coalesce(
            Sum(
                "expenditure_amount",
                filter=Q(entry_type=CashExpenditure.EntryType.EXPENDITURE),
            ),
            0.0,
        ),
        cash_expenditure=Coalesce(
            Sum(
                "expenditure_amount",
                filter=Q(
                    entry_type=CashExpenditure.EntryType.EXPENDITURE,
                    payment_method=CashExpenditure.PaymentMethod.CASH,
                ),
            ),
            0.0,
        ),
        online_expenditure=Coalesce(
            Sum(
                "expenditure_amount",
                filter=Q(entry_type=CashExpenditure.EntryType.EXPENDITURE)
                & ~Q(payment_method=CashExpenditure.PaymentMethod.CASH),
            ),
            0.0,
        ),
        total_entries=Count("id"),
        cash_in_count=Count(
            "id", filter=Q(entry_type=CashExpenditure.EntryType.CASH_IN)
        ),
        online_in_count=Count(
            "id", filter=Q(entry_type=CashExpenditure.EntryType.ONLINE_IN)
        ),
        expenditure_count=Count(
            "id", filter=Q(entry_type=CashExpenditure.EntryType.EXPENDITURE)
        ),
    )

    total_cash_in = round(float(agg["total_cash_in"] or 0.0), 2)
    total_online_in = round(float(agg["total_online_in"] or 0.0), 2)
    total_inflow = round(total_cash_in + total_online_in, 2)
    total_expenditure = round(float(agg["total_expenditure"] or 0.0), 2)
    cash_expenditure = round(float(agg["cash_expenditure"] or 0.0), 2)
    online_expenditure = round(float(agg["online_expenditure"] or 0.0), 2)

    total_available_balance = round(total_inflow - total_expenditure, 2)
    available_cash_balance = round(total_cash_in - cash_expenditure, 2)
    available_online_balance = round(total_online_in - online_expenditure, 2)

    return {
        "total_cash_in": total_cash_in,
        "total_online_in": total_online_in,
        "total_cash_amount": total_inflow,
        "total_expenditure_amount": total_expenditure,
        "cash_expenditure_amount": cash_expenditure,
        "online_expenditure_amount": online_expenditure,
        "total_available_balance": total_available_balance,
        "available_cash_balance": available_cash_balance,
        "available_online_balance": available_online_balance,
        "total_entries": agg["total_entries"],
        "cash_in_entries_count": agg["cash_in_count"],
        "online_in_entries_count": agg["online_in_count"],
        "expenditure_entries_count": agg["expenditure_count"],
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }

