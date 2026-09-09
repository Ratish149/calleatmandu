import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

from tracking.selectors.tracking_selector import (
    get_active_riders_locations_qs,
    get_customer_order_tracking,
)
from tracking.serializers import (
    AdminRiderTrackingSerializer,
    CustomerOrderTrackingSerializer,
)
from tracking.services.tracking_service import (
    toggle_rider_online_status,
    update_rider_location,
)

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string: str):
    """
    Validates SimpleJWT access token string and returns the associated User instance.
    """
    try:
        access_token = AccessToken(token_string)
        user_id = access_token.get("user_id")
        return User.objects.get(id=user_id)
    except Exception as e:
        print(f"❌ [WS AUTH ERROR] Invalid token: {e}")
        return AnonymousUser()


class RiderLocationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for delivery riders to stream live GPS coordinates
    and update online/offline availability in real time.
    URL: ws://<domain>/ws/tracking/rider/?token=<jwt_access_token>
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])

        print(
            f"\n🔌 [WS RIDER CONNECT] Incoming connection attempt. Query string: {query_string}"
        )

        user = self.scope.get("user", AnonymousUser())
        if (not user or user.is_anonymous) and token_list:
            user = await get_user_from_token(token_list[0])

        if not user or user.is_anonymous or user.role not in ["rider", "admin"]:
            print(
                f"⛔ [WS RIDER REJECTED] Unauthorized user: {user} (Role: {getattr(user, 'role', 'N/A')})"
            )
            await self.close(code=4401)
            return

        self.user = user
        self.rider_group = f"rider_{self.user.id}"

        await self.channel_layer.group_add(self.rider_group, self.channel_name)
        await self.accept()

        print(
            f"✅ [WS RIDER ACCEPTED] Rider: {self.user.username} (ID: {self.user.id}, Role: {self.user.role})"
        )

        response = {
            "event": "connected",
            "message": f"Welcome rider {self.user.username}. Live tracking channel active.",
        }
        print(f"📤 [WS RIDER SENT RESPONSE] -> {json.dumps(response)}")
        await self.send_json(response)

    async def disconnect(self, close_code):
        print(
            f"🔌 [WS RIDER DISCONNECT] Rider: {getattr(self, 'user', 'Unknown')} (Code: {close_code})"
        )
        if hasattr(self, "user") and self.user and not self.user.is_anonymous:
            try:
                await database_sync_to_async(toggle_rider_online_status)(
                    rider=self.user,
                    is_online=False,
                )
                print(
                    f"🔴 [WS RIDER OFFLINE] Rider #{self.user.id} ({self.user.username}) marked offline in DB & broadcast to Admin."
                )
            except Exception as e:
                print(f"❌ [WS RIDER DISCONNECT ERROR] Failed to set offline: {e}")

        if hasattr(self, "rider_group"):
            await self.channel_layer.group_discard(self.rider_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        print(
            f"\n📥 [WS RIDER REQUEST RECEIVED] From Rider #{getattr(self.user, 'id', 'N/A')}:\n{json.dumps(content, indent=2)}"
        )

        # Support both 'action' and 'type' keys in JSON payload
        action = content.get("action") or content.get("type")

        if action in [
            "update_location",
            "location_update",
            "location",
            "update_position",
        ]:
            try:
                lat = float(content.get("latitude"))
                lng = float(content.get("longitude"))
            except (ValueError, TypeError) as e:
                err_resp = {
                    "event": "error",
                    "message": "Invalid latitude or longitude format.",
                }
                print(
                    f"❌ [WS RIDER ERROR] {e} -> Sending:\n{json.dumps(err_resp, indent=2)}"
                )
                await self.send_json(err_resp)
                return

            # Perform DB update & broadcast to Admin & Customer groups via service
            location, _ = await database_sync_to_async(update_rider_location)(
                rider=self.user,
                latitude=lat,
                longitude=lng,
            )

            ack_resp = {
                "event": "location_ack",
                "status": "success",
                "latitude": location.latitude,
                "longitude": location.longitude,
                "last_updated_at": location.last_updated_at.isoformat(),
            }
            print(f"📤 [WS RIDER RESPONSE ACK] ->\n{json.dumps(ack_resp, indent=2)}")
            await self.send_json(ack_resp)

        elif action in [
            "toggle_online",
            "rider_online",
            "rider_offline",
            "status_update",
        ]:
            if action == "rider_online":
                is_online = True
            elif action == "rider_offline":
                is_online = False
            else:
                is_online = bool(content.get("is_online", True))

            location = await database_sync_to_async(toggle_rider_online_status)(
                rider=self.user,
                is_online=is_online,
            )

            ack_resp = {
                "event": "status_ack",
                "status": "success",
                "is_online": location.is_online,
                "last_updated_at": location.last_updated_at.isoformat(),
            }
            print(f"📤 [WS RIDER RESPONSE ACK] ->\n{json.dumps(ack_resp, indent=2)}")
            await self.send_json(ack_resp)

        else:
            err_resp = {
                "event": "error",
                "message": (
                    f"Unknown action/type '{action}'. Supported values: "
                    "'update_location', 'toggle_online', 'rider_online', 'rider_offline'."
                ),
            }
            print(
                f"❌ [WS RIDER UNKNOWN ACTION] {action} -> Sending:\n{json.dumps(err_resp, indent=2)}"
            )
            await self.send_json(err_resp)


class AdminTrackingConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for Admins to view the real-time location stream
    of all active delivery riders across the platform.
    URL: ws://<domain>/ws/tracking/admin/?token=<jwt_access_token>
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])

        print(
            f"\n🔌 [WS ADMIN CONNECT] Incoming connection attempt. Query string: {query_string}"
        )

        user = self.scope.get("user", AnonymousUser())
        if (not user or user.is_anonymous) and token_list:
            user = await get_user_from_token(token_list[0])

        if not user or user.is_anonymous or user.role not in ["admin", "reception"]:
            print(
                f"⛔ [WS ADMIN REJECTED] Unauthorized user: {user} (Role: {getattr(user, 'role', 'N/A')})"
            )
            await self.close(code=4401)
            return

        self.user = user
        self.group_name = "admin_rider_tracking"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        print(
            f"✅ [WS ADMIN ACCEPTED] Admin: {self.user.username} (ID: {self.user.id})"
        )

        # Send initial snapshot of all online riders
        initial_riders_data = await self._get_initial_riders_data()
        initial_resp = {
            "event": "initial_rider_locations",
            "data": initial_riders_data,
        }
        print(
            f"📤 [WS ADMIN INITIAL SNAPSHOT SENT] Count: {len(initial_riders_data)} riders:\n{json.dumps(initial_resp, indent=2)}"
        )
        await self.send_json(initial_resp)

    async def disconnect(self, close_code):
        print(
            f"🔌 [WS ADMIN DISCONNECT] Admin: {getattr(self, 'user', 'Unknown')} (Code: {close_code})"
        )
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _get_initial_riders_data(self):
        queryset = get_active_riders_locations_qs()
        serializer = AdminRiderTrackingSerializer(queryset, many=True)
        return serializer.data

    async def rider_location_updated(self, event):
        """
        Handler for real-time rider location updates broadcast from service.
        """
        payload = {
            "event": "rider_location_updated",
            "data": event.get("data", {}),
        }
        print(f"📡 [WS ADMIN BROADCAST SENT] ->\n{json.dumps(payload, indent=2)}")
        await self.send_json(payload)

    async def rider_status_changed(self, event):
        """
        Handler for real-time rider online/offline status changes.
        """
        payload = {
            "event": "rider_status_changed",
            "data": event.get("data", {}),
        }
        print(
            f"📡 [WS ADMIN STATUS BROADCAST SENT] ->\n{json.dumps(payload, indent=2)}"
        )
        await self.send_json(payload)


class CustomerOrderTrackingConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for Customers to track live location updates
    of the rider assigned to their order.
    URL: ws://<domain>/ws/tracking/order/<order_number>/
    """

    async def connect(self):
        self.order_number = self.scope["url_route"]["kwargs"].get("order_number")
        print(
            f"\n🔌 [WS CUSTOMER CONNECT] Order Tracking Attempt for #{self.order_number}"
        )

        if not self.order_number:
            print("⛔ [WS CUSTOMER REJECTED] Missing order_number in URL path.")
            await self.close(code=4400)
            return

        self.group_name = f"order_tracking_{self.order_number}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        print(f"✅ [WS CUSTOMER ACCEPTED] Order: #{self.order_number}")

        # Send initial tracking snapshot
        snapshot = await self._get_order_tracking_snapshot()
        snapshot_resp = {
            "event": "order_tracking_snapshot",
            "data": snapshot,
        }
        print(
            f"📤 [WS CUSTOMER INITIAL SNAPSHOT SENT] Order #{self.order_number}:\n{json.dumps(snapshot_resp, indent=2)}"
        )
        await self.send_json(snapshot_resp)

    async def disconnect(self, close_code):
        print(
            f"🔌 [WS CUSTOMER DISCONNECT] Order: #{getattr(self, 'order_number', 'Unknown')} (Code: {close_code})"
        )
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _get_order_tracking_snapshot(self):
        order = get_customer_order_tracking(self.order_number)
        if not order:
            return {"error": "Order not found."}
        serializer = CustomerOrderTrackingSerializer(order)
        return serializer.data

    async def receive_json(self, content, **kwargs):
        print(
            f"\n📥 [WS CUSTOMER REQUEST RECEIVED] Order #{self.order_number}:\n{json.dumps(content, indent=2)}"
        )
        snapshot = await self._get_order_tracking_snapshot()
        response = {
            "event": "order_tracking_snapshot",
            "data": snapshot,
        }
        print(
            f"📤 [WS CUSTOMER SNAPSHOT SENT] Order #{self.order_number}:\n{json.dumps(response, indent=2)}"
        )
        await self.send_json(response)

    async def rider_location_updated(self, event):
        """
        Handler for live location updates of the assigned rider.
        Sends real-time rider GPS coordinates and order status to customer.
        """
        event_data = event.get("data", {})
        payload = {
            "event": "rider_location_updated",
            "data": event_data,
        }
        print(
            f"📡 [WS CUSTOMER BROADCAST SENT] Order #{self.order_number}:\n{json.dumps(payload, indent=2)}"
        )
        await self.send_json(payload)
