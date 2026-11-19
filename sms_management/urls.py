from django.urls import path

from sms_management.views import (
    SMSLogListCreateAPIView,
    SMSLogRetrieveUpdateDestroyAPIView,
    SMSSettingsListCreateAPIView,
    SMSSettingsRetrieveUpdateDestroyAPIView,
)

app_name = "sms_management"

urlpatterns = [
    path(
        "sms/settings/",
        SMSSettingsListCreateAPIView.as_view(),
        name="sms-settings-list",
    ),
    path(
        "sms/settings/<int:pk>/",
        SMSSettingsRetrieveUpdateDestroyAPIView.as_view(),
        name="sms-settings-detail",
    ),
    path("sms/logs/", SMSLogListCreateAPIView.as_view(), name="sms-log-list"),
    path(
        "sms/logs/<int:pk>/",
        SMSLogRetrieveUpdateDestroyAPIView.as_view(),
        name="sms-log-detail",
    ),
]
