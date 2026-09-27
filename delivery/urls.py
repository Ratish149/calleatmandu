from django.urls import path

from delivery.views import (
    DeliveryEstimateAPIView,
    DeliveryPricingRetrieveUpdateDestroyView,
    DeliveryPricingRetrieveUpdateView,
)

app_name = "delivery"

urlpatterns = [
    path(
        "delivery/pricing/",
        DeliveryPricingRetrieveUpdateView.as_view(),
        name="delivery-pricing",
    ),
    path(
        "delivery/pricing/<int:pk>/",
        DeliveryPricingRetrieveUpdateDestroyView.as_view(),
        name="delivery-pricing-detail",
    ),
    path(
        "delivery/estimate/",
        DeliveryEstimateAPIView.as_view(),
        name="delivery-estimate",
    ),
]
