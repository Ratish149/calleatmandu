from datetime import timedelta

from django.db.models import BooleanField, Case, Count, F, Max, Q, Value, When
from django.utils import timezone

from account.models import User
from order.models import Order


def get_customer_activity_queryset(days: int = 15):
    """
    Optimized queryset to retrieve all customers annotated with:
    - total_orders: Count of non-cancelled orders placed by the customer.
    - last_order_date: DateTime of the customer's most recent non-cancelled order.
    - is_active_customer: Boolean indicating whether last_order_date >= now - days.
    """
    cutoff = timezone.now() - timedelta(days=days)
    non_cancelled = ~Q(orders__status=Order.OrderStatus.CANCELLED)

    return (
        User.objects
        .filter(role="customer")
        .select_related("branch")
        .annotate(
            total_orders=Count("orders", filter=non_cancelled, distinct=True),
            last_order_date=Max("orders__created_at", filter=non_cancelled),
        )
        .annotate(
            is_active_customer=Case(
                When(last_order_date__gte=cutoff, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )
        .order_by(
            F("last_order_date").desc(nulls_last=True),
            "-date_joined",
        )
    )
