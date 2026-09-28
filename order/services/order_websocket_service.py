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
        # payload = {
        #     "type": "print_order",
        #     "data": {
        #         "job_id": job_id,
        #         "job_type": job_type,
        #         "order": order_data,
        #     },
        # }
        # Temporarily commented out: do not send websocket messages to the printer
        # print(
        #     f"\n[WS PRINTER] ───────────────────────────────────────────"
        #     f"\n  → Printer Group : {group_name}"
        #     f"\n  → Job ID        : {job_id}"
        #     f"\n  → Job Type      : {job_type}"
        #     f"\n  → Branch        : {branch_id}"
        #     f"\n────────────────────────────────────────────────────────\n"
        # )
        # return cls._send_to_channel_layer(group_name, payload)
        logger.info(
            "WebSocket message to printer group '%s' for job '%s' (%s) is temporarily disabled.",
            group_name,
            job_id,
            job_type,
        )
        return True

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
                print(
                    f"\n[WS SEND] ──────────────────────────────────────────"
                    f"\n  → Group   : {group_name}"
                    f"\n  → Type    : {payload.get('type')}"
                    f"\n  → Event   : {payload.get('event', 'N/A')}"
                    f"\n  → Order#  : {payload.get('order_number', payload.get('data', {}).get('job_id', 'N/A'))}"
                    f"\n  → Status  : {payload.get('status', 'N/A')}"
                    f"\n────────────────────────────────────────────────────\n"
                )
                async_to_sync(channel_layer.group_send)(group_name, payload)
                print(f"[WS SENT]  ✓ Successfully sent to group: '{group_name}'\n")
                return True
        except Exception as e:
            print(f"[WS ERROR] ✗ Failed to send to group '{group_name}': {e}")
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
            print(
                f"[WS RECEIVE] broadcast_order_created — Order '{order_or_id}' not found, skipping broadcast."
            )
            return False

        print(
            f"\n[WS RECEIVE] broadcast_order_created triggered"
            f"\n  → Order#  : {order.order_number}"
            f"\n  → Status  : {order.status}"
            f"\n  → Branch  : {order.branch_id}"
            f"\n  → Target Groups: [{cls.ORDER_GROUP_ALL}, orders_branch_{order.branch_id}, {cls.ORDER_NOTIFICATIONS_GROUP}, printer_branch_{order.branch_id}]"
        )

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

        # 4. Dedicated thermal printer agent: Dispatch KOT (Temporarily commented out)
        # if order.branch_id:
        #     cls.broadcast_to_printer(
        #         branch_id=order.branch_id,
        #         job_id=f"kot_{order.order_number}",
        #         job_type="KOT",
        #         order_data=serialized_data,
        #     )

        logger.info(
            "WebSocket broadcasted 'order.created' and KOT print job for Order #%s (Branch: %s)",
            order.order_number,
            order.branch_id,
        )
        return True

    @classmethod
    def broadcast_order_ready_for_pickup(cls, order_or_id: Union[Order, int]) -> bool:
        """
        Broadcasts complete order details when the order status changes to READY_FOR_PICKUP.
        (Temporarily commented out / disabled per user request)
        """
        logger.info(
            "WebSocket broadcast for 'order_ready_for_pickup' (Order: %s) is temporarily disabled.",
            order_or_id,
        )
        print(
            f"[WS RECEIVE] broadcast_order_ready_for_pickup for Order '{order_or_id}' skipped (temporarily disabled)."
        )
        return True

        # order = cls._resolve_order(order_or_id)
        # if not order:
        #     logger.warning(
        #         "Could not broadcast order_ready_for_pickup: Order '%s' not found.",
        #         order_or_id,
        #     )
        #     print(
        #         f"[WS RECEIVE] broadcast_order_ready_for_pickup — Order '{order_or_id}' not found, skipping broadcast."
        #     )
        #     return False

        # print(
        #     f"\n[WS RECEIVE] broadcast_order_ready_for_pickup triggered"
        #     f"\n  → Order#  : {order.order_number}"
        #     f"\n  → Status  : READY_FOR_PICKUP"
        #     f"\n  → Branch  : {order.branch_id}"
        #     f"\n  → Target Groups: [{cls.ORDER_GROUP_ALL}, orders_branch_{order.branch_id}, {cls.ORDER_NOTIFICATIONS_GROUP}, printer_branch_{order.branch_id}]"
        # )

        # serialized_data = OrderResponseSerializer(order).data
        # payload = {
        #     "type": "order_ready_for_pickup",
        #     "event": "order.ready_for_pickup",
        #     "order_number": order.order_number,
        #     "status": Order.OrderStatus.READY_FOR_PICKUP,
        #     "data": serialized_data,
        # }

        # # 1. Global order feed
        # cls._send_to_channel_layer(cls.ORDER_GROUP_ALL, payload)

        # # 2. Branch-specific order feed
        # if order.branch_id:
        #     branch_group = cls.get_branch_group(order.branch_id)
        #     cls._send_to_channel_layer(branch_group, payload)

        # # 3. Notification group for backwards compatibility
        # cls._send_to_channel_layer(cls.ORDER_NOTIFICATIONS_GROUP, payload)

        # logger.info(
        #     "WebSocket broadcasted 'order.ready_for_pickup' for Order #%s (Branch: %s)",
        #     order.order_number,
        #     order.branch_id,
        # )
        # return True

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
        print(
            f"\n[WS RECEIVE] broadcast_order_status_update triggered"
            f"\n  → Order   : {order_or_id}"
            f"\n  → New Status : {new_status}"
            f"\n  → Comment : {comment or 'N/A'}"
        )

        if new_status == Order.OrderStatus.READY_FOR_PICKUP:
            print(
                "[WS RECEIVE]  ↳ Status is READY_FOR_PICKUP — WebSocket broadcast skipped (temporarily disabled)"
            )
            return True

        order = cls._resolve_order(order_or_id)
        if not order:
            print(
                f"[WS RECEIVE] broadcast_order_status_update — Order '{order_or_id}' not found, skipping broadcast."
            )
            return False

        print(
            f"[WS RECEIVE]  → Order#  : {order.order_number}"
            f"\n  → Target Groups: [{cls.ORDER_GROUP_ALL}, orders_branch_{order.branch_id}]"
        )

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
