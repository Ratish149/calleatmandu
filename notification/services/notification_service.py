import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from notification.serializers import OrderNotificationSerializer

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Central notification service inside notification app handling:
    Real-time WebSocket broadcasting to connected frontend clients.
    """

    @classmethod
    def send_order_notification(cls, order) -> bool:
        """
        Broadcasts concise order placement event over WebSocket channel layer.
        """
        order_data = OrderNotificationSerializer(order).data

        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "order_notifications",
                    {
                        "type": "order_created",
                        "event": "order.placed",
                        "data": order_data,
                    },
                )
                logger.info(
                    "Broadcasted order notification via WebSocket for order %s",
                    order.order_number,
                )
                return True
        except Exception as e:
            logger.error(
                "Failed to broadcast WebSocket notification for order %s: %s",
                order.order_number,
                str(e),
            )
            return False
