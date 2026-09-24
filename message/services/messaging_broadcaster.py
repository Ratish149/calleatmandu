import logging
from typing import Optional, Union

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from message.models import Conversation, Message
from message.selectors.messaging_selector import get_unread_counts_for_branch
from message.serializers import ConversationSerializer, MessageSerializer

logger = logging.getLogger(__name__)


class MessagingBroadcaster:
    """Service to broadcast real-time messaging events (messages, unread counts, and conversations)

    via Django Channels to branch-specific and global WebSocket groups.
    """

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

        to connected clients on the unread/messages WebSocket.
        """
        branch_id = conversation.branch_id or (
            conversation.business_account.branch_id
            if conversation.business_account
            else None
        )
        unread_counts = get_unread_counts_for_branch(branch_id)
        message_data = MessageSerializer(message).data

        payload = {
            "type": "new_message",
            "event": event_name,
            "data": {
                "message": message_data,
                "conversation_id": str(conversation.id),
                "branch_id": branch_id,
                "unread_counts": unread_counts,
            },
        }

        # Send to branch group
        if branch_id:
            cls._send_to_channel_layer(
                f"messaging_unread_branch_{branch_id}", payload
            )

        # Also send to global/admin group
        cls._send_to_channel_layer("messaging_unread_all", payload)

    @classmethod
    def broadcast_unread_counts_updated(
        cls,
        branch_id: Optional[Union[int, str]] = None,
        conversation_id: Optional[str] = None,
    ):
        """Broadcasts an updated unread counts map (e.g. after mark-as-read)

        to the unread/messages WebSocket.
        """
        unread_counts = get_unread_counts_for_branch(branch_id)

        payload = {
            "type": "unread_counts_update",
            "event": "unread_counts.updated",
            "data": {
                "branch_id": branch_id,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "unread_counts": unread_counts,
            },
        }

        if branch_id:
            cls._send_to_channel_layer(
                f"messaging_unread_branch_{branch_id}", payload
            )

        cls._send_to_channel_layer("messaging_unread_all", payload)

    @classmethod
    def broadcast_conversation_created(cls, conversation: Conversation):
        """Notifies connected clients on the conversations WebSocket that a new conversation has been created."""
        branch_id = conversation.branch_id or (
            conversation.business_account.branch_id
            if conversation.business_account
            else None
        )
        conv_data = ConversationSerializer(conversation).data

        payload = {
            "type": "conversation_created",
            "event": "conversation.created",
            "data": conv_data,
        }

        if branch_id:
            cls._send_to_channel_layer(
                f"messaging_conversations_branch_{branch_id}", payload
            )

        cls._send_to_channel_layer("messaging_conversations_all", payload)

    @classmethod
    def broadcast_conversation_updated(cls, conversation: Conversation):
        """Notifies connected clients on the conversations WebSocket that a conversation's state

        (e.g., latest message, unread count, or timestamp) has been updated.
        """
        branch_id = conversation.branch_id or (
            conversation.business_account.branch_id
            if conversation.business_account
            else None
        )
        conv_data = ConversationSerializer(conversation).data

        payload = {
            "type": "conversation_updated",
            "event": "conversation.updated",
            "data": conv_data,
        }

        if branch_id:
            cls._send_to_channel_layer(
                f"messaging_conversations_branch_{branch_id}", payload
            )

        cls._send_to_channel_layer("messaging_conversations_all", payload)
