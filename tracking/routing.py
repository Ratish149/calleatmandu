from django.urls import path

from tracking.consumers import (
    AdminTrackingConsumer,
    CustomerOrderTrackingConsumer,
    RiderLocationConsumer,
)

websocket_urlpatterns = [
    path("ws/tracking/rider/", RiderLocationConsumer.as_asgi()),
    path("ws/tracking/admin/", AdminTrackingConsumer.as_asgi()),
    path("ws/tracking/order/<str:order_number>/", CustomerOrderTrackingConsumer.as_asgi()),
]
