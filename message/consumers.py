from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from common.permissions import ALLOWED_STAFF_ROLES
from message.models import BusinessAccount
from message.selectors.messaging_selector import (
    get_conversations_for_account,
    get_unread_counts_for_account,
)
from message.serializers import ConversationSerializer
from message.services.messaging_broadcaster import MessagingBroadcaster

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
    except Exception:
        return None
    try:
        return User.objects.select_related("branch").get(id=access_token["user_id"])
    except User.DoesNotExist:
        return None


@database_sync_to_async
def get_business_account_scope(business_account_id):
    """Return {"id", "branch_id"} for the account, or None if it is invalid/missing."""
    try:
        account_pk = int(business_account_id)
    except (TypeError, ValueError):
        return None
    return (
        BusinessAccount.objects
        .filter(id=account_pk)
        .values("id", "branch_id")
        .first()
    )


@database_sync_to_async
def fetch_initial_unread_counts(business_account_id):
    return get_unread_counts_for_account(business_account_id)


@database_sync_to_async
def fetch_initial_conversations(business_account_id):
    queryset = get_conversations_for_account(business_account_id)
    return ConversationSerializer(queryset, many=True).data


def is_authorized_for_account(user, account) -> bool:
    """Only staff/operational users may subscribe, and non-admins are limited to their own branch."""
    if not user or not getattr(user, "is_authenticated", False):
        return False

    role = getattr(user, "role", None)
    is_admin = bool(user.is_superuser or user.is_staff or role == "admin")
    if not (is_admin or role in ALLOWED_STAFF_ROLES):
        return False
    if is_admin:
        return True

    account_branch_id = account.get("branch_id")
    user_branch_id = getattr(user, "branch_id", None)
    if account_branch_id is None or user_branch_id is None:
        return False
    return str(user_branch_id) == str(account_branch_id)


class AccountScopedMessagingConsumer(AsyncJsonWebsocketConsumer):
    """Base consumer that authenticates a JWT, validates access to a single business account,

    and joins only that account's realtime group. No global/branch groups are used, so events
    never leak across accounts.
    """

    group_suffix = ""

    async def _resolve_scope(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)

        token_list = query_params.get("token", [])
        if token_list:
            user = await get_user_from_token(token_list[0])
            if user is not None:
                self.scope["user"] = user

        business_account_id = self.scope.get("url_route", {}).get("kwargs", {}).get(
            "business_account_id"
        )
        if not business_account_id or business_account_id in ["all", "None"]:
            business_account_id = (
                query_params.get("business_account_id", [None])[0]
                or query_params.get("account_id", [None])[0]
                or query_params.get("account", [None])[0]
            )

        return str(business_account_id) if business_account_id else None

    async def connect(self):
        self.business_account_id = await self._resolve_scope()
        self.group_name = None

        if not self.business_account_id:
            await self.close(code=4400)
            return

        account = await get_business_account_scope(self.business_account_id)
        if account is None:
            await self.close(code=4404)
            return

        user = self.scope.get("user")
        if not is_authorized_for_account(user, account):
            await self.close(code=4403)
            return

        self.group_name = MessagingBroadcaster.group_name(
            self.group_suffix, self.business_account_id
        )
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.on_connected()

    async def on_connected(self):
        pass

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )


class UnreadMessagesConsumer(AccountScopedMessagingConsumer):
    """WebSocket consumer for realtime unread counts and new messages of ONE business account.

    Endpoints:
      - ws://<domain>/ws/messaging/unread/account/<business_account_id>/?token=<jwt>
      - ws://<domain>/ws/messaging/unread/?business_account_id=<id>&token=<jwt>
    """

    group_suffix = "unread"

    async def on_connected(self):
        initial_counts = await fetch_initial_unread_counts(self.business_account_id)
        await self.send_json({
            "event": "unread_counts.initial",
            "business_account_id": self.business_account_id,
            "data": initial_counts,
        })

    async def new_message(self, event):
        await self.send_json({
            "event": event.get("event", "message.received"),
            "data": event.get("data", {}),
        })

    async def unread_counts_update(self, event):
        await self.send_json({
            "event": event.get("event", "unread_counts.updated"),
            "data": event.get("data", {}),
        })


class ConversationsConsumer(AccountScopedMessagingConsumer):
    """WebSocket consumer for realtime conversations of ONE business account.

    Endpoints:
      - ws://<domain>/ws/messaging/conversations/account/<business_account_id>/?token=<jwt>
      - ws://<domain>/ws/messaging/conversations/?business_account_id=<id>&token=<jwt>
    """

    group_suffix = "conversations"

    async def on_connected(self):
        initial = await fetch_initial_conversations(self.business_account_id)
        await self.send_json({
            "event": "conversations.initial",
            "business_account_id": self.business_account_id,
            "data": initial,
        })

    async def conversation_created(self, event):
        await self.send_json({
            "event": event.get("event", "conversation.created"),
            "data": event.get("data", {}),
        })

    async def conversation_updated(self, event):
        await self.send_json({
            "event": event.get("event", "conversation.updated"),
            "data": event.get("data", {}),
        })
