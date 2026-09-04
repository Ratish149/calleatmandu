from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from product.models import Product


def get_related_products_by_slug(product_slug: str) -> QuerySet[Product]:
    """
    Fetch related products that share the same category as the given product (by product_slug).
    Excludes the product itself from the returned list.
    Optimizes queries with select_related and prefetch_related to avoid N+1 queries.
    """
    product = get_object_or_404(Product, slug=product_slug)

    if not product.category_id:
        return Product.objects.none()

    return (
        Product.objects
        .filter(category_id=product.category_id)
        .exclude(id=product.id)
        .select_related("category")
        .prefetch_related("extras")
        .order_by("-created_at")
    )
