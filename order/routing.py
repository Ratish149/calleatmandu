from django.urls import path

from order.consumers import OrderConsumer, PrinterConsumer

websocket_urlpatterns = [
    # General order lifecycle feeds
    path("ws/order/", OrderConsumer.as_asgi()),
    path("ws/order/<str:branch_id>/", OrderConsumer.as_asgi()),
    path("ws/orders/live/", OrderConsumer.as_asgi()),
    path("ws/orders/live/<str:branch_id>/", OrderConsumer.as_asgi()),
    path("ws/orders/stream/", OrderConsumer.as_asgi()),
    path("ws/orders/stream/<str:branch_id>/", OrderConsumer.as_asgi()),

    # Dedicated Restaurant Thermal Print Agent feed
    path("ws/printer/<str:branch_id>/", PrinterConsumer.as_asgi()),
]
