from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, ExtractHour

from order.models import Order


def get_peak_order_hours(queryset):
    """
    Selector to calculate order volume and revenue grouped by hour of the day (0-23).
    - Groups by ExtractHour of created_at.
    - Fills in all 24 hours (0 to 23) with labels like '4 AM', '4 PM'.
    """
    hourly_stats = (
        queryset.annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(
            total_orders=Count("id"),
            total_revenue=Coalesce(
                Sum("total_amount", filter=~Q(status=Order.OrderStatus.CANCELLED)),
                0.0,
            ),
        )
        .order_by("hour")
    )

    # Initialize all 24 hours (0-23)
    hour_map = {
        h: {
            "time_label": f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}",
            "total_orders": 0,
            "total_revenue": 0.0,
        }
        for h in range(24)
    }

    for item in hourly_stats:
        h = item["hour"]
        if h is not None and 0 <= h <= 23:
            hour_map[h]["total_orders"] = item["total_orders"]
            hour_map[h]["total_revenue"] = round(float(item["total_revenue"] or 0.0), 2)

    return [hour_map[h] for h in range(24)]
