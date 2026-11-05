from django.urls import path

from product.views import (
    CategoryListCreateAPIView,
    CategoryRetrieveUpdateDestroyAPIView,
    KitchenInventoryItemListCreateAPIView,
    KitchenInventoryItemRetrieveUpdateDestroyAPIView,
    KitchenInventoryLogListCreateAPIView,
    KitchenInventoryLogRetrieveUpdateDestroyAPIView,
    ProductExtraListCreateAPIView,
    ProductExtraRetrieveUpdateDestroyAPIView,
    ProductImageListCreateAPIView,
    ProductImageRetrieveUpdateDestroyAPIView,
    ProductListCreateAPIView,
    ProductRetrieveUpdateDestroyAPIView,
    RelatedProductListAPIView,
    SubcategoryListCreateAPIView,
    SubcategoryRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    # Categories
    path(
        "categories/", CategoryListCreateAPIView.as_view(), name="category-list-create"
    ),
    path(
        "categories/<slug:slug>/",
        CategoryRetrieveUpdateDestroyAPIView.as_view(),
        name="category-detail",
    ),
    # Subcategories
    path(
        "subcategories/",
        SubcategoryListCreateAPIView.as_view(),
        name="subcategory-list-create",
    ),
    path(
        "subcategories/<slug:slug>/",
        SubcategoryRetrieveUpdateDestroyAPIView.as_view(),
        name="subcategory-detail",
    ),
    # Products  — identified by slug
    path("products/", ProductListCreateAPIView.as_view(), name="product-list-create"),
    path(
        "products/<slug:product_slug>/related/",
        RelatedProductListAPIView.as_view(),
        name="related-product-list",
    ),
    path(
        "products/<slug:slug>/",
        ProductRetrieveUpdateDestroyAPIView.as_view(),
        name="product-detail",
    ),
    # Product Extras  (nested under product slug)
    path(
        "products/<slug:product_slug>/extras/",
        ProductExtraListCreateAPIView.as_view(),
        name="product-extra-list-create",
    ),
    path(
        "products/<slug:product_slug>/extras/<int:pk>/",
        ProductExtraRetrieveUpdateDestroyAPIView.as_view(),
        name="product-extra-detail",
    ),
    # Product Images  (nested under product slug)
    path(
        "products/<slug:product_slug>/images/",
        ProductImageListCreateAPIView.as_view(),
        name="product-image-list-create",
    ),
    path(
        "products/<slug:product_slug>/images/<int:pk>/",
        ProductImageRetrieveUpdateDestroyAPIView.as_view(),
        name="product-image-detail",
    ),
    # Kitchen Inventory — Items (admin manages)
    path(
        "kitchen/inventory/items/",
        KitchenInventoryItemListCreateAPIView.as_view(),
        name="kitchen-inventory-item-list-create",
    ),
    path(
        "kitchen/inventory/items/<int:pk>/",
        KitchenInventoryItemRetrieveUpdateDestroyAPIView.as_view(),
        name="kitchen-inventory-item-detail",
    ),
    # Kitchen Inventory — Daily Logs (kitchen staff submits)
    path(
        "kitchen/inventory/logs/",
        KitchenInventoryLogListCreateAPIView.as_view(),
        name="kitchen-inventory-log-list-create",
    ),
    path(
        "kitchen/inventory/logs/<int:pk>/",
        KitchenInventoryLogRetrieveUpdateDestroyAPIView.as_view(),
        name="kitchen-inventory-log-detail",
    ),
]
