from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple, Union

from django.db.models import ExpressionWrapper, F, FloatField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from order.models import Order, OrderItem


def get_night_service_shift_range(
    target_date: Optional[Union[datetime, str]] = None,
) -> Tuple[datetime, datetime]:
    """
    Returns (start_dt, end_dt) for the night service shift:
    Starts at 6:00 PM (18:00:00) and ends at 4:00 AM (04:00:00) the next day
    in the application's timezone (Asia/Kathmandu).

    - If `target_date` is provided (date object or 'YYYY-MM-DD' string):
      The shift runs from target_date at 18:00:00 to (target_date + 1 day) at 04:00:00.
    - If `target_date` is not provided (None):
      Resolves current local time in Kathmandu.
      If current local time is before 04:00:00 AM (e.g., 01:30 AM), it belongs to
      the active night service shift that started yesterday at 18:00:00.
      Otherwise (from 04:00:00 AM onwards), it represents the shift starting today at 18:00:00.
    """
    tz = timezone.get_current_timezone()
    now_local = timezone.localtime(timezone.now(), tz)

    parsed_date = None
    if isinstance(target_date, str):
        try:
            parsed_date = datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            parsed_date = None
    elif (
        hasattr(target_date, "year")
        and hasattr(target_date, "month")
        and hasattr(target_date, "day")
    ):
        parsed_date = (
            target_date.date() if isinstance(target_date, datetime) else target_date
        )

    if parsed_date:
        shift_date = parsed_date
    else:
        # If before 4:00 AM, the shift belongs to the previous calendar day starting at 18:00
        if now_local.time() < time(4, 0, 0):
            shift_date = now_local.date() - timedelta(days=1)
        else:
            shift_date = now_local.date()

    start_naive = datetime.combine(shift_date, time(18, 0, 0))
    end_naive = datetime.combine(shift_date + timedelta(days=1), time(4, 0, 0))

    start_dt = timezone.make_aware(start_naive, tz)
    end_dt = timezone.make_aware(end_naive, tz)

    return start_dt, end_dt


def get_dashboard_stats(
    branch_id: Optional[int] = None,
    target_date: Optional[Union[datetime, str]] = None,
) -> Dict[str, Any]:
    """
    Selector to aggregate dashboard statistics:
    - total_orders_today: Count of orders created during the night service shift (6:00 PM to 4:00 AM next day).
    - total_revenue_today: Sum of revenue from non-cancelled orders created during the night service shift.
    - total_revenue: Total sum of revenue (excluding CANCELLED orders).
    - total_profit: Total profit calculated from revenue minus product cost price (excluding CANCELLED orders).
    - total_orders: Total count of all orders.
    - shift_start: Datetime of the shift start (6:00 PM).
    - shift_end: Datetime of the shift end (4:00 AM next day).
    """
    start_dt, end_dt = get_night_service_shift_range(target_date=target_date)

    order_qs = Order.objects.all()
    if branch_id:
        order_qs = order_qs.filter(branch_id=branch_id)

    today_orders_qs = order_qs.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    total_orders_today = today_orders_qs.count()

    today_revenue_aggregate = today_orders_qs.exclude(
        status=Order.OrderStatus.CANCELLED
    ).aggregate(total=Sum("total_amount"))
    total_revenue_today = round(float(today_revenue_aggregate["total"] or 0.0), 2)

    revenue_aggregate = order_qs.exclude(status=Order.OrderStatus.CANCELLED).aggregate(
        total=Sum("total_amount")
    )
    total_revenue = round(float(revenue_aggregate["total"] or 0.0), 2)

    cost_expr = ExpressionWrapper(
        F("quantity") * Coalesce(F("product__cost_price"), 0.0),
        output_field=FloatField(),
    )
    cost_aggregate = OrderItem.objects.filter(
        order__in=order_qs.exclude(status=Order.OrderStatus.CANCELLED)
    ).aggregate(total_cost=Coalesce(Sum(cost_expr), 0.0))
    total_cost = round(float(cost_aggregate["total_cost"] or 0.0), 2)
    total_profit = round(total_revenue - total_cost, 2)

    total_orders = order_qs.count()

    return {
        "total_orders_today": total_orders_today,
        "total_revenue_today": total_revenue_today,
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_orders": total_orders,
        "shift_start": start_dt,
        "shift_end": end_dt,
    }
