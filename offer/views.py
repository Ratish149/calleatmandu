from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from common.utils import CustomPagination
from offer.filters import OfferFilter, PromoCodeFilter
from offer.models import Offer, PromoCode
from offer.serializers import (
    OfferCheckSerializer,
    OfferSerializer,
    PromoCodeCheckSerializer,
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
    pagination_class = CustomPagination


class OfferRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Offer.objects.prefetch_related("promo_codes", "products").select_related(
        "category", "subcategory", "buy_product", "get_product"
    )
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PromoCodeListCreateAPIView(ListCreateAPIView):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = PromoCodeFilter


class PromoCodeRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class OfferCheckAPIView(APIView):
    """
    Check & calculate applicable offer or validate input promo code for cart.
    Only authenticated users can check/apply offers.
    """

    permission_classes = [IsAuthenticated]

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
            user=request.user,
        )

        status_code = (
            status.HTTP_200_OK if result["is_valid"] else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=status_code)


class PromoCodeCheckAPIView(APIView):
    """
    Check and validate a promo code, returning its details and calculated discount.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PromoCodeCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        cart_total = serializer.validated_data.get("cart_total", 0.0)

        result = OfferService.check_promo_code_detail(
            code_str=code,
            cart_total=cart_total,
            user=request.user,
        )

        status_code = (
            status.HTTP_200_OK if result["is_valid"] else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=status_code)
