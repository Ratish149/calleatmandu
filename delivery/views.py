from rest_framework import status
from rest_framework.generics import (
    CreateAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from delivery.exceptions import (
    BranchNotFoundError,
    DeliveryDistanceExceededError,
    DeliveryPricingError,
    RoutingError,
)
from delivery.models import DeliveryPricing
from delivery.permissions import IsStaffOrReadOnly
from delivery.serializers import (
    DeliveryEstimateRequestSerializer,
    DeliveryEstimateResponseSerializer,
    DeliveryPricingSerializer,
)
from delivery.services.delivery_service import DeliveryService


class DeliveryPricingRetrieveUpdateView(RetrieveUpdateAPIView):
    """
    Retrieve (GET) or update (PUT/PATCH) the singleton delivery pricing configuration.
    Also accepts POST requests to upsert the singleton instance.
    """

    serializer_class = DeliveryPricingSerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_object(self):
        return DeliveryPricing.get_instance()

    def post(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class DeliveryPricingRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve or update the singleton delivery pricing configuration via primary key.
    Deletion is disallowed to preserve singleton integrity.
    """

    serializer_class = DeliveryPricingSerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_object(self):
        return DeliveryPricing.get_instance()

    def delete(self, request, *args, **kwargs):
        return Response(
            {
                "detail": "Delivery pricing is a singleton configuration and cannot be deleted."
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class DeliveryEstimateAPIView(CreateAPIView):
    """
    Public endpoint to estimate road distance, travel duration, and delivery charge
    for a destination coordinate and assigned branch.
    """

    permission_classes = [AllowAny]
    serializer_class = DeliveryEstimateRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lat = serializer.validated_data["latitude"]
        lng = serializer.validated_data["longitude"]
        branch_id = serializer.validated_data.get("branch_id")

        try:
            estimate_result = DeliveryService.estimate_delivery(
                destination_lat=lat,
                destination_lng=lng,
                branch_id=branch_id,
                allow_fallback=True,
            )
        except BranchNotFoundError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DeliveryPricingError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (RoutingError, DeliveryDistanceExceededError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        response_serializer = DeliveryEstimateResponseSerializer(estimate_result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
