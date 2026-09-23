from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from order.models import Order
from product.models import Category, Product


def get_best_seller_products(branch_id=None, category_id=None, limit=5):
    """
    Selector to aggregate top best seller products based on total revenue generated.
    Excludes items from CANCELLED orders.
    Optionally filters by branch_id and category (by id or slug/name).
    """
    order_filter = ~Q(order_items__order__status=Order.OrderStatus.CANCELLED)
    if branch_id:
        order_filter &= Q(order_items__order__branch_id=branch_id)

    queryset = Product.objects.annotate(
        total_quantity_sold=Coalesce(
            Sum("order_items__quantity", filter=order_filter),
            0,
        ),
        total_revenue=Coalesce(
            Sum("order_items__subtotal", filter=order_filter),
            0.0,
        ),
    ).filter(total_revenue__gt=0)

    if category_id:
        if str(category_id).isdigit():
            queryset = queryset.filter(category_id=int(category_id))
        else:
            queryset = queryset.filter(
                Q(category__slug=category_id) | Q(category__name__iexact=category_id)
            )

    queryset = (
        queryset.select_related("category", "sub_category")
        .prefetch_related("extras", "images")
        .order_by("-total_revenue", "-total_quantity_sold")
    )

    if limit and limit > 0:
        queryset = queryset[:limit]

    return queryset


def get_best_seller_categories(branch_id=None, limit=5):
    """
    Selector to aggregate top selling categories based on total revenue generated.
    Excludes items from CANCELLED orders.
    Optionally filters by branch_id.
    """
    cat_order_filter = ~Q(product__order_items__order__status=Order.OrderStatus.CANCELLED)
    if branch_id:
        cat_order_filter &= Q(product__order_items__order__branch_id=branch_id)

    categories_qs = (
        Category.objects.annotate(
            total_quantity_sold=Coalesce(
                Sum("product__order_items__quantity", filter=cat_order_filter),
                0,
            ),
            total_revenue=Coalesce(
                Sum("product__order_items__subtotal", filter=cat_order_filter),
                0.0,
            ),
        )
        .filter(total_revenue__gt=0)
        .order_by("-total_revenue", "-total_quantity_sold")
    )

    if limit and limit > 0:
        categories_qs = categories_qs[:limit]

    return categories_qs


def get_best_sellers_stats(branch_id=None, category_id=None, limit=5):
    """
    Combined selector returning both top selling products and categories ordered by revenue.
    """
    products = get_best_seller_products(
        branch_id=branch_id, category_id=category_id, limit=limit
    )
    categories = get_best_seller_categories(
        branch_id=branch_id, limit=limit
    )
    return {
        "products": products,
        "categories": categories,
    }

