import logging
import secrets
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from message.models import (
    Attachment,
    BusinessAccount,
    Conversation,
    Message,
    PendingOAuthConnection,
)
from message.services.zernio_service import ZernioService

logger = logging.getLogger(__name__)

OAUTH_NONCE_TTL_MINUTES = 15


class MessagingService:
    """Core messaging service handling business account linking, OAuth nonce verification,

    conversation management, outbound message sending, and incoming webhooks.
    """

    def __init__(self, zernio_service: Optional[ZernioService] = None):
        self.zernio_service = zernio_service or ZernioService()

    def assert_conversation_belongs_to_org(
        self, conversation_id: str, org_id: str
    ) -> Conversation:
        """Verify that conversation exists and belongs to org_id via business_account.organization_id.

        Raises PermissionDenied if tenant mismatch occurs.
        """
        conversation = (
            Conversation.objects.select_related("business_account")
            .filter(id=conversation_id)
            .first()
        )

        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        if (
            not conversation.business_account
            or conversation.business_account.organization_id != org_id
        ):
            raise PermissionDenied(
                "You do not have access to this conversation"
            )

        return conversation

    def send_message(
        self, conversation_id: str, message_text: str, org_id: str, user=None
    ) -> Dict[str, Any]:
        """Send an outbound message to a conversation via Zernio and save it in DB."""
        conversation = self.assert_conversation_belongs_to_org(
            conversation_id, org_id
        )

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
            )

            # Update conversation timestamp
            conversation.save(update_fields=["updated_at"])

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
        self, platform: str, organization_id: str, app_url: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate a secure OAuth nonce, save pending connection, and return authUrl from Zernio."""
        base_app_url = (
            app_url
            or getattr(settings, "APP_URL", None)
            or "http://localhost:3000"
        )
        profile_id = self.zernio_service.get_or_create_profile_id(organization_id)

        # Cryptographically secure 32 hex char nonce
        nonce = secrets.token_hex(16)
        expires_at = timezone.now() + timedelta(minutes=OAUTH_NONCE_TTL_MINUTES)

        PendingOAuthConnection.objects.create(
            org_id=organization_id,
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

    def handle_oauth_callback(self, query_params: Dict[str, str]) -> Dict[str, Any]:
        """Validate nonce and complete Zernio OAuth connection flow."""
        platform = query_params.get("connected") or query_params.get("platform", "unknown")
        account_id = query_params.get("accountId") or query_params.get("profileId")
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

        org_id = pending.org_id
        pending.delete()  # Single-use security deletion

        business_account, _ = BusinessAccount.objects.update_or_create(
            zernio_account_id=account_id,
            defaults={
                "organization_id": org_id,
                "platform": platform,
                "account_name": username or None,
            },
        )

        return {
            "success": True,
            "accountId": business_account.zernio_account_id,
            "platform": business_account.platform,
            "organizationId": business_account.organization_id,
        }

    def unlink_account(self, platform: str, organization_id: str) -> Dict[str, bool]:
        """Unlink and delete social account from Zernio and DB."""
        account = BusinessAccount.objects.filter(
            organization_id=organization_id, platform=platform
        ).first()

        if not account:
            raise ValueError(f"No linked {platform} account found for this organization")

        try:
            self.zernio_service.delete_account(account.zernio_account_id)
        except Exception as exc:
            logger.error(f"Failed to delete Zernio account {account.zernio_account_id}: {exc}")
            raise ValueError(f"Failed to unlink {platform} account from Zernio: {exc}")

        account.delete()
        return {"success": True}

    def handle_incoming_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming Zernio webhooks for message.received and message.created events."""
        event = payload.get("event") or payload.get("type")
        data = payload.get("data") or payload

        if event not in ["message.received", "message.created"]:
            logger.debug(f"Ignoring non-messaging webhook event: {event}")
            return payload

        zernio_conv_id = (
            data.get("conversation", {}).get("id")
            or data.get("message", {}).get("conversationId")
        )
        account_id = (
            data.get("account", {}).get("id")
            or data.get("conversation", {}).get("accountId")
            or data.get("accountId")
        )
        platform = (
            data.get("account", {}).get("platform")
            or data.get("conversation", {}).get("platform")
        )

        participant_name = (
            data.get("conversation", {}).get("participantName")
            or data.get("customer", {}).get("name")
            or data.get("message", {}).get("sender", {}).get("name")
        )
        participant_avatar = (
            data.get("customer", {}).get("avatarUrl")
            or data.get("message", {}).get("sender", {}).get("avatarUrl")
        )

        raw_attachments = data.get("message", {}).get("attachments", [])
        message_id = data.get("message", {}).get("id")
        content = (
            data.get("message", {}).get("text")
            or data.get("message", {}).get("content")
        )
        sender_id = (
            data.get("message", {}).get("sender", {}).get("id")
            or data.get("message", {}).get("senderId")
            or data.get("customer", {}).get("id")
        )

        if not zernio_conv_id:
            logger.warning("Webhook payload missing conversation ID")
            return payload

        # Prevent echoing outbound messages
        if sender_id and account_id and sender_id == account_id:
            logger.debug(f"Ignoring echo outbound message from senderId: {sender_id}")
            return payload

        biz_account = BusinessAccount.objects.filter(zernio_account_id=account_id).first() if account_id else None

        conversation, _ = Conversation.objects.update_or_create(
            zernio_conversation_id=zernio_conv_id,
            defaults={
                "zernio_account_id": account_id or "",
                "platform": platform or None,
                "participant_name": participant_name or None,
                "participant_avatar": participant_avatar or None,
                "business_account": biz_account,
            },
        )

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

        return payload

    def mark_conversation_as_read(self, conversation_id: str, org_id: str) -> Dict[str, bool]:
        """Mark all inbound messages in conversation as read."""
        conversation = self.assert_conversation_belongs_to_org(conversation_id, org_id)
        Message.objects.filter(
            conversation=conversation, direction="INBOUND", is_read=False
        ).update(is_read=True)
        return {"success": True}

    def link_conversation(self, conversation_id: str, applicant_id: str, org_id: str) -> Conversation:
        """Link applicant_id to a conversation."""
        conversation = self.assert_conversation_belongs_to_org(conversation_id, org_id)
        conversation.applicant_id = applicant_id
        conversation.save(update_fields=["applicant_id", "updated_at"])
        return conversation

    def unlink_conversation(self, conversation_id: str, org_id: str) -> Conversation:
        """Unlink applicant_id from a conversation."""
        conversation = self.assert_conversation_belongs_to_org(conversation_id, org_id)
        conversation.applicant_id = None
        conversation.save(update_fields=["applicant_id", "updated_at"])
        return conversation

    def delete_conversation(self, conversation_id: str, org_id: str) -> Dict[str, bool]:
        """Delete a conversation."""
        conversation = self.assert_conversation_belongs_to_org(conversation_id, org_id)
        conversation.delete()
        return {"success": True}
