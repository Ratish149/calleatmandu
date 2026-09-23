from datetime import timedelta

from django.db.models import Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from order.models import Order, OrderItem


def get_order_analytics(queryset):
    """
    Selector to aggregate order analytics:
    1. order_volume:
       - today: Total orders created today (local time).
       - this_week: Total orders created this week (Monday to today).
       - this_month: Total orders created this month (1st of month to today).
       - total: Total orders in queryset.
       - revenue_today, revenue_this_week, revenue_this_month, total_revenue.
    2. summary:
       - total_orders, total_revenue, total_cost, gross_profit, profit_margin_percentage.
    3. by_order_type:
       - Breakdown for each OrderType (DELIVERY, TAKEAWAY, POS, DINEIN, etc.)
         including count of orders, revenue, cost price from OrderItems, gross profit,
         margin, and order percentage.
    """
    now = timezone.localtime(timezone.now())
    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # 1. Volume Metrics
    orders_today = queryset.filter(created_at__date=today).count()
    revenue_today = float(
        queryset
        .filter(created_at__date=today)
        .exclude(status=Order.OrderStatus.CANCELLED)
        .aggregate(r=Coalesce(Sum("total_amount"), 0.0))["r"]
    )

    orders_week = queryset.filter(
        created_at__date__gte=week_start, created_at__date__lte=today
    ).count()
    revenue_week = float(
        queryset
        .filter(created_at__date__gte=week_start, created_at__date__lte=today)
        .exclude(status=Order.OrderStatus.CANCELLED)
        .aggregate(r=Coalesce(Sum("total_amount"), 0.0))["r"]
    )

    orders_month = queryset.filter(
        created_at__date__gte=month_start, created_at__date__lte=today
    ).count()
    revenue_month = float(
        queryset
        .filter(created_at__date__gte=month_start, created_at__date__lte=today)
        .exclude(status=Order.OrderStatus.CANCELLED)
        .aggregate(r=Coalesce(Sum("total_amount"), 0.0))["r"]
    )

    total_orders = queryset.count()
    total_revenue = float(
        queryset.exclude(status=Order.OrderStatus.CANCELLED).aggregate(
            r=Coalesce(Sum("total_amount"), 0.0)
        )["r"]
    )

    order_volume = {
        "today": orders_today,
        "this_week": orders_week,
        "this_month": orders_month,
        "total": total_orders,
        "revenue_today": round(revenue_today, 2),
        "revenue_this_week": round(revenue_week, 2),
        "revenue_this_month": round(revenue_month, 2),
        "total_revenue": round(total_revenue, 2),
    }

    # 2. Order Breakdown by Order Type on queryset
    order_type_choices = dict(Order.OrderType.choices)

    order_agg = queryset.values("order_type").annotate(
        total_orders=Count("id"),
        total_revenue=Coalesce(
            Sum("total_amount", filter=~Q(status=Order.OrderStatus.CANCELLED)),
            0.0,
        ),
    )
    order_stats_map = {item["order_type"]: item for item in order_agg}

    cost_expr = ExpressionWrapper(
        F("quantity") * F("product__cost_price"), output_field=FloatField()
    )

    cost_agg = (
        OrderItem.objects
        .filter(order__in=queryset.exclude(status=Order.OrderStatus.CANCELLED))
        .values("order__order_type")
        .annotate(total_cost=Coalesce(Sum(cost_expr), 0.0))
    )
    cost_stats_map = {
        item["order__order_type"]: float(item["total_cost"]) for item in cost_agg
    }

    overall_orders = queryset.count()
    by_order_type = []
    seen_types = set()

    # Prepopulate with standard defined choices so 0-count choices are always returned
    for ot_key, ot_label in order_type_choices.items():
        seen_types.add(ot_key)
        stat = order_stats_map.get(ot_key, {})
        orders_cnt = stat.get("total_orders", 0)
        rev = round(float(stat.get("total_revenue", 0.0)), 2)
        cost = round(float(cost_stats_map.get(ot_key, 0.0)), 2)
        profit = round(rev - cost, 2)
        margin = round((profit / rev) * 100, 2) if rev > 0 else 0.0
        pct = (
            round((orders_cnt / overall_orders) * 100, 2) if overall_orders > 0 else 0.0
        )

        by_order_type.append({
            "order_type": ot_key,
            "order_type_display": ot_label,
            "total_orders": orders_cnt,
            "total_revenue": rev,
            "total_cost": cost,
            "gross_profit": profit,
            "profit_margin_percentage": margin,
            "order_percentage": pct,
        })

    # Include any legacy / unspecified rows where order_type is None or custom
    for ot_key, stat in order_stats_map.items():
        if ot_key not in seen_types:
            orders_cnt = stat.get("total_orders", 0)
            rev = round(float(stat.get("total_revenue", 0.0)), 2)
            cost = round(float(cost_stats_map.get(ot_key, 0.0)), 2)
            profit = round(rev - cost, 2)
            margin = round((profit / rev) * 100, 2) if rev > 0 else 0.0
            pct = (
                round((orders_cnt / overall_orders) * 100, 2)
                if overall_orders > 0
                else 0.0
            )

            by_order_type.append({
                "order_type": ot_key,
                "order_type_display": "Unspecified" if ot_key is None else str(ot_key),
                "total_orders": orders_cnt,
                "total_revenue": rev,
                "total_cost": cost,
                "gross_profit": profit,
                "profit_margin_percentage": margin,
                "order_percentage": pct,
            })

    # Summary
    sum_orders = sum(item["total_orders"] for item in by_order_type)
    sum_rev = round(sum(item["total_revenue"] for item in by_order_type), 2)
    sum_cost = round(sum(item["total_cost"] for item in by_order_type), 2)
    sum_profit = round(sum_rev - sum_cost, 2)
    sum_margin = round((sum_profit / sum_rev) * 100, 2) if sum_rev > 0 else 0.0

    summary = {
        "total_orders": sum_orders,
        "total_revenue": sum_rev,
        "total_cost": sum_cost,
        "gross_profit": sum_profit,
        "profit_margin_percentage": sum_margin,
    }

    return {
        "order_volume": order_volume,
        "summary": summary,
        "by_order_type": by_order_type,
    }
