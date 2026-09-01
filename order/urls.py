from django.urls import path

from order.views import (
    AssignRiderAPIView,
    OrderListCreateAPIView,
    OrderRetrieveUpdateDestroyAPIView,
    POSOrderListCreateAPIView,
)

urlpatterns = [
    path("orders/", OrderListCreateAPIView.as_view(), name="order-list-create"),
    path(
        "orders/pos/", POSOrderListCreateAPIView.as_view(), name="pos-order-list-create"
    ),
    path(
        "orders/assign-rider/",
        AssignRiderAPIView.as_view(),
        name="order-assign-rider",
    ),
    path(
        "orders/<str:order_number>/",
        OrderRetrieveUpdateDestroyAPIView.as_view(),
        name="order-detail",
    ),
]
