from django.urls import path

from .views import (
    NPSConfigListCreateAPIView,
    NPSConfigRetrieveUpdateDestroyAPIView,
    NPSInitiatePaymentAPIView,
    NPSInstrumentsAPIView,
    NPSServiceChargeAPIView,
    NPSStatusAPIView,
    NPSTransactionListAPIView,
    NPSTransactionRetrieveAPIView,
    NPSVerifyTransactionAPIView,
    NPSWebhookListenerAPIView,
)

urlpatterns = [
    path("nps/status/", NPSStatusAPIView.as_view(), name="nps-status"),
    path(
        "nps/config/",
        NPSConfigListCreateAPIView.as_view(),
        name="nps-config-list-create",
    ),
    path(
        "nps/config/<int:pk>/",
        NPSConfigRetrieveUpdateDestroyAPIView.as_view(),
        name="nps-config-detail",
    ),
    path("nps/instruments/", NPSInstrumentsAPIView.as_view(), name="nps-instruments"),
    path(
        "nps/service-charge/",
        NPSServiceChargeAPIView.as_view(),
        name="nps-service-charge",
    ),
    path(
        "nps/initiate/",
        NPSInitiatePaymentAPIView.as_view(),
        name="nps-initiate-payment",
    ),
    path("nps/webhook/", NPSWebhookListenerAPIView.as_view(), name="nps-webhook"),
    path(
        "nps/verify/",
        NPSVerifyTransactionAPIView.as_view(),
        name="nps-verify-transaction",
    ),
    path(
        "nps/transactions/",
        NPSTransactionListAPIView.as_view(),
        name="nps-transaction-list",
    ),
    path(
        "nps/transactions/<int:pk>/",
        NPSTransactionRetrieveAPIView.as_view(),
        name="nps-transaction-detail",
    ),
]
