from django.urls import path

from offer.views import (
    OfferCheckAPIView,
    OfferListCreateAPIView,
    OfferRetrieveUpdateDestroyAPIView,
    PromoCodeListCreateAPIView,
    PromoCodeRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    # Offer CRUD endpoints
    path("offers/", OfferListCreateAPIView.as_view(), name="offer-list-create"),
    path(
        "offers/<int:pk>/",
        OfferRetrieveUpdateDestroyAPIView.as_view(),
        name="offer-detail",
    ),
    # PromoCode CRUD endpoints
    path(
        "promo-codes/",
        PromoCodeListCreateAPIView.as_view(),
        name="promocode-list-create",
    ),
    path(
        "promo-codes/<int:pk>/",
        PromoCodeRetrieveUpdateDestroyAPIView.as_view(),
        name="promocode-detail",
    ),
    # Offer Verification / Checking endpoint
    path("offers/check/", OfferCheckAPIView.as_view(), name="offer-check"),
]
