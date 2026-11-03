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
    Optimized selector to calculate total cash added, total expenditure, and available balance.
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
        total_cash=Coalesce(Sum("cash_amount"), 0.0),
        total_expenditure=Coalesce(Sum("expenditure_amount"), 0.0),
        total_entries=Count("id"),
        cash_in_count=Count("id", filter=Q(cash_amount__gt=0)),
        expenditure_count=Count("id", filter=Q(expenditure_amount__gt=0)),
    )

    total_cash = round(float(agg["total_cash"] or 0.0), 2)
    total_expenditure = round(float(agg["total_expenditure"] or 0.0), 2)
    available_balance = round(total_cash - total_expenditure, 2)

    return {
        "total_cash_amount": total_cash,
        "total_expenditure_amount": total_expenditure,
        "total_available_balance": available_balance,
        "total_entries": agg["total_entries"],
        "cash_in_entries_count": agg["cash_in_count"],
        "expenditure_entries_count": agg["expenditure_count"],
        "start_date": start_date,
        "end_date": end_date,
    }
