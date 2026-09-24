from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

from message.selectors.messaging_selector import (
    get_conversations_for_branch,
    get_unread_counts_for_branch,
)
from message.serializers import ConversationSerializer

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string: str):
    """Validates SimpleJWT access token string and returns the associated User instance."""
    try:
        access_token = AccessToken(token_string)
        user_id = access_token.get("user_id")
        return User.objects.select_related("branch").get(id=user_id)
    except Exception:
        return AnonymousUser()


@database_sync_to_async
def fetch_initial_unread_counts(branch_id):
    return get_unread_counts_for_branch(branch_id)


@database_sync_to_async
def fetch_initial_conversations(branch_id):
    qs = get_conversations_for_branch(branch_id=branch_id)
    return ConversationSerializer(qs, many=True).data


class UnreadMessagesConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for real-time unread counts and message arrival notifications.

    Endpoints:
      - ws://<domain>/ws/messaging/unread/<branch_id>/?token=<jwt_access_token>
      - ws://<domain>/ws/messaging/unread/?branch_id=<branch_id>&token=<jwt_access_token>
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)

        # Authenticate via JWT token if passed in query string
        token_list = query_params.get("token", [])
        user = self.scope.get("user")
        if token_list:
            user = await get_user_from_token(token_list[0])
            self.scope["user"] = user

        # Resolve branch_id from URL kwargs, query params, or user token
        branch_id = self.scope.get("url_route", {}).get("kwargs", {}).get("branch_id")
        if not branch_id or branch_id in ["all", "None"]:
            branch_id = (
                query_params.get("branch_id", [None])[0]
                or query_params.get("branch", [None])[0]
            )

        if not branch_id and user and user.is_authenticated and getattr(user, "branch_id", None):
            branch_id = str(user.branch_id)

        self.branch_id = str(branch_id) if branch_id else None
        self.branch_group = (
            f"messaging_unread_branch_{self.branch_id}"
            if self.branch_id
            else None
        )
        self.all_group = "messaging_unread_all"

        if self.branch_group:
            await self.channel_layer.group_add(self.branch_group, self.channel_name)
        await self.channel_layer.group_add(self.all_group, self.channel_name)

        await self.accept()

        # Send initial unread counts to the client immediately upon connection
        initial_counts = await fetch_initial_unread_counts(self.branch_id)
        await self.send_json({
            "event": "unread_counts.initial",
            "branch_id": self.branch_id,
            "data": initial_counts,
        })

    async def disconnect(self, close_code):
        if self.branch_group:
            await self.channel_layer.group_discard(
                self.branch_group, self.channel_name
            )
        await self.channel_layer.group_discard(self.all_group, self.channel_name)

    async def new_message(self, event):
        """Dispatched when a new inbound/outbound message arrives."""
        await self.send_json({
            "event": event.get("event", "message.received"),
            "data": event.get("data", {}),
        })

    async def unread_counts_update(self, event):
        """Dispatched when unread counts are updated (e.g. mark-as-read)."""
        await self.send_json({
            "event": event.get("event", "unread_counts.updated"),
            "data": event.get("data", {}),
        })


class ConversationsConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for real-time conversation notifications (new conversations and updates).

    Endpoints:
      - ws://<domain>/ws/messaging/conversations/<branch_id>/?token=<jwt_access_token>
      - ws://<domain>/ws/messaging/conversations/?branch_id=<branch_id>&token=<jwt_access_token>
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)

        # Authenticate via JWT token if passed in query string
        token_list = query_params.get("token", [])
        user = self.scope.get("user")
        if token_list:
            user = await get_user_from_token(token_list[0])
            self.scope["user"] = user

        # Resolve branch_id from URL kwargs, query params, or user token
        branch_id = self.scope.get("url_route", {}).get("kwargs", {}).get("branch_id")
        if not branch_id or branch_id in ["all", "None"]:
            branch_id = (
                query_params.get("branch_id", [None])[0]
                or query_params.get("branch", [None])[0]
            )

        if not branch_id and user and user.is_authenticated and getattr(user, "branch_id", None):
            branch_id = str(user.branch_id)

        self.branch_id = str(branch_id) if branch_id else None
        self.branch_group = (
            f"messaging_conversations_branch_{self.branch_id}"
            if self.branch_id
            else None
        )
        self.all_group = "messaging_conversations_all"

        if self.branch_group:
            await self.channel_layer.group_add(self.branch_group, self.channel_name)
        await self.channel_layer.group_add(self.all_group, self.channel_name)

        await self.accept()

        # Send initial conversation list to the client upon connection
        initial_conversations = await fetch_initial_conversations(self.branch_id)
        await self.send_json({
            "event": "conversations.initial",
            "branch_id": self.branch_id,
            "data": initial_conversations,
        })

    async def disconnect(self, close_code):
        if self.branch_group:
            await self.channel_layer.group_discard(
                self.branch_group, self.channel_name
            )
        await self.channel_layer.group_discard(self.all_group, self.channel_name)

    async def conversation_created(self, event):
        """Dispatched when a new conversation is created."""
        await self.send_json({
            "event": event.get("event", "conversation.created"),
            "data": event.get("data", {}),
        })

    async def conversation_updated(self, event):
        """Dispatched when an existing conversation has new message/unread update."""
        await self.send_json({
            "event": event.get("event", "conversation.updated"),
            "data": event.get("data", {}),
        })
