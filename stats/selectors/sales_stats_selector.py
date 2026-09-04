from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate

from order.models import Order


def get_daily_sales_stats(queryset):
    """
    Selector to calculate daily breakdown of orders and revenue from an Order queryset.
    - Groups by created_at date using TruncDate.
    - Counts total orders per day.
    - Sums total revenue per day (excluding CANCELLED orders).
    """
    daily_stats = (
        queryset.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(
            total_orders=Count("id"),
            total_revenue=Coalesce(
                Sum("total_amount", filter=~Q(status=Order.OrderStatus.CANCELLED)),
                0.0,
            ),
        )
        .order_by("date")
    )

    results = []
    for item in daily_stats:
        date_str = item["date"].strftime("%Y-%m-%d") if item["date"] else ""
        rev = round(float(item["total_revenue"] or 0.0), 2)
        orders_count = item["total_orders"]

        results.append(
            {
                "date": date_str,
                "total_orders": orders_count,
                "total_revenue": rev,
            }
        )

    return results
