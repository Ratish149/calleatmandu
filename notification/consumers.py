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
                "data": event.get("data", {}),
            })
        )
