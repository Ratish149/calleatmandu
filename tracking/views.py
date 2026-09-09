from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from tracking.filters import RiderLocationFilter
from tracking.selectors.tracking_selector import (
    get_active_riders_locations_qs,
    get_customer_order_tracking,
)
from tracking.serializers import (
    AdminRiderTrackingSerializer,
    CustomerOrderTrackingSerializer,
    RiderLocationSerializer,
    RiderLocationUpdateSerializer,
    RiderToggleOnlineSerializer,
)
from tracking.services.tracking_service import (
    toggle_rider_online_status,
    update_rider_location,
)


class RiderUpdateLocationAPIView(CreateAPIView):
    """
    HTTP REST endpoint for riders to submit location updates.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RiderLocationUpdateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location, created = update_rider_location(
            rider=request.user,
            latitude=serializer.validated_data["latitude"],
            longitude=serializer.validated_data["longitude"],
        )

        response_serializer = RiderLocationSerializer(location)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_serializer.data, status=status_code)


class RiderToggleOnlineAPIView(CreateAPIView):
    """
    HTTP REST endpoint for riders to toggle online/offline availability.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RiderToggleOnlineSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location = toggle_rider_online_status(
            rider=request.user,
            is_online=serializer.validated_data["is_online"],
        )

        response_serializer = RiderLocationSerializer(location)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class AdminRiderListTrackingAPIView(ListAPIView):
    """
    HTTP REST endpoint for Admins to view all rider locations with filtering.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AdminRiderTrackingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RiderLocationFilter

    def get_queryset(self):
        return get_active_riders_locations_qs()


class CustomerOrderTrackingAPIView(RetrieveAPIView):
    """
    HTTP REST endpoint for customers to get current tracking snapshot for an order.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerOrderTrackingSerializer
    lookup_field = "order_number"

    def get_object(self):
        order_number = self.kwargs.get("order_number")
        order = get_customer_order_tracking(order_number)
        if not order:
            from rest_framework.exceptions import NotFound

            raise NotFound(detail=f"Order '{order_number}' not found.")
        return order
