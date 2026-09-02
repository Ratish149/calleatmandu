from typing import Optional

from django.db.models import QuerySet

from notification.models import Notification


class NotificationSelector:
    """
    Selector layer handling optimized read queries for notifications.
    """

    @staticmethod
    def get_user_notifications(user) -> QuerySet[Notification]:
        """
        Returns notifications belonging to the specified user or global notifications.
        Optimized using select_related.
        """
        if not user or not user.is_authenticated:
            return Notification.objects.none()

        return (
            Notification.objects.filter(user=user)
            .select_related("user")
            .only(
                "id",
                "user_id",
                "title",
                "message",
                "notification_type",
                "data",
                "is_read",
                "read_at",
                "created_at",
                "updated_at",
                "user__id",
                "user__username",
                "user__email",
            )
        )

    @staticmethod
    def get_unread_count(user) -> int:
        """
        Returns total count of unread notifications for a user.
        """
        if not user or not user.is_authenticated:
            return 0
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def get_notification_by_id(user, notification_id: int) -> Optional[Notification]:
        """
        Fetches a single notification belonging to the specified user by ID.
        """
        if not user or not user.is_authenticated:
            return None
        return (
            Notification.objects.filter(id=notification_id, user=user)
            .select_related("user")
            .first()
        )
