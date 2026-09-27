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

    async def order_created(self, event):
        """
        Broadcasts order notification payload to connected WebSocket clients.
        """
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
        """
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
        """
        await self.send(
            text_data=json.dumps({
                "event": event.get("event", "order.status_updated"),
                "order_number": event.get("order_number"),
                "status": event.get("status"),
                "data": event.get("data", {}),
            })
        )

