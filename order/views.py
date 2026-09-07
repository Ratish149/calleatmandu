from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import ALLOWED_STAFF_ROLES, IsStaffOrOperationalRole
from common.utils import CustomPagination
from order.filters import OrderFilter
from order.models import Order
from order.serializers import (
    AssignRiderSerializer,
    OrderCreateSerializer,
    OrderResponseSerializer,
    OrderStatusUpdateSerializer,
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
            .prefetch_related(
                "items__product",
                "items__selected_extras",
                "nps_transactions",
                "status_history__changed_by",
            )
            .order_by("-created_at")
        )
        user = self.request.user

        if user and user.is_authenticated:
            # If user is a customer, return only orders belonging to that customer
            if getattr(user, "role", None) == "customer" or not (
                user.is_superuser
                or user.is_staff
                or getattr(user, "role", None) in ALLOWED_STAFF_ROLES
            ):
                queryset = queryset.filter(user=user)
            # If user is a rider, return orders assigned to this rider
            elif getattr(user, "role", None) == "rider":
                queryset = queryset.filter(assigned_to_rider=user)
            # If staff user has an assigned branch, return orders belonging to that branch only
            elif getattr(user, "branch_id", None):
                queryset = queryset.filter(branch_id=user.branch_id)

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
            .prefetch_related(
                "items__product",
                "items__selected_extras",
                "nps_transactions",
                "status_history__changed_by",
            )
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


class OrderStatusUpdateAPIView(GenericAPIView):
    """
    API View for riders and operational staff to update order status.
    Requires a comment/reason if the target status is CANCELLED.
    Lookup supports either:
    1. URL parameter `order_number` (e.g. PATCH /orders/<order_number>/status/)
    2. Body parameters `order_number` or `barcode_number` (e.g. POST /orders/status/)
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = OrderStatusUpdateSerializer

    def patch(self, request, *args, **kwargs):
        return self.update_status(request, *args, **kwargs)

    def update_status(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_number = kwargs.get("order_number") or serializer.validated_data.get(
            "order_number"
        )
        barcode_number = serializer.validated_data.get("barcode_number")
        new_status = serializer.validated_data["status"]
        comment = serializer.validated_data.get("comment")

        order = None
        if order_number:
            order = Order.objects.filter(order_number=order_number).first()
            if not order:
                return Response(
                    {"error": f"Order with order_number '{order_number}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif barcode_number:
            order = Order.objects.filter(barcode_number=barcode_number).first()
            if not order:
                return Response(
                    {"error": f"Order with barcode '{barcode_number}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {
                    "error": "Either order_number (in URL or body) or barcode_number must be provided."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = OrderService.update_order_status(
                order=order,
                new_status=new_status,
                comment=comment,
                changed_by=request.user,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderResponseSerializer(order).data, status=status.HTTP_200_OK)


class OrderRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Order.objects.select_related(
        "branch", "user", "created_by", "assigned_to_rider", "offer", "promo_code"
    ).prefetch_related(
        "items__product",
        "items__selected_extras",
        "nps_transactions",
        "status_history__changed_by",
    )
    serializer_class = OrderResponseSerializer
    permission_classes = [IsStaffOrOperationalRole]
    lookup_field = "order_number"

    def perform_update(self, serializer):
        new_status = serializer.validated_data.get("status")
        comment = self.request.data.get("comment") or self.request.data.get(
            "status_comment"
        )

        if new_status == Order.OrderStatus.CANCELLED and (
            not comment or not comment.strip()
        ):
            raise serializers.ValidationError({
                "comment": "A comment/reason is required when cancelling an order."
            })

        if comment:
            serializer.instance._status_change_comment = comment
        if self.request.user and self.request.user.is_authenticated:
            serializer.instance._status_changed_by = self.request.user
        serializer.save()


class RecentOrdersAPIView(GenericAPIView):
    """
    API View to retrieve the 5 most recent orders for any authenticated user.
    Accepts optional query parameter `limit` (default: 5).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OrderResponseSerializer

    def get(self, request, *args, **kwargs):
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
            .prefetch_related(
                "items__product",
                "items__selected_extras",
                "nps_transactions",
                "status_history__changed_by",
            )
            .order_by("-created_at")
        )

        try:
            limit = int(request.query_params.get("limit", 5))
        except (ValueError, TypeError):
            limit = 5

        recent_orders = queryset[:limit]
        serializer = self.get_serializer(recent_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
