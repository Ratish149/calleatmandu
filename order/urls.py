from django.urls import path

from order.views import (
    AssignRiderAPIView,
    CustomerOrderHistoryAPIView,
    OrderListCreateAPIView,
    OrderRetrieveUpdateDestroyAPIView,
    OrderStatusUpdateAPIView,
    POSOrderListCreateAPIView,
    PublicOrderUpdateAPIView,
    RecentOrdersAPIView,
)

urlpatterns = [
    path("orders/", OrderListCreateAPIView.as_view(), name="order-list-create"),
    path(
        "orders/recent/",
        RecentOrdersAPIView.as_view(),
        name="recent-orders",
    ),
    path(
        "orders/customer/<int:customer_id>/",
        CustomerOrderHistoryAPIView.as_view(),
        name="customer-order-history",
    ),
    path(
        "orders/pos/", POSOrderListCreateAPIView.as_view(), name="pos-order-list-create"
    ),
    path(
        "orders/assign-rider/",
        AssignRiderAPIView.as_view(),
        name="order-assign-rider",
    ),
    path(
        "orders/update-status/",
        OrderStatusUpdateAPIView.as_view(),
        name="order-update-status-body",
    ),
    path(
        "orders/<str:order_number>/update-public/",
        PublicOrderUpdateAPIView.as_view(),
        name="order-update-public",
    ),
    path(
        "orders/<str:order_number>/status/",
        OrderStatusUpdateAPIView.as_view(),
        name="order-update-status",
    ),
    path(
        "orders/<str:order_number>/",
        OrderRetrieveUpdateDestroyAPIView.as_view(),
        name="order-detail",
    ),
]
