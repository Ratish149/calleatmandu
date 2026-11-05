import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from message.models import (
    Attachment,
    BusinessAccount,
    Conversation,
    Message,
    PendingOAuthConnection,
)
from message.services.ai_reply_service import AIReplyService
from message.services.messaging_broadcaster import MessagingBroadcaster
from message.services.zernio_service import ZernioService

logger = logging.getLogger(__name__)

OAUTH_NONCE_TTL_MINUTES = 15

_MEDIA_PLACEHOLDERS = {
    "image": "[Image]",
    "photo": "[Image]",
    "video": "[Video]",
    "audio": "[Audio]",
    "voice": "[Audio]",
    "sticker": "[Sticker]",
    "emoji": "[Sticker]",
    "share": "[Shared post]",
    "share_post": "[Shared post]",
    "file": "[File]",
}


def _media_attachment_placeholder(
    metadata: Dict[str, Any], attachments: List[Dict[str, Any]]
) -> str:
    candidates = [str((metadata or {}).get("tiktokMessageType") or "").lower()]
    if attachments:
        candidates.append(str(attachments[0].get("type") or "").lower())

    for candidate in candidates:
        if candidate in _MEDIA_PLACEHOLDERS:
            return _MEDIA_PLACEHOLDERS[candidate]

    return "[Attachment]"


class MessagingService:
    """Core messaging service handling business account linking, OAuth nonce verification,

    conversation management, outbound message sending, and incoming webhooks.
    """

    def __init__(self, zernio_service: Optional[ZernioService] = None):
        self.zernio_service = zernio_service or ZernioService()

    def assert_conversation_belongs_to_branch(
        self, conversation_id: str, branch_id: Optional[Union[int, str]] = None
    ) -> Conversation:
        """Verify that conversation exists and optionally belongs to the branch.

        Raises PermissionDenied if branch mismatch occurs.
        """
        conversation = (
            Conversation.objects
            .select_related("business_account", "branch")
            .filter(id=conversation_id)
            .first()
        )

        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        if branch_id is not None:
            conv_branch_id = conversation.branch_id or (
                conversation.business_account.branch_id
                if conversation.business_account
                else None
            )
            if conv_branch_id is not None and str(conv_branch_id) != str(branch_id):
                raise PermissionDenied("You do not have access to this conversation")

        return conversation

    def send_message(
        self,
        conversation_id: str,
        message_text: str,
        branch_id: Optional[Union[int, str]] = None,
        user=None,
        is_ai_generated: bool = False,
    ) -> Dict[str, Any]:
        """Send an outbound message to a conversation via Zernio and save it in DB."""
        conversation = self.assert_conversation_belongs_to_branch(
            conversation_id, branch_id
        )

        if not is_ai_generated:
            # A human replied: cancel any pending AI reply and hand over permanently.
            AIReplyService.deactivate(conversation)

        try:
            result = self.zernio_service.send_inbox_message(
                conversation_id=conversation.zernio_conversation_id,
                account_id=conversation.zernio_account_id,
                message=message_text,
            )

            zernio_message_id = None
            if isinstance(result, dict):
                zernio_message_id = result.get("messageId") or result.get("id")

            message_obj = Message.objects.create(
                zernio_message_id=zernio_message_id,
                conversation=conversation,
                content=message_text,
                direction="OUTBOUND",
                sent_by=user if getattr(user, "is_authenticated", False) else None,
                is_ai_generated=is_ai_generated,
            )

            # Assign branch to conversation if not already set
            update_fields = ["updated_at"]
            user_branch_id = getattr(user, "branch_id", None) or branch_id
            if not conversation.branch_id and user_branch_id:
                conversation.branch_id = user_branch_id
                update_fields.append("branch")

            # Update conversation timestamp and branch
            conversation.save(update_fields=update_fields)

            # Broadcast new outbound message and conversation update
            MessagingBroadcaster.broadcast_new_message(
                message=message_obj,
                conversation=conversation,
                event_name="message.sent",
            )
            MessagingBroadcaster.broadcast_conversation_updated(conversation)

            return {
                "id": str(message_obj.id),
                "zernioMessageId": zernio_message_id,
                "content": message_text,
                "direction": "OUTBOUND",
                "createdAt": message_obj.created_at,
            }
        except Exception as exc:
            logger.error(f"Failed to send message: {exc}", exc_info=True)
            raise ValueError(f"Failed to send message: {exc}")

    def get_connect_url(
        self,
        platform: str,
        branch_id: Optional[Union[int, str]] = None,
        app_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate a secure OAuth nonce, save pending connection, and return authUrl from Zernio."""
        base_app_url = (
            app_url or getattr(settings, "APP_URL", None) or "http://localhost:3000"
        )
        profile_id = self.zernio_service.get_or_create_profile_id(branch_id)

        # Cryptographically secure 32 hex char nonce
        nonce = secrets.token_hex(16)
        expires_at = timezone.now() + timedelta(minutes=OAUTH_NONCE_TTL_MINUTES)

        PendingOAuthConnection.objects.create(
            branch_id=branch_id,
            platform=platform,
            nonce=nonce,
            expires_at=expires_at,
        )

        redirect_url = f"{base_app_url}/api/messaging/accounts/callback?nonce={nonce}"

        result = self.zernio_service.get_connect_url(
            platform=platform,
            profile_id=profile_id,
            redirect_url=redirect_url,
        )

        auth_url = result.get("authUrl")
        if not auth_url:
            logger.error(f"Zernio did not return authUrl: {result}")
            raise ValueError("Zernio did not return an authUrl")

        return {"authUrl": auth_url}

    def handle_oauth_callback(
        self,
        query_params: Dict[str, str],
        fallback_branch_id: Optional[Union[int, str]] = None,
    ) -> Dict[str, Any]:
        """Validate nonce and complete Zernio OAuth connection flow."""
        platform = query_params.get("connected") or query_params.get(
            "platform", "unknown"
        )
        account_id = (
            query_params.get("accountId")
            or query_params.get("account_id")
            or query_params.get("id")
        )
        username = query_params.get("username")
        nonce = query_params.get("nonce")

        if not nonce:
            raise ValueError("OAuth callback is missing the nonce parameter")

        if not account_id:
            raise ValueError("Zernio callback did not include an accountId")

        pending = PendingOAuthConnection.objects.filter(nonce=nonce).first()
        if not pending:
            raise ValueError("Invalid or already-used OAuth nonce")

        if pending.expires_at < timezone.now():
            pending.delete()
            raise ValueError("OAuth nonce has expired — please start connection again")

        branch_id = pending.branch_id or fallback_branch_id
        pending.delete()  # Single-use security deletion

        business_account, _ = BusinessAccount.objects.update_or_create(
            zernio_account_id=account_id,
            defaults={
                "branch_id": branch_id,
                "platform": platform,
                "account_name": username or None,
            },
        )

        return {
            "success": True,
            "accountId": business_account.zernio_account_id,
            "platform": business_account.platform,
            "branchId": business_account.branch_id,
        }

    def unlink_account(
        self,
        platform: str,
        branch_id: Optional[Union[int, str]] = None,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Unlink and delete social account from Zernio and DB."""
        query = BusinessAccount.objects.filter(platform=platform)
        if branch_id is not None:
            query = query.filter(branch_id=branch_id)
        if account_id:
            query = query.filter(zernio_account_id=account_id)
        account = query.first()

        if not account:
            raise ValueError(f"No linked {platform} account found for this branch")

        try:
            self.zernio_service.delete_account(account.zernio_account_id)
        except Exception as exc:
            logger.error(
                f"Failed to delete Zernio account {account.zernio_account_id}: {exc}"
            )
            # If Zernio reports 404 (not found / already deleted) or 400 (invalid format),
            # clean up the local database record so the branch isn't stuck with an un-deletable broken account.
            err_msg = str(exc).lower()
            status_code = getattr(exc, "status_code", None)
            is_non_fatal = (
                status_code in [400, 404]
                or "invalid accountid" in err_msg
                or "not found" in err_msg
            )
            if is_non_fatal:
                logger.warning(
                    f"Zernio account {account.zernio_account_id} not found or invalid format on remote ({exc}). Removing local record."
                )
            else:
                raise ValueError(
                    f"Failed to unlink {platform} account from Zernio: {exc}"
                )

        account.delete()
        return {"success": True}

    def sync_accounts_from_zernio(
        self, branch_id: Optional[Union[int, str]] = None
    ) -> List[BusinessAccount]:
        """Fetch all connected accounts from Zernio and update local database."""
        response = self.zernio_service.list_accounts()
        accounts_data = response.get("accounts", [])
        synced_accounts = []

        for acc in accounts_data:
            zernio_id = acc.get("_id") or acc.get("id")
            if not zernio_id:
                continue

            platform = acc.get("platform", "unknown")
            metadata = acc.get("metadata") or {}
            profile_data = metadata.get("profileData") or {}
            username = (
                acc.get("username")
                or acc.get("displayName")
                or profile_data.get("username")
            )

            business_account, _ = BusinessAccount.objects.update_or_create(
                zernio_account_id=zernio_id,
                defaults={
                    "branch_id": branch_id,
                    "platform": platform,
                    "account_name": username,
                },
            )
            synced_accounts.append(business_account)

        return synced_accounts

    def handle_incoming_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming Zernio webhooks for message.received and message.created events."""
        event = payload.get("event") or payload.get("type")
        data = payload.get("data") or payload

        if event not in ["message.received", "message.created"]:
            logger.debug(f"Ignoring non-messaging webhook event: {event}")
            return payload

        account = data.get("account") or {}
        conversation = data.get("conversation") or {}
        message = data.get("message") or {}
        sender = message.get("sender") or {}
        customer = data.get("customer") or {}
        metadata = data.get("metadata") or {}

        zernio_conv_id = conversation.get("id") or message.get("conversationId")
        account_id = (
            account.get("accountId")
            or account.get("id")
            or conversation.get("accountId")
            or data.get("accountId")
        )
        platform = (
            message.get("platform")
            or account.get("platform")
            or conversation.get("platform")
        )

        participant_name = (
            conversation.get("participantName")
            or conversation.get("participantUsername")
            or customer.get("name")
            or sender.get("name")
            or sender.get("username")
        )
        participant_avatar = (
            conversation.get("participantPicture")
            or customer.get("avatarUrl")
            or sender.get("picture")
            or sender.get("avatarUrl")
        )

        raw_attachments = message.get("attachments") or []
        message_id = message.get("id")
        content = message.get("text") or message.get("content")
        if not str(content or "").strip() and raw_attachments:
            content = _media_attachment_placeholder(metadata, raw_attachments)
        sender_id = (
            sender.get("id")
            or message.get("senderId")
            or customer.get("id")
        )

        if not zernio_conv_id:
            logger.warning("Webhook payload missing conversation ID")
            return payload

        # Prevent echoing outbound messages
        if sender_id and account_id and sender_id == account_id:
            logger.debug(f"Ignoring echo outbound message from senderId: {sender_id}")
            return payload

        biz_account = (
            BusinessAccount.objects
            .select_related("branch")
            .filter(zernio_account_id=account_id)
            .first()
            if account_id
            else None
        )

        if not biz_account:
            logger.warning(
                "Ignoring webhook for unconnected business account %s (conversation %s)",
                account_id,
                zernio_conv_id,
            )
            return payload

        branch = biz_account.branch

        conversation, created = Conversation.objects.update_or_create(
            zernio_conversation_id=zernio_conv_id,
            defaults={
                "zernio_account_id": account_id or "",
                "platform": platform or None,
                "participant_name": participant_name or None,
                "participant_avatar": participant_avatar or None,
                "business_account": biz_account,
                "branch": branch,
            },
        )

        if created:
            MessagingBroadcaster.broadcast_conversation_created(conversation)

        if message_id and (content or raw_attachments):
            if not Message.objects.filter(zernio_message_id=message_id).exists():
                message_obj = Message.objects.create(
                    zernio_message_id=message_id,
                    conversation=conversation,
                    content=content,
                    direction="INBOUND",
                    external_sender_id=sender_id,
                )

                for att in raw_attachments:
                    att_type = att.get("type", "FILE").upper()
                    if att_type not in ["IMAGE", "VIDEO", "AUDIO", "FILE"]:
                        att_type = "FILE"

                    Attachment.objects.create(
                        message=message_obj,
                        type=att_type,
                        url=att.get("url") or att.get("payload", {}).get("url", ""),
                    )

                conversation.save(update_fields=["updated_at"])

                # Broadcast new inbound message and conversation update
                MessagingBroadcaster.broadcast_new_message(
                    message=message_obj,
                    conversation=conversation,
                    event_name="message.received",
                )
                MessagingBroadcaster.broadcast_conversation_updated(conversation)

                # Instantaneous Ollama auto-reply (runs in a background thread)
                AIReplyService.maybe_schedule_reply(conversation)

        return payload

    def mark_conversation_as_read(
        self, conversation_id: str, branch_id: Optional[Union[int, str]] = None
    ) -> Dict[str, bool]:
        """Mark all inbound messages in conversation as read."""
        conversation = self.assert_conversation_belongs_to_branch(
            conversation_id, branch_id
        )
        Message.objects.filter(
            conversation=conversation, direction="INBOUND", is_read=False
        ).update(is_read=True)

        MessagingBroadcaster.broadcast_unread_counts_updated(
            business_account_id=conversation.business_account_id,
            conversation_id=conversation.id,
        )
        MessagingBroadcaster.broadcast_conversation_updated(conversation)

        return {"success": True}

    def link_conversation(
        self,
        conversation_id: str,
        applicant_id: str,
        branch_id: Optional[Union[int, str]] = None,
    ) -> Conversation:
        """Link applicant_id to a conversation."""
        conversation = self.assert_conversation_belongs_to_branch(
            conversation_id, branch_id
        )
        conversation.applicant_id = applicant_id
        update_fields = ["applicant_id", "updated_at"]
        if not conversation.branch_id and branch_id:
            conversation.branch_id = branch_id
            update_fields.append("branch")
        conversation.save(update_fields=update_fields)
        return conversation

    def unlink_conversation(
        self, conversation_id: str, branch_id: Optional[Union[int, str]] = None
    ) -> Conversation:
        """Unlink applicant_id from a conversation."""
        conversation = self.assert_conversation_belongs_to_branch(
            conversation_id, branch_id
        )
        conversation.applicant_id = None
        conversation.save(update_fields=["applicant_id", "updated_at"])
        return conversation

    def delete_conversation(
        self, conversation_id: str, branch_id: Optional[Union[int, str]] = None
    ) -> Dict[str, bool]:
        """Delete a conversation."""
        conversation = self.assert_conversation_belongs_to_branch(
            conversation_id, branch_id
        )
        conversation.delete()
        return {"success": True}
