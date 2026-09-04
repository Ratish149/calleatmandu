from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from order.models import Order
from product.models import Product


def get_best_seller_products(branch_id=None, limit=5):
    """
    Selector to aggregate top best seller products based on total quantity sold in OrderItems.
    Excludes items from CANCELLED orders.
    Optionally filters by branch_id.
    """
    order_filter = ~Q(order_items__order__status=Order.OrderStatus.CANCELLED)
    if branch_id:
        order_filter &= Q(order_items__order__branch_id=branch_id)

    queryset = (
        Product.objects.annotate(
            total_quantity_sold=Coalesce(
                Sum("order_items__quantity", filter=order_filter),
                0,
            ),
            total_revenue=Coalesce(
                Sum("order_items__subtotal", filter=order_filter),
                0.0,
            ),
        )
        .filter(total_quantity_sold__gt=0)
        .select_related("category", "sub_category")
        .prefetch_related("extras", "images")
        .order_by("-total_quantity_sold", "-total_revenue")
    )

    if limit and limit > 0:
        queryset = queryset[:limit]

    return queryset
