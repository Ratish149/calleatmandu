from typing import Optional

from django.db.models import QuerySet

from notification.models import Notification


class NotificationSelector:
    """
    Selector layer handling optimized read queries for notifications.
    """

    @staticmethod
    def get_all_notifications() -> QuerySet[Notification]:
        """
        Returns all system notifications optimized with .only().
        """
        return Notification.objects.only(
            "id",
            "title",
            "message",
            "notification_type",
            "data",
            "is_read",
            "read_at",
            "created_at",
            "updated_at",
        )

    @staticmethod
    def get_unread_count() -> int:
        """
        Returns total count of unread notifications.
        """
        return Notification.objects.filter(is_read=False).count()

    @staticmethod
    def get_notification_by_id(notification_id: int) -> Optional[Notification]:
        """
        Fetches a single notification by ID.
        """
        return Notification.objects.filter(id=notification_id).first()
