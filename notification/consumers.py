import json

from channels.generic.websocket import AsyncWebsocketConsumer


class OrderNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time order notifications.
    Frontend connects to: ws://<domain>/ws/orders/
    """

    async def connect(self):
        self.group_name = "order_notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @staticmethod
    def _is_pos_order(event: dict) -> bool:
        """
        Checks if the event corresponds to a POS order (is_pos_order is True).
        """
        is_pos = event.get("is_pos_order")
        if is_pos is None:
            data = event.get("data", {})
            if isinstance(data, dict):
                is_pos = data.get("is_pos_order", False)
                if not is_pos and isinstance(data.get("order"), dict):
                    is_pos = data["order"].get("is_pos_order", False)
                elif not is_pos and isinstance(data.get("data"), dict):
                    is_pos = data["data"].get("is_pos_order", False)
        return bool(is_pos is True or str(is_pos).lower() == "true")

    async def order_created(self, event):
        """
        Broadcasts order notification payload to connected WebSocket clients.
        Skips POS orders (is_pos_order is True).
        """
        if self._is_pos_order(event):
            return

        await self.send(
            text_data=json.dumps({
                "event": event.get("event", "order.placed"),
                "order_number": event.get("order_number"),
                "status": event.get("status"),
                "data": event.get("data", {}),
            })
        )

    async def order_ready_for_pickup(self, event):
        """
        Broadcasts ready for pickup payload to connected WebSocket clients.
        Skips POS orders (is_pos_order is True).
        """
        if self._is_pos_order(event):
            return

        await self.send(
            text_data=json.dumps({
                "event": event.get("event", "order.ready_for_pickup"),
                "order_number": event.get("order_number"),
                "status": event.get("status", "READY_FOR_PICKUP"),
                "data": event.get("data", {}),
            })
        )

    async def order_status_updated(self, event):
        """
        Broadcasts order status update payload to connected WebSocket clients.
        Skips POS orders (is_pos_order is True).
        """
        if self._is_pos_order(event):
            return

        await self.send(
            text_data=json.dumps({
                "event": event.get("event", "order.status_updated"),
                "order_number": event.get("order_number"),
                "status": event.get("status"),
                "data": event.get("data", {}),
            })
        )
