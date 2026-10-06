from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response

from account.models import User
from common.permissions import ALLOWED_STAFF_ROLES, IsStaffOrOperationalRole
from common.utils import CustomPagination
from order.filters import ActivityLogFilter, OrderFilter
from order.models import Order
from order.selectors import (
    get_activity_logs_queryset,
    get_customer_orders_queryset,
    get_order_activity_logs_queryset,
    get_orders_for_user_queryset,
)
from order.serializers import (
    ActivityLogSerializer,
    AssignRiderSerializer,
    OrderCreateSerializer,
    OrderResponseSerializer,
    OrderStatusUpdateSerializer,
    POSOrderCreateSerializer,
    PublicOrderUpdateSerializer,
)
from order.services.order_service import OrderService


class OrderListCreateAPIView(ListCreateAPIView):
    serializer_class = OrderResponseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = OrderFilter
    pagination_class = CustomPagination
    search_fields = ["customer_name", "phone_number", "order_number", "barcode_number"]

    def get_queryset(self):
        return get_orders_for_user_queryset(self.request.user)

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
        validated_data.pop(
            "branch", None
        )  # ignored; branch is taken from the authenticated user
        created_by = request.user
        branch = getattr(request.user, "branch", None)

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
    Unified API view to assign or unassign a rider to an order.
    Accepts either `barcode_number` or `order_number` to find the order.
    If `rider` key is provided (including null), sets rider to that value.
    If `rider` key is omitted completely, defaults to `request.user`.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = AssignRiderSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        barcode_number = serializer.validated_data.get("barcode_number")
        order_number = serializer.validated_data.get("order_number")

        if "rider" in serializer.validated_data:
            rider = serializer.validated_data["rider"]
        else:
            rider = request.user

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

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

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

        # ── Handle direct customer-detail fields sent in the PATCH body ──────
        order = serializer.instance
        raw = self.request.data

        updatable_fields = [
            "customer_name",
            "phone_number",
            "delivery_location",
            "special_note",
            "payment_type",
            "is_paid",
        ]
        for field in updatable_fields:
            if field in raw:
                value = raw[field]
                if field == "is_paid":
                    # Accept boolean strings from JSON body
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes")
                    else:
                        value = bool(value)
                setattr(order, field, value)

        # ── Handle delivery_fee / delivery_amount update ─────────────────────
        delivery_fee_val = None
        if "delivery_fee" in raw:
            delivery_fee_val = raw.get("delivery_fee")
        elif "delivery_amount" in raw:
            delivery_fee_val = raw.get("delivery_amount")
        elif "delivery_fee" in serializer.validated_data:
            delivery_fee_val = serializer.validated_data.get("delivery_fee")

        delivery_fee_updated = False
        if delivery_fee_val is not None:
            try:
                order.delivery_fee = max(0.0, round(float(delivery_fee_val), 2))
                delivery_fee_updated = True
            except (TypeError, ValueError):
                pass

        # ── Handle discount_amount update ────────────────────────────────────
        discount_amount_val = raw.get("discount_amount")
        if discount_amount_val is not None:
            try:
                order.discount_amount = max(0.0, round(float(discount_amount_val), 2))
                delivery_fee_updated = True
            except (TypeError, ValueError):
                pass

        # ── Handle items update ───────────────────────────────────────────────
        items_data = raw.get("items")
        if items_data is not None:
            try:
                OrderService.update_order_items(order, items_data, save_order=False)
            except ValueError as exc:
                raise serializers.ValidationError({"items": str(exc)})
        elif delivery_fee_updated:
            # If items did not change but delivery fee or discount changed, recalculate total
            OrderService.recalculate_order_totals(order, save_order=False)

        # Single atomic save for all validated serializer fields and direct model fields
        serializer.save(
            subtotal=order.subtotal,
            total_amount=order.total_amount,
            delivery_fee=order.delivery_fee,
            discount_amount=order.discount_amount,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        # Re-fetch order with optimized relations so the response is fully fresh and optimal
        refreshed_order = (
            self.get_queryset().filter(pk=serializer.instance.pk).first()
        ) or serializer.instance

        return Response(self.get_serializer(refreshed_order).data)


class RecentOrdersAPIView(GenericAPIView):
    """
    API View to retrieve the most recent orders scoped to user.branch.
    Accepts optional query parameter `limit` (default: 5).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OrderResponseSerializer

    def get_queryset(self):
        return get_orders_for_user_queryset(self.request.user)

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        try:
            limit = int(request.query_params.get("limit", 5))
        except (ValueError, TypeError):
            limit = 5

        recent_orders = queryset[:limit]
        serializer = self.get_serializer(recent_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicOrderUpdateAPIView(GenericAPIView):
    """
    Public API view to update an order's payment and status fields without requiring authentication (without token).
    Identified by `order_number` passed in URL path or request payload.
    Supports updating:
    - is_paid (boolean)
    - payment_type (COD / NPS)
    - status (PENDING / CONFIRMED / PREPARING / OUT_FOR_DELIVERY / DELIVERED / CANCELLED)
    - transaction_id (string)
    - comment (optional string for status change history)
    """

    permission_classes = [AllowAny]
    serializer_class = PublicOrderUpdateSerializer

    def patch(self, request, order_number=None, *args, **kwargs):
        return self._update_order(request, order_number)

    def _update_order(self, request, order_number=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_order_number = order_number or serializer.validated_data.get(
            "order_number"
        )

        if not target_order_number:
            return Response(
                {"error": "order_number is required in URL path or request body."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = Order.objects.filter(
            order_number=str(target_order_number).strip()
        ).first()
        if not order:
            return Response(
                {"error": f"Order '{target_order_number}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        validated_data = serializer.validated_data

        if "is_paid" in validated_data:
            order.is_paid = validated_data["is_paid"]

        if "payment_type" in validated_data:
            order.payment_type = validated_data["payment_type"]

        if "order_type" in validated_data:
            order.order_type = validated_data["order_type"]

        if "transaction_id" in validated_data:
            order.transaction_id = validated_data["transaction_id"]

        comment = validated_data.get("comment")
        if comment:
            order._status_change_comment = comment

        if "status" in validated_data:
            order.status = validated_data["status"]

        order.save()

        return Response(OrderResponseSerializer(order).data, status=status.HTTP_200_OK)


class CustomerOrderHistoryAPIView(ListAPIView):
    """
    API View to retrieve order history for a specific customer by customer ID.
    - Accessible by staff, admin, and operational roles.
    - Customers can view their own order history.
    - Supports pagination (CustomPagination), search, and filtering via OrderFilter.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OrderResponseSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = OrderFilter
    search_fields = [
        "order_number",
        "barcode_number",
        "customer_name",
        "phone_number",
        "delivery_location",
    ]

    def get_queryset(self):
        customer_id = self.kwargs.get("customer_id")
        user = self.request.user

        if not customer_id:
            raise NotFound("Customer ID is required.")

        if not User.objects.filter(id=customer_id).exists():
            raise NotFound(f"Customer with ID {customer_id} does not exist.")

        is_staff = (
            user.is_superuser
            or user.is_staff
            or getattr(user, "role", None) in ALLOWED_STAFF_ROLES
        )
        if not is_staff and user.id != int(customer_id):
            raise PermissionDenied(
                "You do not have permission to view another customer's order history."
            )

        queryset = get_customer_orders_queryset(customer_id=customer_id)

        # If rider, restrict to orders assigned to this rider
        if getattr(user, "role", None) == "rider":
            queryset = queryset.filter(assigned_to_rider=user)

        return queryset


class ActivityLogListCreateAPIView(ListCreateAPIView):
    """
    List and create activity log records.
    Supports filtering by entity_type, action_type, entity_name, user, order, date range, and search.
    """

    # permission_classes = [IsAuthenticated, IsStaffOrOperationalRole]
    serializer_class = ActivityLogSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = ActivityLogFilter
    pagination_class = CustomPagination
    search_fields = [
        "description",
        "record_repr",
        "record_id",
        "entity_name",
        "order__order_number",
        "user__username",
    ]

    def get_queryset(self):
        return get_activity_logs_queryset()


class ActivityLogRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, partial update, or delete a specific activity log entry.
    """

    permission_classes = [IsAuthenticated, IsStaffOrOperationalRole]
    serializer_class = ActivityLogSerializer

    def get_queryset(self):
        return get_activity_logs_queryset()


class OrderActivityLogListAPIView(ListAPIView):
    """
    List all activity logs associated with a specific order number.
    """

    permission_classes = [IsAuthenticated, IsStaffOrOperationalRole]
    serializer_class = ActivityLogSerializer
    pagination_class = CustomPagination

    def get_queryset(self):
        order_number = self.kwargs.get("order_number")
        if not order_number:
            raise NotFound("Order number is required.")
        return get_order_activity_logs_queryset(order_number)
