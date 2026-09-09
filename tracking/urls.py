from django.urls import path

from tracking.views import (
    AdminRiderListTrackingAPIView,
    CustomerOrderTrackingAPIView,
    RiderToggleOnlineAPIView,
    RiderUpdateLocationAPIView,
)

app_name = "tracking"

urlpatterns = [
    path(
        "tracking/location/",
        RiderUpdateLocationAPIView.as_view(),
        name="rider-update-location",
    ),
    path(
        "tracking/toggle-online/",
        RiderToggleOnlineAPIView.as_view(),
        name="rider-toggle-online",
    ),
    path(
        "tracking/riders/",
        AdminRiderListTrackingAPIView.as_view(),
        name="admin-list-riders",
    ),
    path(
        "tracking/order/<str:order_number>/",
        CustomerOrderTrackingAPIView.as_view(),
        name="customer-order-tracking",
    ),
]
