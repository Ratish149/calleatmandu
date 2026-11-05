from typing import Any, Dict, Optional

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from order.models import Order, OrderItem
from product.models import Product

DRINK_KEYWORDS = (
    "drink",
    "liquor",
    "beverage",
    "alcohol",
    "wine",
    "beer",
    "whiskey",
    "whisky",
    "vodka",
    "rum",
    "gin",
    "bar",
)


def get_drink_or_liquor_q() -> Q:
    """
    Constructs an optimized Q expression to classify drink and liquor products
    based on Product.type (DRINK, LIQUOR) or beverage/liquor keywords in
    category, subcategory, or product name.
    """
    drink_q = Q(
        product__type__in=[
            Product.ProductType.DRINK,
            Product.ProductType.LIQUOR,
        ]
    )
    for kw in DRINK_KEYWORDS:
        drink_q |= (
            Q(product__category__name__icontains=kw)
            | Q(product__category__slug__icontains=kw)
            | Q(product__sub_category__name__icontains=kw)
            | Q(product__sub_category__slug__icontains=kw)
            | Q(product__name__icontains=kw)
        )
    return drink_q


def get_revenue_breakdown_stats(
    orders_qs: QuerySet[Order],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregates financial breakdown for the given orders queryset:
    - total_delivery_amount: Total delivery fee collected from orders.
    - total_food_item_amount: Total amount from food items (excluding drinks/liquors).
    - total_liquor_or_drink_amount: Total amount from liquor and drink items.
    - total_orders: Total count of non-cancelled orders.
    - total_amount: Total order revenue.
    Executed in 2 optimized SQL queries with zero N+1 overhead.
    """
    drink_q = get_drink_or_liquor_q()

    # 1. Order-level aggregate for delivery fees and overall order counts
    order_stats = orders_qs.aggregate(
        total_delivery_amount=Coalesce(Sum("delivery_fee"), 0.0),
        total_orders=Count("id"),
        total_amount=Coalesce(Sum("total_amount"), 0.0),
    )

    # 2. Item-level conditional aggregate for food vs drink/liquor items
    item_stats = OrderItem.objects.filter(order__in=orders_qs).aggregate(
        total_food_item_amount=Coalesce(Sum("subtotal", filter=~drink_q), 0.0),
        total_liquor_or_drink_amount=Coalesce(Sum("subtotal", filter=drink_q), 0.0),
    )

    total_delivery = round(float(order_stats["total_delivery_amount"] or 0.0), 2)
    total_food = round(float(item_stats["total_food_item_amount"] or 0.0), 2)
    total_drinks = round(
        float(item_stats["total_liquor_or_drink_amount"] or 0.0), 2
    )
    total_revenue = round(float(order_stats["total_amount"] or 0.0), 2)
    total_orders = order_stats["total_orders"]

    return {
        "total_delivery_amount": total_delivery,
        "total_food_item_amount": total_food,
        "total_liquor_or_drink_amount": total_drinks,
        "total_orders": total_orders,
        "total_amount": total_revenue,
        "start_date": start_date,
        "end_date": end_date,
    }
