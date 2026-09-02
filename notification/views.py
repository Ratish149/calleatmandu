from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from notification.filters import NotificationFilter
from notification.selectors.notification_selector import NotificationSelector
from notification.serializers import (
    MarkNotificationReadSerializer,
    NotificationSerializer,
)
from notification.services.notification_service import NotificationService


class NotificationPagination(PageNumberPagination):
    """
    Custom pagination class for notifications providing page-based navigation
    along with total count and total unread_count.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        unread_count = NotificationSelector.get_unread_count()
        return Response({
            "count": self.page.paginator.count,
            "unread_count": unread_count,
            "total_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })


class NotificationListAPIView(ListAPIView):
    """
    List system notifications with optional status/type filtering and search.
    Supports offline retrieval of historical notifications with custom pagination.
    """

    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = NotificationFilter
    ordering_fields = ["created_at", "is_read"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return NotificationSelector.get_all_notifications()


class NotificationDetailAPIView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a single notification.
    """

    serializer_class = NotificationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return NotificationSelector.get_all_notifications()


class NotificationMarkReadAPIView(APIView):
    """
    Single unified API endpoint to mark notifications as read.
    Accepts:
    - Single ID: {"notification_id": 10}
    - Multiple IDs: {"notification_ids": [10, 11, 12]}
    - All notifications: {"mark_all": true}
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = MarkNotificationReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        notification_id = serializer.validated_data.get("notification_id")
        notification_ids = serializer.validated_data.get("notification_ids")
        mark_all = serializer.validated_data.get("mark_all", False)

        updated_count, unread_count = NotificationService.mark_notifications_as_read(
            notification_id=notification_id,
            notification_ids=notification_ids,
            mark_all=mark_all,
        )

        return Response(
            {
                "detail": "Notification(s) marked as read successfully.",
                "updated_count": updated_count,
                "unread_count": unread_count,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)
