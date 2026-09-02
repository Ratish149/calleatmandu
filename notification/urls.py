from django.urls import path

from notification.views import (
    NotificationDetailAPIView,
    NotificationListAPIView,
    NotificationMarkReadAPIView,
)

urlpatterns = [
    path("notifications/", NotificationListAPIView.as_view(), name="notification-list"),
    path(
        "notifications/mark-read/",
        NotificationMarkReadAPIView.as_view(),
        name="notification-mark-read",
    ),
    path(
        "notifications/<int:pk>/",
        NotificationDetailAPIView.as_view(),
        name="notification-detail",
    ),
]
