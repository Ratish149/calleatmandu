from typing import Any, Dict, Optional

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from accounting.models import CreditEntry, CreditOwner, CreditSettlement


def get_credit_owner_summary_report(
    owner_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Calculates aggregate financial metrics for credit owners:
    - total_credit_amount: Total credit given across entries.
    - total_settled_amount: Total amount settled via cash and online.
    - total_remaining_due: Outstanding debt owed by owners.
    - total_owners: Count of active credit owners.
    - pending_entries_count: Total pending credit entries.
    """
    entries_qs = CreditEntry.objects.select_related(
        "credit_owner", "cash_entry", "branch"
    ).all()

    if (
        user
        and user.is_authenticated
        and not user.is_superuser
        and getattr(user, "role", None) != "admin"
    ):
        if getattr(user, "branch_id", None):
            entries_qs = entries_qs.filter(branch_id=user.branch_id)
    elif branch_id:
        entries_qs = entries_qs.filter(branch_id=branch_id)

    if owner_id:
        entries_qs = entries_qs.filter(credit_owner_id=owner_id)

    if start_date:
        entries_qs = entries_qs.filter(
            Q(date__gte=start_date) | Q(cash_entry__date__gte=start_date)
        )

    if end_date:
        entries_qs = entries_qs.filter(
            Q(date__lte=end_date) | Q(cash_entry__date__lte=end_date)
        )

    entry_agg = entries_qs.aggregate(
        total_credit=Coalesce(Sum("credit_amount"), 0.0),
        total_entries=Count("id"),
        pending_count=Count("id", filter=Q(status=CreditEntry.Status.PENDING)),
        settled_count=Count("id", filter=Q(status=CreditEntry.Status.SETTLED)),
    )

    settlement_agg = CreditSettlement.objects.filter(
        credit_entry__in=entries_qs
    ).aggregate(
        settled_cash=Coalesce(Sum("cash_settled"), 0.0),
        settled_online=Coalesce(Sum("online_settled"), 0.0),
    )

    total_credit = round(float(entry_agg["total_credit"] or 0.0), 2)
    total_settled = round(
        float(settlement_agg["settled_cash"] or 0.0)
        + float(settlement_agg["settled_online"] or 0.0),
        2,
    )
    remaining_due = round(total_credit - total_settled, 2)

    owners_qs = CreditOwner.objects.all()
    if (
        user
        and user.is_authenticated
        and not user.is_superuser
        and getattr(user, "role", None) != "admin"
    ):
        if getattr(user, "branch_id", None):
            owners_qs = owners_qs.filter(branch_id=user.branch_id)
    elif branch_id:
        owners_qs = owners_qs.filter(branch_id=branch_id)

    return {
        "total_credit_amount": total_credit,
        "total_settled_amount": total_settled,
        "total_remaining_due": remaining_due,
        "total_entries": entry_agg["total_entries"],
        "pending_entries_count": entry_agg["pending_count"],
        "settled_entries_count": entry_agg["settled_count"],
        "total_owners_count": owners_qs.count(),
        "active_owners_count": owners_qs.count(),
        "owner_id": owner_id,
        "branch_id": branch_id,
        "start_date": start_date,
        "end_date": end_date,
    }
