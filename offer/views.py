from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from offer.filters import OfferFilter, PromoCodeFilter
from offer.models import Offer, PromoCode
from offer.serializers import (
    OfferCheckSerializer,
    OfferSerializer,
    PromoCodeSerializer,
)
from offer.services.offer_service import OfferService


class OfferListCreateAPIView(ListCreateAPIView):
    queryset = Offer.objects.prefetch_related("promo_codes", "products").select_related(
        "category", "subcategory", "buy_product", "get_product"
    )
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = OfferFilter


class OfferRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Offer.objects.prefetch_related("promo_codes", "products").select_related(
        "category", "subcategory", "buy_product", "get_product"
    )
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PromoCodeListCreateAPIView(ListCreateAPIView):
    queryset = PromoCode.objects.select_related("offer")
    serializer_class = PromoCodeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = PromoCodeFilter


class PromoCodeRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = PromoCode.objects.select_related("offer")
    serializer_class = PromoCodeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class OfferCheckAPIView(APIView):
    """
    Check & calculate applicable offer or validate input promo code for cart.
    """

    def post(self, request, *args, **kwargs):
        serializer = OfferCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_total = serializer.validated_data["cart_total"]
        cart_items = serializer.validated_data.get("cart_items", [])
        promo_code = serializer.validated_data.get("promo_code")

        result = OfferService.evaluate_cart_offer(
            cart_items=cart_items,
            cart_total=cart_total,
            promo_code_str=promo_code,
            user=request.user if request.user.is_authenticated else None,
        )

        status_code = (
            status.HTTP_200_OK if result["is_valid"] else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=status_code)
