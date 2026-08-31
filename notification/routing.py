from django.urls import path

from notification.consumers import OrderNotificationConsumer

websocket_urlpatterns = [
    path("ws/orders/", OrderNotificationConsumer.as_asgi()),
]
