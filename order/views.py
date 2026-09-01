from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response

from common.permissions import ALLOWED_STAFF_ROLES, IsStaffOrOperationalRole
from common.utils import CustomPagination
from order.filters import OrderFilter
from order.models import Order
from order.serializers import (
    AssignRiderSerializer,
    OrderCreateSerializer,
    OrderResponseSerializer,
    POSOrderCreateSerializer,
)
from order.services.order_service import OrderService


class OrderListCreateAPIView(ListCreateAPIView):
    serializer_class = OrderResponseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = OrderFilter
    pagination_class = CustomPagination
    search_fields = ["customer_name", "phone_number", "order_number", "barcode_number"]

    def get_queryset(self):
        queryset = (
            Order.objects
            .select_related(
                "branch",
                "user",
                "created_by",
                "assigned_to_rider",
                "offer",
                "promo_code",
            )
            .prefetch_related("items__product", "items__selected_extras")
            .order_by("-created_at")
        )
        user = self.request.user

        if user and user.is_authenticated:
            # If user is a rider, return orders assigned to this rider
            if getattr(user, "role", None) == "rider":
                queryset = queryset.filter(assigned_to_rider=user)
            # If staff user has an assigned branch, return orders belonging to that branch only
            elif getattr(user, "branch_id", None):
                queryset = queryset.filter(branch_id=user.branch_id)
            elif not (
                user.is_superuser
                or user.is_staff
                or getattr(user, "role", None) in ALLOWED_STAFF_ROLES
            ):
                # Non-staff customer users see only their own orders
                queryset = queryset.filter(user=user)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items_data = serializer.validated_data.pop("items")
        user = request.user

        try:
            order = OrderService.create_order(
                user=user,
                order_data=serializer.validated_data,
                cart_items_data=items_data,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = OrderResponseSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class POSOrderListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsStaffOrOperationalRole]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = OrderFilter
    pagination_class = CustomPagination
    search_fields = ["customer_name", "phone_number", "order_number", "barcode_number"]

    def get_queryset(self):
        queryset = (
            Order.objects
            .filter(is_pos_order=True)
            .select_related(
                "branch",
                "user",
                "created_by",
                "assigned_to_rider",
                "offer",
                "promo_code",
            )
            .prefetch_related("items__product", "items__selected_extras")
            .order_by("-created_at")
        )
        user = self.request.user

        if user and user.is_authenticated and getattr(user, "branch_id", None):
            queryset = queryset.filter(branch_id=user.branch_id)

        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return POSOrderCreateSerializer
        return OrderResponseSerializer

    def create(self, request, *args, **kwargs):
        serializer = POSOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        items_data = validated_data.pop("items")
        customer_user = validated_data.pop("user", None)
        branch = validated_data.pop("branch", None)
        created_by = request.user

        try:
            order = OrderService.create_pos_order(
                created_by=created_by,
                customer_user=customer_user,
                branch=branch,
                order_data=validated_data,
                cart_items_data=items_data,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = OrderResponseSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AssignRiderAPIView(GenericAPIView):
    """
    Unified API view to assign a rider to an order.
    Accepts either `barcode_number` or `order_number` to find the order.
    Assigns to specified `rider` if provided, otherwise defaults to `request.user`.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = AssignRiderSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        barcode_number = serializer.validated_data.get("barcode_number")
        order_number = serializer.validated_data.get("order_number")
        rider = serializer.validated_data.get("rider") or request.user

        try:
            order = OrderService.assign_rider(
                barcode_number=barcode_number,
                order_number=order_number,
                rider=rider,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderResponseSerializer(order).data, status=status.HTTP_200_OK)


class OrderRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Order.objects.select_related(
        "branch", "user", "created_by", "assigned_to_rider", "offer", "promo_code"
    ).prefetch_related("items__product", "items__selected_extras")
    serializer_class = OrderResponseSerializer
    permission_classes = [IsStaffOrOperationalRole]
    lookup_field = "order_number"
