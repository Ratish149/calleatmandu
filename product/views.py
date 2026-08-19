from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from product.models import Category, Product, ProductExtra, Subcategory
from product.serializers import (
    CategorySerializer,
    ProductCreateSerializer,
    ProductDetailSerializer,
    ProductExtraCreateSerializer,
    ProductListSerializer,
    SubcategorySerializer,
)

# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CategoryListCreateAPIView(ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class CategoryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


# ---------------------------------------------------------------------------
# Subcategory
# ---------------------------------------------------------------------------


class SubcategoryListCreateAPIView(ListCreateAPIView):
    queryset = Subcategory.objects.select_related("category").all()
    serializer_class = SubcategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category"]


class SubcategoryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Subcategory.objects.select_related("category").all()
    serializer_class = SubcategorySerializer
    permission_classes = [AllowAny]


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------


class ProductListCreateAPIView(ListCreateAPIView):
    queryset = Product.objects.select_related("category", "sub_category").all()
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "sub_category"]

    def create(self, request, *args, **kwargs):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        response_serializer = ProductDetailSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ProductRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = (
        Product.objects.select_related("category", "sub_category")
        .prefetch_related("extras", "images")
        .all()
    )
    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


# ---------------------------------------------------------------------------
# ProductExtra  (nested under a product)
# ---------------------------------------------------------------------------


class ProductExtraListCreateAPIView(ListCreateAPIView):
    """
    GET  /products/<product_slug>/extras/   — list all extras for a product
    POST /products/<product_slug>/extras/   — add a new extra to a product
    """

    serializer_class = ProductExtraCreateSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return ProductExtra.objects.filter(product__slug=self.kwargs["product_slug"])

    def perform_create(self, serializer):
        product = Product.objects.get(slug=self.kwargs["product_slug"])
        serializer.save(product=product)


class ProductExtraRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /products/<product_slug>/extras/<pk>/
    PUT    /products/<product_slug>/extras/<pk>/
    PATCH  /products/<product_slug>/extras/<pk>/
    DELETE /products/<product_slug>/extras/<pk>/
    """

    serializer_class = ProductExtraCreateSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return ProductExtra.objects.filter(product__slug=self.kwargs["product_slug"])
