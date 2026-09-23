from django.db.models import ExpressionWrapper, F, FloatField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from order.models import Order, OrderItem


def get_dashboard_stats(branch_id=None):
    """
    Selector to aggregate dashboard statistics:
    - total_orders_today: Count of orders created today (local time).
    - total_revenue_today: Sum of revenue from non-cancelled orders created today.
    - total_revenue: Total sum of revenue (excluding CANCELLED orders).
    - total_profit: Total profit calculated from revenue minus product cost price (excluding CANCELLED orders).
    - total_products: Total count of products in catalog.
    - total_orders: Total count of all orders.
    """
    today_date = timezone.localtime(timezone.now()).date()

    order_qs = Order.objects.all()
    if branch_id:
        order_qs = order_qs.filter(branch_id=branch_id)

    total_orders_today = order_qs.filter(created_at__date=today_date).count()

    today_revenue_aggregate = (
        order_qs
        .filter(created_at__date=today_date)
        .exclude(status=Order.OrderStatus.CANCELLED)
        .aggregate(total=Sum("total_amount"))
    )
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
    }
