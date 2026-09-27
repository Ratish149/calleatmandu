import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

from order.services.order_websocket_service import OrderWebSocketService

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string: str):
    """
    Validates SimpleJWT access token string and returns the associated User instance.
    """
    try:
        access_token = AccessToken(token_string)
        user_id = access_token.get("user_id")
        return User.objects.select_related("branch").get(id=user_id)
    except Exception as e:
        logger.debug("Failed validating JWT in WebSocket: %s", str(e))
        return AnonymousUser()


class OrderConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time order lifecycle events.
    Endpoints:
      - ws://<domain>/ws/order/
      - ws://<domain>/ws/order/<branch_id>/
      - ws://<domain>/ws/orders/live/
      - ws://<domain>/ws/orders/live/<branch_id>/
    Query params supported:
      - ?token=<jwt_access_token> (Optional, for authenticated sessions)
      - ?branch_id=<branch_id> (Optional, scopes events to specific branch)
    Events broadcasted to connected clients:
      1. {"event": "order.created", "order_number": "...", "status": "...", "data": {...}}
      2. {"event": "order.ready_for_pickup", "order_number": "...", "status": "READY_FOR_PICKUP", "data": {...}}
      3. {"event": "order.status_updated", "order_number": "...", "status": "...", "data": {...}}
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)

        # 1. Resolve authentication (JWT in query string or session)
        token_list = query_params.get("token", [])
        user = self.scope.get("user")
        if token_list:
            user = await get_user_from_token(token_list[0])
            self.scope["user"] = user
        elif not user:
            user = AnonymousUser()
        self.user = user

        # 2. Resolve branch_id from URL kwargs, query params, or authenticated user
        branch_id = self.scope.get("url_route", {}).get("kwargs", {}).get("branch_id")
        if not branch_id or branch_id in ["all", "None"]:
            branch_id = (
                query_params.get("branch_id", [None])[0]
                or query_params.get("branch", [None])[0]
            )

        if not branch_id and user and user.is_authenticated and getattr(user, "branch_id", None):
            branch_id = str(user.branch_id)

        self.branch_id = str(branch_id) if branch_id else None

        # 3. Determine Channel Layer group
        if self.branch_id:
            self.group_name = OrderWebSocketService.get_branch_group(self.branch_id)
        else:
            self.group_name = OrderWebSocketService.ORDER_GROUP_ALL

        # Join the channel layer group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(
            "OrderConsumer connected: channel=%s, group=%s, branch_id=%s, user=%s",
            self.channel_name,
            self.group_name,
            self.branch_id,
            getattr(self.user, "username", "Anonymous"),
        )

        # Send connection confirmation payload
        await self.send_json({
            "event": "connection_established",
            "message": "Connected to order real-time stream.",
            "group": self.group_name,
            "branch_id": self.branch_id,
        })

    async def disconnect(self, close_code):
        if hasattr(self, "group_name") and self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(
            "OrderConsumer disconnected: channel=%s, code=%s",
            getattr(self, "channel_name", "N/A"),
            close_code,
        )

    async def receive_json(self, content, **kwargs):
        """
        Handle incoming client messages (e.g. heartbeat ping/pong).
        """
        action = content.get("action") or content.get("type")
        if action == "ping":
            await self.send_json({"event": "pong", "message": "pong"})

    # -------------------------------------------------------------------------
    # Channel Layer Group Event Handlers
    # -------------------------------------------------------------------------

    async def order_created(self, event):
        """
        Dispatched when an order is created. Sends full order details to the client.
        """
        await self.send_json({
            "event": event.get("event", "order.created"),
            "order_number": event.get("order_number"),
            "status": event.get("status"),
            "data": event.get("data", {}),
        })

    async def order_ready_for_pickup(self, event):
        """
        Dispatched when an order status changes to READY_FOR_PICKUP.
        Sends full order details to the client.
        """
        await self.send_json({
            "event": event.get("event", "order.ready_for_pickup"),
            "order_number": event.get("order_number"),
            "status": event.get("status", "READY_FOR_PICKUP"),
            "data": event.get("data", {}),
        })

    async def order_status_updated(self, event):
        """
        Dispatched on generic order status transitions.
        """
        await self.send_json({
            "event": event.get("event", "order.status_updated"),
            "order_number": event.get("order_number"),
            "status": event.get("status"),
            "comment": event.get("comment"),
            "data": event.get("data", {}),
        })


class PrinterConsumer(AsyncJsonWebsocketConsumer):
    """
    Dedicated WebSocket consumer for Restaurant Thermal Print Agent.
    Endpoints:
      - ws://<domain>/ws/printer/<branch_id>/
      - wss://<domain>/ws/printer/<branch_id>/

    Automatically binds the connection to printer_branch_{branch_id}
    channel layer group without requiring authentication tokens or printer IDs.
    """

    async def connect(self):
        self.branch_id = self.scope.get("url_route", {}).get("kwargs", {}).get("branch_id")
        self.group_name = None

        if not self.branch_id:
            logger.warning("PrinterConsumer rejected: missing branch_id in URL path.")
            await self.close(code=4000)
            return

        self.branch_id = str(self.branch_id)
        self.group_name = OrderWebSocketService.get_printer_branch_group(self.branch_id)

        # Join the dedicated printer channel layer group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(
            "Printer Agent connected directly for branch %s (Group: %s)",
            self.branch_id,
            self.group_name,
        )

        await self.send_json({
            "type": "connected",
            "message": f"Connected to printer stream for branch {self.branch_id}",
            "branch_id": self.branch_id,
        })

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(
            "Printer Agent disconnected: branch=%s, code=%s",
            getattr(self, "branch_id", "N/A"),
            close_code,
        )

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")

        # 1. Print Acknowledgement from Agent
        if msg_type == "print_ack":
            job_id = content.get("job_id")
            success = content.get("success", False)
            error = content.get("error")
            logger.info(
                "Printer ACK received: branch=%s, job=%s, success=%s, error=%s",
                self.branch_id,
                job_id,
                success,
                error,
            )

        # 2. Heartbeat
        elif msg_type in ("ping", "heartbeat"):
            await self.send_json({"type": "pong"})

    # -------------------------------------------------------------------------
    # Channel Layer Group Handler
    # -------------------------------------------------------------------------

    async def print_order(self, event):
        """
        Dispatched by OrderWebSocketService.broadcast_to_printer.
        Sends print_order payload to the connected printer agent.
        """
        payload_data = event.get("data", {})
        await self.send_json({
            "type": "print_order",
            "job_id": payload_data.get("job_id"),
            "job_type": payload_data.get("job_type", "KOT"),
            "order": payload_data.get("order", {}),
        })
