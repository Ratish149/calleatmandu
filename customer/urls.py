from django.urls import path

from customer.views import (
    CustomerFollowUpListCreateAPIView,
    CustomerFollowUpRetrieveUpdateDestroyAPIView,
    CustomerOrderActivityListAPIView,
)

urlpatterns = [
    path(
        "customers/order-activity/",
        CustomerOrderActivityListAPIView.as_view(),
        name="customer-order-activity",
    ),
    path(
        "customers/activity/",
        CustomerOrderActivityListAPIView.as_view(),
        name="customer-activity-alias",
    ),
    path(
        "customers/follow-ups/",
        CustomerFollowUpListCreateAPIView.as_view(),
        name="customer-followup-list-create",
    ),
    path(
        "customers/follow-ups/<int:pk>/",
        CustomerFollowUpRetrieveUpdateDestroyAPIView.as_view(),
        name="customer-followup-detail",
    ),
    path(
        "customers/follow-ups/by-phone/<str:phone_number>/",
        CustomerFollowUpListCreateAPIView.as_view(),
        name="customer-followup-by-phone",
    ),
]
