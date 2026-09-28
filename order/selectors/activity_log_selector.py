from typing import Optional

from django.db.models import QuerySet

from order.models import ActivityLog


def get_activity_logs_queryset() -> QuerySet[ActivityLog]:
    """
    Optimized base queryset to retrieve activity logs.
    Pre-fetches user and order to eliminate N+1 queries.
    """
    return (
        ActivityLog.objects
        .select_related("user", "order")
        .order_by("-created_at", "-id")
    )


def get_order_activity_logs_queryset(
    order_identifier: str,
) -> QuerySet[ActivityLog]:
    """
    Retrieves all activity logs associated with a specific order (by ID or order_number).
    """
    qs = get_activity_logs_queryset()
    if order_identifier.isdigit():
        return qs.filter(order_id=int(order_identifier))
    return qs.filter(order__order_number__iexact=order_identifier)


def get_entity_activity_logs_queryset(
    entity_type: str,
    record_id: Optional[str] = None,
) -> QuerySet[ActivityLog]:
    """
    Retrieves activity logs filtered by entity type (and optionally record ID).
    """
    qs = get_activity_logs_queryset().filter(entity_type=entity_type)
    if record_id:
        qs = qs.filter(record_id=str(record_id))
    return qs
