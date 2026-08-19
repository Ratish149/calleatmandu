from django.urls import path

from order.views import (
    OrderListCreateAPIView,
    OrderRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("orders/", OrderListCreateAPIView.as_view(), name="order-list-create"),
    path(
        "orders/<str:order_number>/",
        OrderRetrieveUpdateDestroyAPIView.as_view(),
        name="order-detail",
    ),
]
