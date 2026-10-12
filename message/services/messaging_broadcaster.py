import logging
from typing import Optional, Union

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from message.models import Conversation, Message
from message.selectors.messaging_selector import get_unread_counts_for_account
from message.serializers import ConversationSerializer, MessageSerializer

logger = logging.getLogger(__name__)


class MessagingBroadcaster:
    """Service to broadcast real-time messaging events (messages, unread counts, and conversations)

    to the WebSocket group of the specific business account the event belongs to.

    Events are only ever delivered to clients subscribed to that exact business account. They are
    never fanned out to other accounts or to a branch/global group.
    """

    @staticmethod
    def group_name(suffix: str, business_account_id: Union[int, str]) -> str:
        return f"messaging_{suffix}_account_{business_account_id}"

    @staticmethod
    def unread_group_name(business_account_id: Union[int, str]) -> str:
        return MessagingBroadcaster.group_name("unread", business_account_id)

    @staticmethod
    def conversations_group_name(business_account_id: Union[int, str]) -> str:
        return MessagingBroadcaster.group_name("conversations", business_account_id)

    @staticmethod
    def _account_group_id(conversation: Conversation) -> Optional[str]:
        account_id = conversation.business_account_id
        return str(account_id) if account_id else None

    @staticmethod
    def _send_to_channel_layer(group_name: str, payload: dict):
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(group_name, payload)
        except Exception as exc:
            logger.warning(
                f"Failed to broadcast on group {group_name}: {exc}",
                exc_info=True,
            )

    @classmethod
    def broadcast_new_message(
        cls,
        message: Message,
        conversation: Conversation,
        event_name: str = "message.received",
    ):
        """Broadcasts a new message (inbound or outbound) and the updated unread counts map

        to connected clients subscribed to the conversation's business account.
        """
        account_id = cls._account_group_id(conversation)
        if not account_id:
            logger.debug(
                "Skipping message broadcast: conversation %s has no business account",
                conversation.pk,
            )
            return

        unread_counts = get_unread_counts_for_account(account_id)
        message_data = MessageSerializer(message).data

        payload = {
            "type": "new_message",
            "event": event_name,
            "data": {
                "message": message_data,
                "conversation_id": str(conversation.id),
                "business_account_id": account_id,
                "unread_counts": unread_counts,
            },
        }

        cls._send_to_channel_layer(cls.unread_group_name(account_id), payload)

    @classmethod
    def broadcast_unread_counts_updated(
        cls,
        business_account_id: Optional[Union[int, str]] = None,
        conversation_id: Optional[str] = None,
    ):
        """Broadcasts an updated unread counts map (e.g. after mark-as-read)

        to connected clients subscribed to the given business account.
        """
        if not business_account_id:
            return

        unread_counts = get_unread_counts_for_account(business_account_id)

        payload = {
            "type": "unread_counts_update",
            "event": "unread_counts.updated",
            "data": {
                "business_account_id": str(business_account_id),
                "conversation_id": str(conversation_id) if conversation_id else None,
                "unread_counts": unread_counts,
            },
        }

        cls._send_to_channel_layer(
            cls.unread_group_name(business_account_id), payload
        )

    @classmethod
    def broadcast_conversation_created(cls, conversation: Conversation):
        """Notifies clients subscribed to the conversation's business account that a new conversation exists."""
        account_id = cls._account_group_id(conversation)
        if not account_id:
            return

        conv_data = ConversationSerializer(conversation).data

        payload = {
            "type": "conversation_created",
            "event": "conversation.created",
            "data": conv_data,
        }

        cls._send_to_channel_layer(
            cls.conversations_group_name(account_id), payload
        )

    @classmethod
    def broadcast_conversation_updated(cls, conversation: Conversation):
        """Notifies clients subscribed to the conversation's business account that it changed."""
        account_id = cls._account_group_id(conversation)
        if not account_id:
            return

        conv_data = ConversationSerializer(conversation).data

        payload = {
            "type": "conversation_updated",
            "event": "conversation.updated",
            "data": conv_data,
        }

        cls._send_to_channel_layer(
            cls.conversations_group_name(account_id), payload
        )
