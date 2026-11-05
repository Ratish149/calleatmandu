from django.urls import path

from customer.views import (
    CustomerFollowUpListCreateAPIView,
    CustomerFollowUpRetrieveUpdateDestroyAPIView,
    CustomerOrderActivityListAPIView,
    CustomerOrderActivityPhoneExportExcelAPIView,
)

urlpatterns = [
    path(
        "customers/order-activity/",
        CustomerOrderActivityListAPIView.as_view(),
        name="customer-order-activity",
    ),
    path(
        "customers/order-activity/export-phones/",
        CustomerOrderActivityPhoneExportExcelAPIView.as_view(),
        name="customer-order-activity-export-phones",
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
        "customers/follow-up-phone/<str:phone_number>/",
        CustomerFollowUpListCreateAPIView.as_view(),
        name="customer-followup-by-phone",
    ),
]
