import logging
from typing import List, Optional, Tuple

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from notification.models import Notification
from notification.selectors.notification_selector import NotificationSelector
from notification.serializers import OrderNotificationSerializer

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service layer handling notification creation, persistence, WebSocket broadcasting,
    and batch/single mark-as-read operations.
    """

    @classmethod
    def create_notification(
        cls,
        title: str = "",
        message: str = "",
        notification_type: str = "order_update",
        data: Optional[dict] = None,
    ) -> Notification:
        """
        Creates and saves a Notification record to database, then broadcasts over WebSocket.
        """
        if data is None:
            data = {}

        notification = Notification.objects.create(
            title=title,
            message=message,
            notification_type=notification_type,
            data=data,
        )

        cls._broadcast_via_websocket(notification)
        return notification

    @classmethod
    def _broadcast_via_websocket(cls, notification: Notification) -> bool:
        """
        Helper method to push real-time notification payload over WebSocket channel layer.
        """
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                payload = {
                    "type": "order_created",
                    "event": f"notification.{notification.notification_type}",
                    "data": {
                        "id": notification.id,
                        "title": notification.title,
                        "message": notification.message,
                        "notification_type": notification.notification_type,
                        "data": notification.data,
                        "created_at": notification.created_at.isoformat(),
                    },
                }
                async_to_sync(channel_layer.group_send)(
                    "order_notifications", payload
                )
                logger.info(
                    "Broadcasted notification ID %s via WebSocket", notification.id
                )
                return True
        except Exception as e:
            logger.error(
                "Failed to broadcast WebSocket notification ID %s: %s",
                notification.id,
                str(e),
            )
        return False

    @classmethod
    def send_order_notification(cls, order) -> bool:
        """
        Broadcasts order notification over WebSocket and persists Notification record in database.
        """
        order_data = OrderNotificationSerializer(order).data
        title = f"New Order #{order.order_number}"
        message = f"Order of Rs. {order.total_amount} placed by {order.customer_name}"

        # Persist notification in database & broadcast via WebSocket
        notification = cls.create_notification(
            title=title,
            message=message,
            notification_type="order_placed",
            data=order_data,
        )
        return notification is not None

    @classmethod
    def mark_notifications_as_read(
        cls,
        notification_id: Optional[int] = None,
        notification_ids: Optional[List[int]] = None,
        mark_all: bool = False,
    ) -> Tuple[int, int]:
        """
        Marks single notification, multiple notifications, or all notifications as read.
        Returns a tuple of (updated_count, unread_count).
        """
        qs = Notification.objects.filter(is_read=False)

        if mark_all:
            # Mark all unread notifications as read
            updated_count = qs.update(is_read=True, read_at=timezone.now())
        elif notification_ids:
            # Mark multiple specific IDs as read
            updated_count = qs.filter(id__in=notification_ids).update(
                is_read=True, read_at=timezone.now()
            )
        elif notification_id is not None:
            # Mark a single ID as read
            updated_count = qs.filter(id=notification_id).update(
                is_read=True, read_at=timezone.now()
            )
        else:
            updated_count = 0

        unread_count = NotificationSelector.get_unread_count()
        return updated_count, unread_count
