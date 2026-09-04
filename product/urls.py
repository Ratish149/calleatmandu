from django.urls import path

from product.views import (
    CategoryListCreateAPIView,
    CategoryRetrieveUpdateDestroyAPIView,
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
]
