from django.db.models import Sum
from django.utils import timezone

from order.models import Order
from product.models import Product


def get_dashboard_stats(branch_id=None):
    """
    Selector to aggregate dashboard statistics:
    - total_orders_today: Count of orders created today (local time).
    - total_revenue_today: Sum of revenue from non-cancelled orders created today.
    - total_revenue: Total sum of revenue (excluding CANCELLED orders).
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

    total_products = Product.objects.count()
    total_orders = order_qs.count()

    return {
        "total_orders_today": total_orders_today,
        "total_revenue_today": total_revenue_today,
        "total_revenue": total_revenue,
        "total_products": total_products,
        "total_orders": total_orders,
    }
