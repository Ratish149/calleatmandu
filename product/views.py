from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsAdminRole, IsStaffOrOperationalRole
from common.utils import CustomPagination
from product.filters import (
    CategoryFilter,
    KitchenInventoryItemFilter,
    KitchenInventoryLogFilter,
    ProductFilter,
    SubcategoryFilter,
)
from product.models import (
    Category,
    KitchenInventoryItem,
    KitchenInventoryLog,
    Product,
    ProductExtra,
    ProductImage,
    Subcategory,
)
from product.selectors import get_related_products_by_slug
from product.serializers import (
    CategorySerializer,
    KitchenInventoryItemSerializer,
    KitchenInventoryLogSerializer,
    ProductCreateSerializer,
    ProductDetailSerializer,
    ProductExtraCreateSerializer,
    ProductImageCreateSerializer,
    ProductListSerializer,
    SubcategorySerializer,
)

# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CategoryListCreateAPIView(ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = CategoryFilter
    search_fields = ["name"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]


class CategoryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]


# ---------------------------------------------------------------------------
# Subcategory
# ---------------------------------------------------------------------------


class SubcategoryListCreateAPIView(ListCreateAPIView):
    queryset = Subcategory.objects.select_related("category").all()
    serializer_class = SubcategorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = SubcategoryFilter
    search_fields = ["name"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]


class SubcategoryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Subcategory.objects.select_related("category").all()
    serializer_class = SubcategorySerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------


class ProductListCreateAPIView(ListCreateAPIView):
    queryset = (
        Product.objects
        .select_related("category", "sub_category")
        .prefetch_related("extras")
        .all()
        .order_by("-created_at")
    )
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = ProductFilter
    pagination_class = CustomPagination
    search_fields = ["name"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        response_serializer = ProductDetailSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ProductRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = (
        Product.objects
        .select_related("category", "sub_category")
        .prefetch_related("extras", "images")
        .all()
    )
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return ProductCreateSerializer
        return ProductDetailSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = ProductCreateSerializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        response_serializer = ProductDetailSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# ProductExtra  (nested under a product)
# ---------------------------------------------------------------------------


class ProductExtraListCreateAPIView(ListCreateAPIView):
    """
    GET  /products/<product_slug>/extras/   — list all extras for a product
    POST /products/<product_slug>/extras/   — add a new extra to a product
    """

    serializer_class = ProductExtraCreateSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

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

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return ProductExtra.objects.filter(product__slug=self.kwargs["product_slug"])


# ---------------------------------------------------------------------------
# ProductImage  (nested under a product)
# ---------------------------------------------------------------------------


class ProductImageListCreateAPIView(ListCreateAPIView):
    """
    GET  /products/<product_slug>/images/   — list all images for a product
    POST /products/<product_slug>/images/   — add a new image to a product
    """

    serializer_class = ProductImageCreateSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return ProductImage.objects.filter(product__slug=self.kwargs["product_slug"])

    def perform_create(self, serializer):
        product = Product.objects.get(slug=self.kwargs["product_slug"])
        serializer.save(product=product)


class ProductImageRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /products/<product_slug>/images/<pk>/
    PUT    /products/<product_slug>/images/<pk>/
    PATCH  /products/<product_slug>/images/<pk>/
    DELETE /products/<product_slug>/images/<pk>/
    """

    serializer_class = ProductImageCreateSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return ProductImage.objects.filter(product__slug=self.kwargs["product_slug"])


# ---------------------------------------------------------------------------
# Related Product
# ---------------------------------------------------------------------------


class RelatedProductListAPIView(ListAPIView):
    """
    GET /products/<product_slug>/related/ — list related products in the same category
    """

    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    pagination_class = CustomPagination

    def get_queryset(self):
        product_slug = self.kwargs.get("product_slug") or self.kwargs.get("slug")
        return get_related_products_by_slug(product_slug)


# ---------------------------------------------------------------------------
# Kitchen Inventory
# ---------------------------------------------------------------------------


class KitchenInventoryItemListCreateAPIView(ListCreateAPIView):
    """
    GET  /kitchen/inventory/items/        — Admin & kitchen staff: list all items
    POST /kitchen/inventory/items/        — Admin only: create a new inventory item

    Supports filtering by: search, unit, below_benchmark
    Supports ordering by: name, total_quantity, benchmark_quantity, created_at
    """

    serializer_class = KitchenInventoryItemSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = KitchenInventoryItemFilter
    search_fields = ["name"]
    ordering_fields = ["name", "total_quantity", "benchmark_quantity", "created_at"]
    ordering = ["name"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsStaffOrOperationalRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        return KitchenInventoryItem.objects.all()


class KitchenInventoryItemRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /kitchen/inventory/items/<pk>/  — retrieve item detail
    PUT    /kitchen/inventory/items/<pk>/  — admin: full update
    PATCH  /kitchen/inventory/items/<pk>/  — admin: partial update
    DELETE /kitchen/inventory/items/<pk>/  — admin: delete item
    """

    serializer_class = KitchenInventoryItemSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsStaffOrOperationalRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        return KitchenInventoryItem.objects.all()


class KitchenInventoryLogListCreateAPIView(ListCreateAPIView):
    """
    GET  /kitchen/inventory/logs/     — List daily logs (admin sees all, kitchen sees own)
    POST /kitchen/inventory/logs/     — Kitchen staff: submit today's consumption log

    Supports filtering by: item, start_date, end_date, updated_by, search
    Supports ordering by: date, consumed_quantity, received_quantity, created_at
    """

    serializer_class = KitchenInventoryLogSerializer
    permission_classes = [IsStaffOrOperationalRole]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = KitchenInventoryLogFilter
    search_fields = ["item__name", "notes"]
    ordering_fields = ["date", "consumed_quantity", "received_quantity", "created_at"]
    ordering = ["-date"]

    def get_queryset(self):
        return (
            KitchenInventoryLog.objects
            .select_related("item", "updated_by")
            .all()
        )


class KitchenInventoryLogRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /kitchen/inventory/logs/<pk>/  — retrieve log detail
    PUT    /kitchen/inventory/logs/<pk>/  — kitchen staff: full update (corrects total_quantity)
    PATCH  /kitchen/inventory/logs/<pk>/  — kitchen staff: partial update
    DELETE /kitchen/inventory/logs/<pk>/  — admin only: delete a log entry
    """

    serializer_class = KitchenInventoryLogSerializer

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsAdminRole()]
        return [IsStaffOrOperationalRole()]

    def get_queryset(self):
        return (
            KitchenInventoryLog.objects
            .select_related("item", "updated_by")
            .all()
        )
