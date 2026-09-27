import logging
from typing import Optional, Union

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from order.models import Order
from order.selectors.order_selector import get_order_by_id_with_relations
from order.serializers import OrderResponseSerializer

logger = logging.getLogger(__name__)


class OrderWebSocketService:
    """
    Dedicated service for broadcasting real-time order events over Django Channels WebSockets.
    Dispatches:
      1. order.created: when an order is first created (with complete item and financial details)
      2. order.ready_for_pickup: when an order status changes to READY_FOR_PICKUP
      3. order.status_updated: when any order status transition occurs
    """

    ORDER_GROUP_ALL = "orders_all"
    ORDER_NOTIFICATIONS_GROUP = "order_notifications"

    @classmethod
    def get_branch_group(cls, branch_id: Union[int, str]) -> str:
        return f"orders_branch_{branch_id}"

    @classmethod
    def get_printer_branch_group(cls, branch_id: Union[int, str]) -> str:
        """Dedicated Channel Layer group for thermal printer agents of a branch."""
        return f"printer_branch_{branch_id}"

    @classmethod
    def broadcast_to_printer(
        cls,
        branch_id: Union[int, str],
        job_id: Union[int, str],
        job_type: str,
        order_data: dict,
    ) -> bool:
        """
        Dispatches print_order message directly to the dedicated printer agent group:
        printer_branch_{branch_id}
        """
        group_name = cls.get_printer_branch_group(branch_id)
        payload = {
            "type": "print_order",
            "data": {
                "job_id": job_id,
                "job_type": job_type,
                "order": order_data,
            },
        }
        return cls._send_to_channel_layer(group_name, payload)

    @classmethod
    def _resolve_order(cls, order_or_id: Union[Order, int]) -> Optional[Order]:
        """
        Resolves an Order model instance with all optimized select_related and
        prefetch_related objects loaded to prevent N+1 queries during serialization.
        """
        if isinstance(order_or_id, Order):
            order_id = order_or_id.id
        else:
            order_id = order_or_id

        return get_order_by_id_with_relations(order_id)

    @classmethod
    def _send_to_channel_layer(cls, group_name: str, payload: dict) -> bool:
        """
        Safely dispatches payload to a Channel Layer group using async_to_sync.
        """
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(group_name, payload)
                return True
        except Exception as e:
            logger.error(
                "Failed sending WebSocket message to group '%s': %s",
                group_name,
                str(e),
                exc_info=True,
            )
        return False

    @classmethod
    def broadcast_order_created(cls, order_or_id: Union[Order, int]) -> bool:
        """
        Broadcasts complete order data when an order is created.
        Sends to:
          - 'orders_all': Global order stream for master dashboards/kitchens
          - 'orders_branch_<id>': Scoped order stream for the assigned branch
          - 'order_notifications': Compatibility stream for notification subscribers
        """
        order = cls._resolve_order(order_or_id)
        if not order:
            logger.warning(
                "Could not broadcast order_created: Order '%s' not found.", order_or_id
            )
            return False

        serialized_data = OrderResponseSerializer(order).data
        payload = {
            "type": "order_created",
            "event": "order.created",
            "order_number": order.order_number,
            "status": order.status,
            "data": serialized_data,
        }

        # 1. Global order feed
        cls._send_to_channel_layer(cls.ORDER_GROUP_ALL, payload)

        # 2. Branch-specific order feed
        if order.branch_id:
            branch_group = cls.get_branch_group(order.branch_id)
            cls._send_to_channel_layer(branch_group, payload)

        # 3. Notification group for backwards compatibility
        cls._send_to_channel_layer(cls.ORDER_NOTIFICATIONS_GROUP, payload)

        # 4. Dedicated thermal printer agent: Dispatch KOT
        if order.branch_id:
            cls.broadcast_to_printer(
                branch_id=order.branch_id,
                job_id=f"kot_{order.order_number}",
                job_type="KOT",
                order_data=serialized_data,
            )

        logger.info(
            "WebSocket broadcasted 'order.created' and KOT print job for Order #%s (Branch: %s)",
            order.order_number,
            order.branch_id,
        )
        return True

    @classmethod
    def broadcast_order_ready_for_pickup(
        cls, order_or_id: Union[Order, int]
    ) -> bool:
        """
        Broadcasts complete order details when the order status changes to READY_FOR_PICKUP.
        Sends to:
          - 'orders_all': Global order stream (riders, managers, counter)
          - 'orders_branch_<id>': Scoped order stream for the assigned branch
          - 'order_notifications': Compatibility stream for notification subscribers
          - 'printer_branch_<id>': Customer Bill to dedicated thermal printer agent
        """
        order = cls._resolve_order(order_or_id)
        if not order:
            logger.warning(
                "Could not broadcast order_ready_for_pickup: Order '%s' not found.",
                order_or_id,
            )
            return False

        serialized_data = OrderResponseSerializer(order).data
        payload = {
            "type": "order_ready_for_pickup",
            "event": "order.ready_for_pickup",
            "order_number": order.order_number,
            "status": Order.OrderStatus.READY_FOR_PICKUP,
            "data": serialized_data,
        }

        # 1. Global order feed
        cls._send_to_channel_layer(cls.ORDER_GROUP_ALL, payload)

        # 2. Branch-specific order feed
        if order.branch_id:
            branch_group = cls.get_branch_group(order.branch_id)
            cls._send_to_channel_layer(branch_group, payload)

        # 3. Notification group for backwards compatibility
        cls._send_to_channel_layer(cls.ORDER_NOTIFICATIONS_GROUP, payload)

        # 4. Dedicated thermal printer agent: Dispatch Customer Bill
        if order.branch_id:
            cls.broadcast_to_printer(
                branch_id=order.branch_id,
                job_id=f"bill_{order.order_number}",
                job_type="BILL",
                order_data=serialized_data,
            )

        logger.info(
            "WebSocket broadcasted 'order.ready_for_pickup' and Customer Bill for Order #%s (Branch: %s)",
            order.order_number,
            order.branch_id,
        )
        return True

    @classmethod
    def broadcast_order_status_update(
        cls,
        order_or_id: Union[Order, int],
        new_status: str,
        comment: Optional[str] = None,
    ) -> bool:
        """
        General broadcaster for any status update.
        If target status is READY_FOR_PICKUP, delegates to broadcast_order_ready_for_pickup.
        Otherwise sends order.status_updated.
        """
        if new_status == Order.OrderStatus.READY_FOR_PICKUP:
            return cls.broadcast_order_ready_for_pickup(order_or_id)

        order = cls._resolve_order(order_or_id)
        if not order:
            return False

        serialized_data = OrderResponseSerializer(order).data
        payload = {
            "type": "order_status_updated",
            "event": "order.status_updated",
            "order_number": order.order_number,
            "status": new_status,
            "comment": comment,
            "data": serialized_data,
        }

        cls._send_to_channel_layer(cls.ORDER_GROUP_ALL, payload)
        if order.branch_id:
            cls._send_to_channel_layer(cls.get_branch_group(order.branch_id), payload)

        return True
