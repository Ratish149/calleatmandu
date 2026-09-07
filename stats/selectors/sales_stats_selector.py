from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncMonth, TruncWeek

from order.models import Order


def get_daily_sales_stats(queryset, period="daily"):
    """
    Selector to calculate breakdown of orders and revenue from an Order queryset.
    - Groups by created_at date based on period:
      - 'daily': TruncDate (YYYY-MM-DD)
      - 'weekly': TruncWeek (YYYY-MM-DD representing week start date)
      - 'monthly': TruncMonth (YYYY-MM representing month)
    - Counts total orders per period.
    - Sums total revenue per period (excluding CANCELLED orders).
    """
    if period == "weekly":
        trunc_func = TruncWeek("created_at")
        date_format = "%Y-%m-%d"
    elif period == "monthly":
        trunc_func = TruncMonth("created_at")
        date_format = "%Y-%m"
    else:
        trunc_func = TruncDate("created_at")
        date_format = "%Y-%m-%d"

    daily_stats = (
        queryset.annotate(date=trunc_func)
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
        if not item["date"]:
            continue
        date_str = item["date"].strftime(date_format)
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

