from django.urls import path

from product.views import (
    CategoryListCreateAPIView,
    CategoryRetrieveUpdateDestroyAPIView,
    ProductExtraListCreateAPIView,
    ProductExtraRetrieveUpdateDestroyAPIView,
    ProductListCreateAPIView,
    ProductRetrieveUpdateDestroyAPIView,
    SubcategoryListCreateAPIView,
    SubcategoryRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    # Categories
    path("categories/", CategoryListCreateAPIView.as_view(), name="category-list-create"),
    path("categories/<int:pk>/", CategoryRetrieveUpdateDestroyAPIView.as_view(), name="category-detail"),

    # Subcategories
    path("subcategories/", SubcategoryListCreateAPIView.as_view(), name="subcategory-list-create"),
    path("subcategories/<int:pk>/", SubcategoryRetrieveUpdateDestroyAPIView.as_view(), name="subcategory-detail"),

    # Products  — identified by slug
    path("products/", ProductListCreateAPIView.as_view(), name="product-list-create"),
    path("products/<slug:slug>/", ProductRetrieveUpdateDestroyAPIView.as_view(), name="product-detail"),

    # Product Extras  (nested under product slug)
    path("products/<slug:product_slug>/extras/", ProductExtraListCreateAPIView.as_view(), name="product-extra-list-create"),
    path("products/<slug:product_slug>/extras/<int:pk>/", ProductExtraRetrieveUpdateDestroyAPIView.as_view(), name="product-extra-detail"),
]
