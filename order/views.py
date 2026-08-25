from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsStaffOrOperationalRole
from order.filters import OrderFilter
from order.models import Order
from order.serializers import OrderCreateSerializer, OrderSerializer
from order.services.order_service import OrderService


class OrderListCreateAPIView(ListCreateAPIView):
    queryset = Order.objects.select_related(
        "branch", "user", "offer", "promo_code"
    ).prefetch_related("items__product", "items__selected_extras")
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = OrderFilter

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [IsStaffOrOperationalRole()]

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

        response_serializer = OrderSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class OrderRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Order.objects.select_related(
        "branch", "user", "offer", "promo_code"
    ).prefetch_related("items__product", "items__selected_extras")
    serializer_class = OrderSerializer
    permission_classes = [IsStaffOrOperationalRole]
    lookup_field = "order_number"
