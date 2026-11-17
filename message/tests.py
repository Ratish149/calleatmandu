import json
from datetime import timedelta
from io import StringIO
from unittest.mock import Mock, patch

import msgpack
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from message.routing import websocket_urlpatterns

from account.models import Branch, User
from faq.models import Faq
from order.models import Order
from product.models import Product
from message.consumers import (
    ConversationsConsumer,
    UnreadMessagesConsumer,
    is_authorized_for_account,
)
from message.models import BranchAISettings, BusinessAccount, Conversation, Message
from message.serializers import ConversationSerializer
from message.selectors.messaging_selector import (
    get_conversations_for_account,
    get_unread_counts_for_account,
)
from message.services.ai_order_settings import (
    get_order_feature_flags,
    resolve_conversation_branch_id,
)
from message.services.ai_reply_service import AIReplyService
from message.services.ai_tools import execute_tool, get_enabled_tool_schemas
from message.services.language_detection import detect_reply_language
from message.services.messaging_broadcaster import MessagingBroadcaster
from message.services.messaging_service import MessagingService
from message.services.ollama_service import OllamaError, OllamaService
from message.services.reply_quality import assess_reply
from message.services.zernio_service import ZernioService

from calleatmandu.celery import app as celery_app

# Run Celery tasks inline so the test suite needs no broker or worker.
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

WEBHOOK_URL = "/api/webhook/"


def webhook_payload(conversation_id="zc-1", message_id="m-1", text="Do you deliver?"):
    return {
        "event": "message.received",
        "data": {
            "conversation": {
                "id": conversation_id,
                "accountId": "acc-1",
                "platform": "instagram",
                "participantName": "Sam",
            },
            "account": {"id": "acc-1", "platform": "instagram"},
            "customer": {"id": "cust-1", "name": "Sam"},
            "message": {
                "id": message_id,
                "text": text,
                "sender": {"id": "cust-1", "name": "Sam"},
            },
        },
    }


def tiktok_webhook_payload(
    conversation_id="tt-zc-1",
    message_id="tt-m-1",
    text="Hello",
    attachments=None,
    message_type=None,
    participant_name=None,
):
    payload = {
        "id": f"evt-{message_id}",
        "event": "message.received",
        "message": {
            "id": message_id,
            "conversationId": conversation_id,
            "platform": "tiktok",
            "platformMessageId": f"platform-{message_id}",
            "direction": "inbound",
            "text": text,
            "attachments": attachments or [],
            "sender": {
                "id": "tt-user-1",
                "name": None,
                "username": "tiktok_customer",
                "picture": "https://cdn.example/sender.jpg",
            },
            "sentAt": "2026-01-01T00:00:00Z",
            "isRead": False,
        },
        "conversation": {
            "id": conversation_id,
            "platformConversationId": conversation_id,
            "participantId": "tt-user-1",
            "participantName": participant_name,
            "participantUsername": "tiktok_customer",
            "participantPicture": "https://cdn.example/avatar.jpg",
            "status": "active",
        },
        "account": {
            "id": "tt-acc-1",
            "accountId": "tt-acc-1",
            "platform": "tiktok",
            "username": "business",
        },
        "timestamp": "2026-01-01T00:00:00Z",
    }
    if message_type:
        payload["metadata"] = {"tiktokMessageType": message_type}
    return payload


class MessagingTestCase(TestCase):
    def setUp(self):
        patcher = patch("message.services.messaging_service.ZernioService")
        self.mock_zernio_cls = patcher.start()
        self.addCleanup(patcher.stop)

    def make_conversation(
        self,
        conversation_id="zc-1",
        active=True,
        pending=False,
        task_id=None,
        due_at=None,
    ):
        return Conversation.objects.create(
            zernio_conversation_id=conversation_id,
            zernio_account_id="acc-1",
            platform="instagram",
            participant_name="Sam",
            ai_replies_active=active,
            ai_reply_pending=pending,
            ai_reply_task_id=task_id,
            ai_reply_due_at=due_at,
        )


class ZernioWebhookAITest(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.business_account = BusinessAccount.objects.create(
            zernio_account_id="acc-1",
            platform="instagram",
            account_name="Test Account",
        )

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_webhook_creates_conversation_and_schedules_reply(self, mock_schedule):
        response = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(webhook_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        conversation = Conversation.objects.get(zernio_conversation_id="zc-1")
        self.assertEqual(conversation.business_account_id, self.business_account.id)
        self.assertTrue(
            conversation.messages.filter(direction="INBOUND", content="Do you deliver?").exists()
        )
        mock_schedule.assert_called_once()
        self.assertEqual(mock_schedule.call_args.args[0].pk, conversation.pk)

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_duplicate_webhook_does_not_reschedule(self, mock_schedule):
        payload = webhook_payload()
        self.client.post(WEBHOOK_URL, data=json.dumps(payload), content_type="application/json")
        self.client.post(WEBHOOK_URL, data=json.dumps(payload), content_type="application/json")

        self.assertEqual(Message.objects.filter(zernio_message_id="m-1").count(), 1)
        mock_schedule.assert_called_once()

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_webhook_ignored_when_no_business_account_connected(self, mock_schedule):
        BusinessAccount.objects.all().delete()

        response = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(webhook_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Conversation.objects.filter(zernio_conversation_id="zc-1").exists()
        )
        self.assertFalse(Message.objects.filter(zernio_message_id="m-1").exists())
        mock_schedule.assert_not_called()

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_webhook_ignored_for_unmatched_business_account(self, mock_schedule):
        payload = webhook_payload()
        payload["data"]["conversation"]["accountId"] = "acc-unknown"
        payload["data"]["account"]["id"] = "acc-unknown"

        response = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Conversation.objects.filter(zernio_conversation_id="zc-1").exists())
        self.assertFalse(Message.objects.filter(zernio_message_id="m-1").exists())
        self.assertEqual(get_unread_counts_for_account(self.business_account.id), {})
        mock_schedule.assert_not_called()

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_connected_account_inbound_message_is_unread(self, mock_schedule):
        self.client.post(
            WEBHOOK_URL,
            data=json.dumps(webhook_payload()),
            content_type="application/json",
        )

        message = Message.objects.get(zernio_message_id="m-1")
        self.assertFalse(message.is_read)
        self.assertEqual(
            get_unread_counts_for_account(self.business_account.id),
            {str(message.conversation_id): 1},
        )


class TikTokWebhookTest(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.business_account = BusinessAccount.objects.create(
            zernio_account_id="tt-acc-1",
            platform="tiktok",
            account_name="TikTok Business",
        )

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_flat_text_payload_creates_conversation(self, mock_schedule):
        response = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(tiktok_webhook_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        conversation = Conversation.objects.get(zernio_conversation_id="tt-zc-1")
        self.assertEqual(conversation.business_account_id, self.business_account.id)
        self.assertEqual(conversation.platform, "tiktok")
        self.assertEqual(conversation.participant_name, "tiktok_customer")
        self.assertEqual(
            conversation.participant_avatar, "https://cdn.example/avatar.jpg"
        )

        message = Message.objects.get(zernio_message_id="tt-m-1")
        self.assertEqual(message.content, "Hello")
        self.assertEqual(message.direction, "INBOUND")
        self.assertFalse(message.is_read)
        self.assertEqual(message.external_sender_id, "tt-user-1")
        mock_schedule.assert_called_once()

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_image_payload_uses_placeholder_and_stores_attachment(
        self, mock_schedule
    ):
        response = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(
                tiktok_webhook_payload(
                    text=None,
                    attachments=[
                        {
                            "type": "image",
                            "url": "https://cdn.example/image.jpg",
                        }
                    ],
                    message_type="image",
                )
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        message = Message.objects.get(zernio_message_id="tt-m-1")
        self.assertEqual(message.content, "[Image]")
        attachment = message.attachments.get()
        self.assertEqual(attachment.type, "IMAGE")
        self.assertEqual(attachment.url, "https://cdn.example/image.jpg")
        mock_schedule.assert_called_once()

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_share_post_payload_uses_placeholder(self, mock_schedule):
        response = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(
                tiktok_webhook_payload(
                    text=None,
                    attachments=[
                        {
                            "type": "share",
                            "url": "https://www.tiktok.com/@user/video/123",
                        }
                    ],
                    message_type="share_post",
                )
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        message = Message.objects.get(zernio_message_id="tt-m-1")
        self.assertEqual(message.content, "[Shared post]")
        self.assertEqual(message.attachments.get().type, "FILE")
        mock_schedule.assert_called_once()

    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_duplicate_payload_is_not_inserted_twice(self, mock_schedule):
        payload = tiktok_webhook_payload()
        for _ in range(2):
            self.client.post(
                WEBHOOK_URL,
                data=json.dumps(payload),
                content_type="application/json",
            )

        self.assertEqual(Message.objects.filter(zernio_message_id="tt-m-1").count(), 1)
        mock_schedule.assert_called_once()


class ZernioConnectURLTest(TestCase):
    def setUp(self):
        self.service = ZernioService(api_key="test-key")
        self.service.client = Mock()
        self.service.client.connect.get_connect_url.return_value = {
            "authUrl": "https://auth.example"
        }

    def test_tiktok_omits_instagram_login_method(self):
        self.service.get_connect_url(platform="tiktok", profile_id="profile-1")

        kwargs = self.service.client.connect.get_connect_url.call_args.kwargs
        self.assertNotIn("login_method", kwargs)

    def test_instagram_includes_default_login_method(self):
        self.service.get_connect_url(platform="instagram", profile_id="profile-1")

        kwargs = self.service.client.connect.get_connect_url.call_args.kwargs
        self.assertEqual(kwargs["login_method"], "instagram_login")


class ScheduleReplyTest(MessagingTestCase):
    def test_disabled_setting_skips(self):
        conversation = self.make_conversation()
        with override_settings(AI_REPLY_ENABLED=False):
            scheduled = AIReplyService.maybe_schedule_reply(conversation)
        self.assertFalse(scheduled)
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)

    def test_branch_chat_disabled_skips(self):
        branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )
        conversation = self.make_conversation()
        conversation.branch = branch
        conversation.save(update_fields=["branch"])
        BranchAISettings.objects.create(branch=branch, ai_chat_enabled=False)

        with override_settings(AI_REPLY_ENABLED=True):
            scheduled = AIReplyService.maybe_schedule_reply(conversation)

        self.assertFalse(scheduled)
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)
        self.assertIsNone(conversation.ai_reply_due_at)

    def test_pending_reply_is_rescheduled_on_new_inbound(self):
        conversation = self.make_conversation(pending=True, task_id="old-task")
        before = timezone.now()
        with patch("message.tasks.revoke_task") as mock_revoke:
            scheduled = AIReplyService.maybe_schedule_reply(conversation)
        after = timezone.now()

        self.assertTrue(scheduled)
        mock_revoke.assert_called_once_with("old-task")
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_reply_pending)
        self.assertTrue(conversation.ai_reply_task_id)
        self.assertNotEqual(conversation.ai_reply_task_id, "old-task")
        self.assertGreaterEqual(
            conversation.ai_reply_due_at, before + timedelta(seconds=120)
        )
        self.assertLessEqual(
            conversation.ai_reply_due_at, after + timedelta(seconds=120)
        )

    def test_inbound_reactivates_inactive_conversation(self):
        conversation = self.make_conversation(active=False)
        scheduled = AIReplyService.maybe_schedule_reply(conversation)
        self.assertTrue(scheduled)
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_replies_active)
        self.assertTrue(conversation.ai_reply_pending)
        self.assertIsNotNone(conversation.ai_reply_due_at)

    def test_happy_path_sets_pending_and_due_at(self):
        conversation = self.make_conversation()
        before = timezone.now()
        scheduled = AIReplyService.maybe_schedule_reply(conversation)
        after = timezone.now()

        self.assertTrue(scheduled)
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_reply_pending)
        self.assertTrue(conversation.ai_reply_task_id)
        self.assertGreaterEqual(
            conversation.ai_reply_due_at, before + timedelta(seconds=120)
        )
        self.assertLessEqual(
            conversation.ai_reply_due_at, after + timedelta(seconds=120)
        )

    def test_branch_reply_delay_override_used_for_due_at(self):
        branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )
        conversation = self.make_conversation()
        conversation.branch = branch
        conversation.save(update_fields=["branch"])
        BranchAISettings.objects.create(
            branch=branch, ai_reply_delay_seconds=45
        )

        before = timezone.now()
        scheduled = AIReplyService.maybe_schedule_reply(conversation)
        after = timezone.now()

        self.assertTrue(scheduled)
        conversation.refresh_from_db()
        self.assertGreaterEqual(
            conversation.ai_reply_due_at, before + timedelta(seconds=45)
        )
        self.assertLessEqual(
            conversation.ai_reply_due_at, after + timedelta(seconds=45)
        )


class GenerateAndSendTest(MessagingTestCase):
    def test_ai_reply_is_generated_and_sent(self):
        conversation = self.make_conversation(
            pending=True, due_at=timezone.now() + timedelta(minutes=2)
        )
        Message.objects.create(
            zernio_message_id="m-1",
            conversation=conversation,
            content="Do you deliver?",
            direction="INBOUND",
        )

        with patch("message.services.ai_reply_service.OllamaService") as mock_ollama_cls:
            mock_ollama_cls.return_value.generate_with_tools.return_value = "Yes, we deliver!"
            AIReplyService._generate_and_send(conversation.pk)

        outbound = conversation.messages.filter(direction="OUTBOUND").first()
        self.assertIsNotNone(outbound)
        self.assertTrue(outbound.content.startswith("Yes, we deliver!"))
        self.assertIn("- Calleatmandu bot", outbound.content)
        self.assertTrue(outbound.is_ai_generated)
        self.assertIsNone(outbound.sent_by)

        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)
        self.assertIsNone(conversation.ai_reply_due_at)

    def test_branch_chat_disabled_skips_generation(self):
        branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )
        conversation = self.make_conversation(pending=True)
        conversation.branch = branch
        conversation.save(update_fields=["branch"])
        BranchAISettings.objects.create(branch=branch, ai_chat_enabled=False)
        Message.objects.create(
            zernio_message_id="m-1",
            conversation=conversation,
            content="Do you deliver?",
            direction="INBOUND",
        )

        with override_settings(AI_REPLY_ENABLED=True), patch(
            "message.services.ai_reply_service.OllamaService"
        ) as mock_ollama_cls:
            AIReplyService._generate_and_send(conversation.pk)

        mock_ollama_cls.return_value.generate_with_tools.assert_not_called()
        self.assertFalse(conversation.messages.filter(direction="OUTBOUND").exists())
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)

    def test_empty_ollama_reply_sends_nothing(self):
        conversation = self.make_conversation(pending=True)
        Message.objects.create(
            zernio_message_id="m-1",
            conversation=conversation,
            content="Hi",
            direction="INBOUND",
        )
        with patch("message.services.ai_reply_service.OllamaService") as mock_ollama_cls:
            mock_ollama_cls.return_value.generate_with_tools.return_value = ""
            AIReplyService._generate_and_send(conversation.pk)

        self.assertFalse(conversation.messages.filter(direction="OUTBOUND").exists())
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)

    def test_ollama_error_clears_pending_without_reply(self):
        conversation = self.make_conversation(pending=True)
        Message.objects.create(
            zernio_message_id="m-1",
            conversation=conversation,
            content="Hi",
            direction="INBOUND",
        )
        with patch("message.services.ai_reply_service.OllamaService") as mock_ollama_cls:
            mock_ollama_cls.return_value.generate_with_tools.side_effect = OllamaError("down")
            AIReplyService._generate_and_send(conversation.pk)

        self.assertFalse(conversation.messages.filter(direction="OUTBOUND").exists())
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)

    def test_human_reply_during_generation_cancels(self):
        conversation = self.make_conversation(active=True, pending=False)
        AIReplyService._send_if_still_pending(conversation, "Should not send")
        self.assertFalse(conversation.messages.filter(direction="OUTBOUND").exists())


class AIReplyTaskGuardTest(MessagingTestCase):
    def test_new_inbound_revokes_previous_task(self):
        old_due_at = timezone.now() - timedelta(seconds=1)
        conversation = self.make_conversation(
            pending=True, task_id="old-task", due_at=old_due_at
        )
        with patch("message.tasks.revoke_task") as mock_revoke:
            scheduled = AIReplyService.maybe_schedule_reply(conversation)

        self.assertTrue(scheduled)
        mock_revoke.assert_called_once_with("old-task")
        conversation.refresh_from_db()
        self.assertNotEqual(conversation.ai_reply_task_id, "old-task")
        self.assertTrue(conversation.ai_reply_task_id)
        self.assertGreater(conversation.ai_reply_due_at, old_due_at)

    def test_stale_task_does_not_send(self):
        due_at = timezone.now() + timedelta(minutes=2)
        conversation = self.make_conversation(
            pending=True, task_id="new-task", due_at=due_at
        )
        Message.objects.create(
            zernio_message_id="m-1",
            conversation=conversation,
            content="Hi",
            direction="INBOUND",
        )
        with patch("message.services.ai_reply_service.OllamaService") as mock_ollama:
            mock_ollama.return_value.generate_with_tools.return_value = "Stale"
            AIReplyService._generate_and_send(conversation.pk, task_id="old-task")

        self.assertFalse(conversation.messages.filter(direction="OUTBOUND").exists())
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_reply_pending)
        self.assertEqual(conversation.ai_reply_task_id, "new-task")
        self.assertEqual(conversation.ai_reply_due_at, due_at)

    def test_deactivate_revokes_pending_task(self):
        conversation = self.make_conversation(
            pending=True,
            task_id="t1",
            due_at=timezone.now() + timedelta(minutes=2),
        )
        with patch("message.tasks.revoke_task") as mock_revoke:
            AIReplyService.deactivate(conversation)

        mock_revoke.assert_called_once_with("t1")
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)
        self.assertFalse(conversation.ai_replies_active)
        self.assertIsNone(conversation.ai_reply_task_id)
        self.assertIsNone(conversation.ai_reply_due_at)

    def test_activate_revokes_pending_task(self):
        conversation = self.make_conversation(
            active=False,
            pending=True,
            task_id="t2",
            due_at=timezone.now() + timedelta(minutes=2),
        )
        with patch("message.tasks.revoke_task") as mock_revoke:
            AIReplyService.activate(conversation)

        mock_revoke.assert_called_once_with("t2")
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_replies_active)
        self.assertFalse(conversation.ai_reply_pending)
        self.assertIsNone(conversation.ai_reply_task_id)
        self.assertIsNone(conversation.ai_reply_due_at)

    def test_cancel_pending_for_branch_clears_only_that_branch(self):
        branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )
        other_branch = Branch.objects.create(
            name="Thamel",
            address="Thamel, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000001",
        )
        due_at = timezone.now() + timedelta(minutes=2)
        first = self.make_conversation(
            conversation_id="zc-1", pending=True, task_id="t1", due_at=due_at
        )
        second = self.make_conversation(
            conversation_id="zc-2", pending=True, task_id="t2", due_at=due_at
        )
        untouched = self.make_conversation(
            conversation_id="zc-3", pending=True, task_id="t3", due_at=due_at
        )
        first.branch = branch
        second.branch = branch
        untouched.branch = other_branch
        first.save(update_fields=["branch"])
        second.save(update_fields=["branch"])
        untouched.save(update_fields=["branch"])

        with patch("message.tasks.revoke_task") as mock_revoke:
            cancelled = AIReplyService.cancel_pending_for_branch(branch.pk)

        self.assertEqual(cancelled, 2)
        self.assertEqual(
            {call.args[0] for call in mock_revoke.call_args_list}, {"t1", "t2"}
        )
        first.refresh_from_db()
        second.refresh_from_db()
        untouched.refresh_from_db()
        self.assertFalse(first.ai_reply_pending)
        self.assertFalse(second.ai_reply_pending)
        self.assertIsNone(first.ai_reply_task_id)
        self.assertIsNone(second.ai_reply_task_id)
        self.assertIsNone(first.ai_reply_due_at)
        self.assertIsNone(second.ai_reply_due_at)
        self.assertTrue(untouched.ai_reply_pending)
        self.assertEqual(untouched.ai_reply_task_id, "t3")
        self.assertEqual(untouched.ai_reply_due_at, due_at)


class DispatchDueRepliesTest(MessagingTestCase):
    def test_dispatches_due_pending_conversation(self):
        conversation = self.make_conversation(
            pending=True,
            task_id="t1",
            due_at=timezone.now() - timedelta(seconds=1),
        )
        with patch.object(AIReplyService, "_generate_and_send") as mock_send:
            dispatched = AIReplyService.dispatch_due_replies()

        self.assertEqual(dispatched, 1)
        mock_send.assert_called_once_with(conversation.pk, task_id="t1")
        conversation.refresh_from_db()
        self.assertGreater(conversation.ai_reply_due_at, timezone.now())

    def test_dispatches_legacy_pending_without_due_at(self):
        conversation = self.make_conversation(
            pending=True, task_id="legacy-task", due_at=None
        )
        with patch.object(AIReplyService, "_generate_and_send") as mock_send:
            dispatched = AIReplyService.dispatch_due_replies()

        self.assertEqual(dispatched, 1)
        mock_send.assert_called_once_with(conversation.pk, task_id="legacy-task")

    def test_skips_future_pending_reply(self):
        due_at = timezone.now() + timedelta(minutes=2)
        conversation = self.make_conversation(
            pending=True, task_id="t1", due_at=due_at
        )
        with patch.object(AIReplyService, "_generate_and_send") as mock_send:
            dispatched = AIReplyService.dispatch_due_replies()

        self.assertEqual(dispatched, 0)
        mock_send.assert_not_called()
        conversation.refresh_from_db()
        self.assertEqual(conversation.ai_reply_due_at, due_at)

    def test_skips_inactive_and_non_pending_conversations(self):
        self.make_conversation(
            conversation_id="zc-1",
            active=False,
            pending=True,
            due_at=timezone.now() - timedelta(seconds=1),
        )
        self.make_conversation(
            conversation_id="zc-2",
            active=True,
            pending=False,
            due_at=timezone.now() - timedelta(seconds=1),
        )
        with patch.object(AIReplyService, "_generate_and_send") as mock_send:
            dispatched = AIReplyService.dispatch_due_replies()

        self.assertEqual(dispatched, 0)
        mock_send.assert_not_called()

    def test_claimed_reply_is_not_dispatched_twice(self):
        self.make_conversation(
            pending=True,
            task_id="t1",
            due_at=timezone.now() - timedelta(seconds=1),
        )
        with patch.object(AIReplyService, "_generate_and_send") as mock_send:
            first = AIReplyService.dispatch_due_replies()
            second = AIReplyService.dispatch_due_replies()

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        mock_send.assert_called_once()

    def test_failed_generation_is_retried_after_lease(self):
        conversation = self.make_conversation(
            pending=True,
            task_id="t1",
            due_at=timezone.now() - timedelta(seconds=1),
        )
        with patch.object(
            AIReplyService, "_generate_and_send", side_effect=RuntimeError("boom")
        ) as mock_send:
            first = AIReplyService.dispatch_due_replies()

        self.assertEqual(first, 1)
        mock_send.assert_called_once()

        conversation.refresh_from_db()
        conversation.ai_reply_due_at = timezone.now() - timedelta(seconds=1)
        conversation.save(update_fields=["ai_reply_due_at"])

        with patch.object(AIReplyService, "_generate_and_send") as retry:
            second = AIReplyService.dispatch_due_replies()

        self.assertEqual(second, 1)
        retry.assert_called_once_with(conversation.pk, task_id="t1")


class ClearAIReplyQueueCommandTest(MessagingTestCase):
    @patch("message.management.commands.clear_ai_reply_queue.revoke_task")
    def test_clears_pending_ai_replies(self, mock_revoke):
        due_at = timezone.now() + timedelta(minutes=2)
        conversation = self.make_conversation(
            pending=True, task_id="t1", due_at=due_at
        )
        non_pending = self.make_conversation(
            conversation_id="zc-2", pending=False, task_id="t2", due_at=due_at
        )

        with patch(
            "message.management.commands.clear_ai_reply_queue."
            "MessagingBroadcaster.broadcast_conversation_updated"
        ) as mock_broadcast:
            call_command("clear_ai_reply_queue", stdout=StringIO())

        conversation.refresh_from_db()
        non_pending.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)
        self.assertIsNone(conversation.ai_reply_task_id)
        self.assertIsNone(conversation.ai_reply_due_at)
        self.assertFalse(non_pending.ai_reply_pending)
        self.assertEqual(non_pending.ai_reply_task_id, "t2")
        mock_revoke.assert_called_once_with("t1")
        mock_broadcast.assert_called_once_with(conversation)

    @patch("message.management.commands.clear_ai_reply_queue.revoke_task")
    @patch(
        "message.management.commands.clear_ai_reply_queue.purge_broker_queues",
        return_value=2,
    )
    def test_purge_broker_option(self, mock_purge, mock_revoke):
        conversation = self.make_conversation(
            pending=True,
            task_id="t1",
            due_at=timezone.now() + timedelta(minutes=2),
        )
        output = StringIO()

        call_command("clear_ai_reply_queue", "--purge-broker", stdout=output)

        mock_purge.assert_called_once()
        mock_revoke.assert_called_once_with("t1")
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)
        self.assertIsNone(conversation.ai_reply_due_at)
        self.assertIn("Purged 2", output.getvalue())


class HumanTakeoverTest(MessagingTestCase):
    def test_human_reply_deactivates_ai(self):
        conversation = self.make_conversation(active=True, pending=True)
        user = User.objects.create_user(username="admin", password="secret")

        MessagingService().send_message(
            conversation_id=str(conversation.pk),
            message_text="Hi, this is a human.",
            user=user,
        )

        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_replies_active)
        self.assertFalse(conversation.ai_reply_pending)

        message = conversation.messages.filter(direction="OUTBOUND").first()
        self.assertFalse(message.is_ai_generated)
        self.assertEqual(message.sent_by, user)

    def test_ai_send_keeps_ai_active(self):
        conversation = self.make_conversation(active=True, pending=True)
        MessagingService().send_message(
            conversation_id=str(conversation.pk),
            message_text="Automated reply",
            is_ai_generated=True,
        )
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_replies_active)
        self.assertTrue(
            conversation.messages.get(direction="OUTBOUND").is_ai_generated
        )


class ResumeAITest(MessagingTestCase):
    def test_serializer_exposes_ai_flags(self):
        conversation = self.make_conversation(active=False, pending=True)
        data = ConversationSerializer(conversation).data
        self.assertIn("ai_replies_active", data)
        self.assertIn("ai_reply_pending", data)
        self.assertIn("ai_chat_enabled", data)
        self.assertFalse(data["ai_replies_active"])
        self.assertTrue(data["ai_reply_pending"])

    def test_activate_clears_pending_and_reactivates(self):
        conversation = self.make_conversation(active=False, pending=True)
        AIReplyService.activate(conversation)
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_replies_active)
        self.assertFalse(conversation.ai_reply_pending)

    def test_resume_endpoint_reactivates_conversation(self):
        conversation = self.make_conversation(
            active=False,
            pending=True,
            due_at=timezone.now() + timedelta(minutes=2),
        )
        response = self.client.post(
            f"/api/conversations/{conversation.pk}/ai/resume/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ai_replies_active"])
        self.assertFalse(response.data["ai_reply_pending"])

        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_replies_active)
        self.assertFalse(conversation.ai_reply_pending)
        self.assertIsNone(conversation.ai_reply_due_at)

    def test_inbound_after_resume_schedules_reply(self):
        conversation = self.make_conversation(active=False, pending=False)
        AIReplyService.activate(conversation)
        conversation.refresh_from_db()
        scheduled = AIReplyService.maybe_schedule_reply(conversation)
        self.assertTrue(scheduled)
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_reply_pending)
        self.assertIsNotNone(conversation.ai_reply_due_at)

    def test_takeover_endpoint_deactivates_conversation(self):
        conversation = self.make_conversation(active=True, pending=True)
        response = self.client.post(
            f"/api/conversations/{conversation.pk}/ai/takeover/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["ai_replies_active"])
        self.assertFalse(response.data["ai_reply_pending"])

        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_replies_active)
        self.assertFalse(conversation.ai_reply_pending)


class SignatureTest(TestCase):
    def test_signature_appended(self):
        reply = AIReplyService._with_signature("We deliver hai.")
        self.assertTrue(reply.endswith("- Calleatmandu bot"))
        self.assertIn("We deliver hai.", reply)

    def test_signature_not_duplicated(self):
        signed = "We deliver hai. - Calleatmandu bot"
        self.assertEqual(AIReplyService._with_signature(signed), signed)

    def test_empty_reply_unchanged(self):
        self.assertEqual(AIReplyService._with_signature(""), "")

    @override_settings(AI_REPLY_SIGNATURE="")
    def test_empty_signature_leaves_reply_unchanged(self):
        self.assertEqual(AIReplyService._with_signature("Hello"), "Hello")


class LanguageDetectionTest(TestCase):
    def test_devanagari_detected(self):
        self.assertEqual(detect_reply_language("खानाको मूल्य कति हो?"), "devanagari")
        self.assertEqual(
            detect_reply_language("तपाईंको मेनु कस्तो छ?"), "devanagari"
        )

    def test_romanized_strong_word_detected(self):
        self.assertEqual(detect_reply_language("khaana ko mulya kati ho?"), "romanized")
        self.assertEqual(detect_reply_language("yo katti ko ho?"), "romanized")

    def test_romanized_two_common_words_detected(self):
        self.assertEqual(detect_reply_language("yo chai ma ko lagi ho"), "romanized")

    def test_problem_sentence_detected_as_romanized(self):
        self.assertEqual(
            detect_reply_language("khaana kati chhito deliver huncha?"), "romanized"
        )

    def test_english_not_detected(self):
        for text in (
            "Give me the menu",
            "What is the delivery time?",
            "ok",
            "Menu",
            "delivery time?",
            "How much is momo?",
        ):
            self.assertIsNone(detect_reply_language(text), text)

    def test_empty_not_detected(self):
        self.assertIsNone(detect_reply_language(""))
        self.assertIsNone(detect_reply_language(None))


class LanguagePromptTest(MessagingTestCase):
    def _system_prompt_for(self, text):
        conversation = self.make_conversation()
        Message.objects.create(
            zernio_message_id="m-lang",
            conversation=conversation,
            content=text,
            direction="INBOUND",
        )
        final = {"message": {"role": "assistant", "content": "reply"}}
        with patch.object(OllamaService, "chat", return_value=final):
            AIReplyService._generate_reply(conversation)
            called = OllamaService.chat.call_args_list
        self.assertTrue(called)
        return called[0].args[0][0]["content"]

    def test_devanagari_message_injects_instruction(self):
        prompt = self._system_prompt_for("खानाको मूल्य कति हो?")
        self.assertIn("The customer is writing in Devanagari Nepali.", prompt)

    def test_romanized_message_injects_instruction(self):
        prompt = self._system_prompt_for("khaana ko mulya kati ho?")
        self.assertIn("The customer is writing in romanized Nepali", prompt)

    def test_english_message_uses_generic_rule(self):
        prompt = self._system_prompt_for("Give me the menu")
        self.assertNotIn("The customer is writing in", prompt)

    def test_detection_flag_disables_hint(self):
        conversation = self.make_conversation()
        Message.objects.create(
            zernio_message_id="m-lang2",
            conversation=conversation,
            content="खानाको मूल्य कति हो?",
            direction="INBOUND",
        )
        final = {"message": {"role": "assistant", "content": "reply"}}
        with override_settings(AI_REPLY_LANGUAGE_DETECT=False):
            with patch.object(OllamaService, "chat", return_value=final):
                AIReplyService._generate_reply(conversation)
                called = OllamaService.chat.call_args_list
        self.assertNotIn(
            "The customer is writing in", called[0].args[0][0]["content"]
        )

    def test_romanized_prompt_includes_style_guide_and_examples(self):
        prompt = self._system_prompt_for("khaana kati chhito deliver huncha?")
        self.assertIn("Romanized Nepali style", prompt)
        self.assertIn("Examples of the TONE and FORMAT only", prompt)

    def test_romanized_prompt_covers_all_intents(self):
        prompt = self._system_prompt_for("khaana kati chhito deliver huncha?")
        for snippet in (
            "deliver huncha",
            "menu pathaunus",
            "kati parcha",
            "payment kasari",
            "discount cha",
            "order kahaan pugyo",
            "order cancel garna milcha",
        ):
            self.assertIn(snippet, prompt)

    def test_prompt_forbids_inventing_facts(self):
        prompt = self._system_prompt_for("khaana kati chhito deliver huncha?")
        self.assertIn("Never invent prices", prompt)
        self.assertIn("never invent Nepali words", prompt)

    def test_romanized_prompt_has_hard_script_and_pronoun_rules(self):
        prompt = self._system_prompt_for("khaana kati chhito deliver huncha?")
        self.assertIn("ONLY the Latin alphabet", prompt)
        self.assertIn('Address the customer as "tapai"', prompt)
        self.assertIn("no markdown", prompt.lower())
        self.assertIn("Never use \"timi\"", prompt)

    def test_romanized_prompt_has_contrastive_examples(self):
        prompt = self._system_prompt_for("khaana kati chhito deliver huncha?")
        self.assertIn("WRONG and RIGHT", prompt)

    def test_prompt_has_final_reminders(self):
        prompt = self._system_prompt_for("khaana kati chhito deliver huncha?")
        self.assertIn("Final reminders for this reply", prompt)

    def test_ordering_instructions_included_when_enabled(self):
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            prompt = self._system_prompt_for("momo euta order garna cha")
        self.assertIn("Ordering:", prompt)
        self.assertIn("create_order", prompt)

    def test_ordering_instructions_hidden_when_disabled(self):
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            prompt = self._system_prompt_for("momo euta order garna cha")
        self.assertNotIn("Ordering:", prompt)
        self.assertNotIn("create_order", prompt)
        self.assertIn("while their order request is processed", prompt)

    def test_cancellation_instructions_included_when_enabled(self):
        with override_settings(
            AI_ORDER_CANCELLATION_ENABLED=True,
            AI_ORDER_CANCELLATION_WINDOW_MINUTES=10,
        ):
            prompt = self._system_prompt_for("mero order cancel garna cha")
        self.assertIn("Cancelling orders:", prompt)
        self.assertIn("cancel_order", prompt)
        self.assertIn("10 minutes", prompt)

    def test_cancellation_instructions_hidden_when_disabled(self):
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=False):
            prompt = self._system_prompt_for("mero order cancel garna cha")
        self.assertNotIn("Cancelling orders:", prompt)
        self.assertNotIn("cancel_order", prompt)
        self.assertIn("while their cancellation request is processed", prompt)


class FabricatedOrderGuardTest(MessagingTestCase):
    def _conversation(self, inbound="momo euta order garna cha"):
        conversation = self.make_conversation()
        Message.objects.create(
            zernio_message_id="m-fab",
            conversation=conversation,
            content=inbound,
            direction="INBOUND",
        )
        return conversation

    def test_fabricated_order_number_replaced_when_disabled(self):
        conversation = self._conversation(inbound="I want to place an order")
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            with patch.object(
                OllamaService,
                "generate_with_tools",
                return_value="Your order is confirmed. Order number ORD_123456.",
            ):
                reply = AIReplyService._generate_reply(conversation)
        self.assertNotIn("ORD_123456", reply)
        self.assertEqual(reply, AIReplyService._ORDER_DEFERRAL_REPLY_DEFAULT)

    def test_fabricated_order_number_uses_romanized_deferral(self):
        conversation = self._conversation(inbound="momo euta order garna cha")
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            with patch.object(
                OllamaService,
                "generate_with_tools",
                return_value="Order placed hai. ORD_123456",
            ):
                reply = AIReplyService._generate_reply(conversation)
        self.assertEqual(reply, AIReplyService._ORDER_DEFERRAL_REPLY["romanized"])

    def test_fabricated_order_number_kept_when_creation_enabled(self):
        conversation = self._conversation()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            with patch.object(
                OllamaService,
                "generate_with_tools",
                return_value="Your order is confirmed. Order number ORD_123456.",
            ):
                reply = AIReplyService._generate_reply(conversation)
        self.assertIn("ORD_123456", reply)

    def test_customer_supplied_order_number_is_preserved(self):
        conversation = self._conversation(
            inbound="mero order number ORD_555555 ho, cancel garna cha"
        )
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            with patch.object(
                OllamaService,
                "generate_with_tools",
                return_value="Tapai ko order ORD_555555 barema sodhnu bhayo.",
            ):
                reply = AIReplyService._generate_reply(conversation)
        self.assertIn("ORD_555555", reply)

    def test_devanagari_deferral_for_devanagari_customer(self):
        conversation = self._conversation(inbound="मेरो अर्डर गर्नु छ")
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            with patch.object(
                OllamaService,
                "generate_with_tools",
                return_value="तपाईंको अर्डर प्लेस भयो। ORD_999999",
            ):
                reply = AIReplyService._generate_reply(conversation)
        self.assertEqual(reply, AIReplyService._ORDER_DEFERRAL_REPLY["devanagari"])


class RomanizedScriptGuardTest(MessagingTestCase):
    def _conversation(self):
        conversation = self.make_conversation()
        Message.objects.create(
            zernio_message_id="m-in",
            conversation=conversation,
            content="khaana kati chhito deliver huncha?",
            direction="INBOUND",
        )
        return conversation

    def test_devanagari_leak_triggers_corrective_retry(self):
        conversation = self._conversation()
        responses = ["ठिक छ hai, 30 min lagcha.", "Thik chha hai, 30 min lagcha."]
        with patch.object(
            OllamaService, "generate_with_tools", side_effect=responses
        ) as mock_gen:
            reply = AIReplyService._generate_reply(conversation)
        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(reply, "Thik chha hai, 30 min lagcha.")
        self.assertFalse(AIReplyService._contains_devanagari(reply))

    def test_retry_keeps_original_when_retry_still_mixed(self):
        conversation = self._conversation()
        with patch.object(
            OllamaService,
            "generate_with_tools",
            side_effect=["ai ठिक", "still ठीक छ"],
        ) as mock_gen:
            reply = AIReplyService._generate_reply(conversation)
        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(reply, "ai ठिक")

    def test_no_retry_when_reply_is_clean(self):
        conversation = self._conversation()
        with patch.object(
            OllamaService, "generate_with_tools", return_value="Thik chha hai."
        ) as mock_gen:
            reply = AIReplyService._generate_reply(conversation)
        self.assertEqual(mock_gen.call_count, 1)
        self.assertEqual(reply, "Thik chha hai.")

    def test_whitespace_normalization(self):
        self.assertEqual(
            AIReplyService._normalize_whitespace("30\u202f-\u202f40 min"),
            "30 - 40 min",
        )
        self.assertEqual(AIReplyService._normalize_whitespace("a\u00a0b"), "a b")

    def test_devanagari_helpers(self):
        self.assertTrue(AIReplyService._contains_devanagari("ठीक छ"))
        self.assertFalse(AIReplyService._contains_devanagari("thik chha"))
        self.assertEqual(AIReplyService._devanagari_count("ठीक छ"), 4)


class HistoryScriptFilterTest(MessagingTestCase):
    def test_devanagari_assistant_turn_dropped_for_romanized_target(self):
        conversation = self.make_conversation()
        Message.objects.create(
            zernio_message_id="m1",
            conversation=conversation,
            content="ठीक छ, 30 मिनेट लाग्छ।",
            direction="OUTBOUND",
        )
        Message.objects.create(
            zernio_message_id="m2",
            conversation=conversation,
            content="khaana kati?",
            direction="INBOUND",
        )
        history = AIReplyService._build_history(conversation, language_hint="romanized")
        roles = [m["role"] for m in history]
        self.assertNotIn("assistant", roles)
        self.assertEqual(history[-1]["content"], "khaana kati?")

    def test_signature_stripped_from_history(self):
        conversation = self.make_conversation()
        Message.objects.create(
            zernio_message_id="m3",
            conversation=conversation,
            content="Thik chha. - Calleatmandu bot",
            direction="OUTBOUND",
        )
        history = AIReplyService._build_history(conversation, language_hint="romanized")
        self.assertEqual(history[-1]["content"], "Thik chha.")


class OllamaOptionsTest(TestCase):
    def _capture_payload(self, **service_kwargs):
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"message": {"role": "assistant", "content": "hi"}}
        with patch(
            "message.services.ollama_service.httpx.post", return_value=fake
        ) as mock_post:
            OllamaService(api_key="test-key", **service_kwargs).chat(
                [{"role": "user", "content": "hi"}]
            )
        return mock_post.call_args.kwargs["json"]

    def test_default_generation_options_are_sent(self):
        payload = self._capture_payload()
        self.assertEqual(payload["options"]["temperature"], 0.7)
        self.assertEqual(payload["options"]["top_p"], 0.9)

    @override_settings(OLLAMA_TEMPERATURE=0.2, OLLAMA_TOP_P=0.5)
    def test_settings_override_generation_options(self):
        payload = self._capture_payload()
        self.assertEqual(payload["options"]["temperature"], 0.2)
        self.assertEqual(payload["options"]["top_p"], 0.5)

    def test_explicit_options_override_settings(self):
        payload = self._capture_payload(options={"temperature": 1.0})
        self.assertEqual(payload["options"], {"temperature": 1.0})


class ReplyQualityTest(TestCase):
    def test_good_romanized_reply_scores_well(self):
        metrics = assess_reply(
            "Usually 30-40 min jati lagcha hai. Location ra traffic anusar "
            "ali time farak parna sakcha.",
            language="romanized",
        )
        self.assertTrue(metrics["language_consistent"])
        self.assertTrue(metrics["is_concise"])
        self.assertGreaterEqual(metrics["naturalness_score"], 2)

    def test_pure_english_is_language_inconsistent(self):
        metrics = assess_reply(
            "Yes we deliver within thirty minutes.", language="romanized"
        )
        self.assertFalse(metrics["language_consistent"])
        self.assertEqual(metrics["romanized_marker_hits"], 0)

    def test_devanagari_leak_fails_romanized(self):
        metrics = assess_reply("हामी deliver garcha hai", language="romanized")
        self.assertFalse(metrics["language_consistent"])
        self.assertTrue(metrics["has_devanagari"])

    def test_leftover_placeholder_is_flagged(self):
        metrics = assess_reply(
            "Chicken momo ko price Rs. XXX parcha hai.", language="romanized"
        )
        self.assertTrue(metrics["has_placeholder"])

    def test_devanagari_expected_is_consistent(self):
        metrics = assess_reply(
            "हामीले ३० मिनेटमा deliver गर्छौं।", language="devanagari"
        )
        self.assertTrue(metrics["language_consistent"])

    def test_empty_reply(self):
        self.assertTrue(assess_reply("", language="romanized")["empty"])


class OllamaToolLoopTest(TestCase):
    def test_tool_call_is_executed_and_final_answer_returned(self):
        tool_call = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_faq",
                            "arguments": {"query": "delivery"},
                        }
                    }
                ],
            }
        }
        final = {"message": {"role": "assistant", "content": "We're open 9-5."}}
        executed = []

        def fake_tool(name, arguments):
            executed.append((name, arguments))
            return json.dumps({"answer": "9-5"})

        service = OllamaService(api_key="test-key")
        with patch.object(
            OllamaService, "chat", side_effect=[tool_call, final]
        ) as mock_chat:
            reply = service.generate_with_tools(
                [{"role": "user", "content": "hours?"}],
                tools=[{"type": "function", "function": {"name": "search_faq"}}],
                execute_tool=fake_tool,
            )

        self.assertEqual(reply, "We're open 9-5.")
        self.assertEqual(executed, [("search_faq", {"query": "delivery"})])

        second_messages = mock_chat.call_args_list[1].args[0]
        self.assertTrue(
            any(msg.get("role") == "tool" for msg in second_messages)
        )

    def test_tool_limit_returns_without_final_answer(self):
        tool_call = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "search_faq", "arguments": {"query": "x"}}}
                ],
            }
        }
        service = OllamaService(api_key="test-key")
        with patch.object(OllamaService, "chat", return_value=tool_call):
            reply = service.generate_with_tools(
                [{"role": "user", "content": "hi"}],
                tools=[{"type": "function", "function": {"name": "search_faq"}}],
                execute_tool=lambda name, args: "{}",
                max_tool_calls=2,
            )
        self.assertEqual(reply, "")


class ExecuteToolTest(TestCase):
    def test_search_faq_returns_matches(self):
        Faq.objects.create(question="Do you deliver?", answer="Yes, within 10 km.")
        result = json.loads(execute_tool("search_faq", {"query": "deliver"}))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["answer"], "Yes, within 10 km.")

    def test_get_branch_info_returns_branch(self):
        branch = Branch.objects.create(
            name="Lazimpat", address="Lazimpat, Kathmandu", latitude=27.7, longitude=85.3, phone="9800000000"
        )
        result = json.loads(execute_tool("get_branch_info", {}, branch_id=branch.pk))
        self.assertEqual(result["name"], "Lazimpat")
        self.assertEqual(result["phone"], "9800000000")

    def test_unknown_tool_returns_error(self):
        result = json.loads(execute_tool("does_not_exist", {}))
        self.assertIn("error", result)

    def test_unexpected_arguments_are_ignored(self):
        result = json.loads(
            execute_tool("search_faq", {"query": "delivery", "bogus": "ignored"})
        )
        self.assertIsInstance(result, list)

    def test_search_menu_generic_query_returns_full_menu(self):
        Product.objects.create(
            name="Chicken Momo", description="Steamed dumplings", price=150.0
        )
        Product.objects.create(
            name="Cheese Ball", description="Fried cheese", price=200.0
        )
        for query in ("menu", "full menu", "show me the menu"):
            result = json.loads(execute_tool("search_menu", {"query": query}))
            self.assertEqual(len(result), 2, query)

    def test_search_menu_specific_query_filters(self):
        Product.objects.create(
            name="Chicken Momo", description="Steamed dumplings", price=150.0
        )
        Product.objects.create(
            name="Cheese Ball", description="Fried cheese", price=200.0
        )
        result = json.loads(execute_tool("search_menu", {"query": "momo"}))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Chicken Momo")

    def test_search_menu_empty_db_returns_empty_list(self):
        result = json.loads(execute_tool("search_menu", {"query": "menu"}))
        self.assertEqual(result, [])

    def test_search_faq_generic_query_returns_all(self):
        Faq.objects.create(question="Do you deliver?", answer="Yes, within 10 km.")
        Faq.objects.create(question="Do you take cards?", answer="Yes, we do.")
        result = json.loads(execute_tool("search_faq", {"query": "questions"}))
        self.assertEqual(len(result), 2)

    def test_enabled_tool_schemas_hides_create_order_by_default(self):
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            names = {s["function"]["name"] for s in get_enabled_tool_schemas()}
        self.assertNotIn("create_order", names)

    def test_enabled_tool_schemas_includes_create_order_when_enabled(self):
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            names = {s["function"]["name"] for s in get_enabled_tool_schemas()}
        self.assertIn("create_order", names)

    def test_enabled_tool_schemas_hides_cancel_order_by_default(self):
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=False):
            names = {s["function"]["name"] for s in get_enabled_tool_schemas()}
        self.assertNotIn("cancel_order", names)

    def test_enabled_tool_schemas_includes_cancel_order_when_enabled(self):
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            names = {s["function"]["name"] for s in get_enabled_tool_schemas()}
        self.assertIn("cancel_order", names)


class AiCreateOrderToolTest(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )

    def _product(self, name="Chicken Momo", price=150.0):
        return Product.objects.create(name=name, description=name, price=price)

    def _context(self):
        return {
            "conversation_id": "1",
            "participant_name": "Sam",
            "created_order": None,
        }

    def _create(self, **kwargs):
        return json.loads(
            execute_tool(
                "create_order",
                kwargs,
                branch_id=self.branch.pk,
                context=self._context(),
            )
        )

    def test_disabled_returns_error(self):
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            result = self._create(
                items=[{"name": "Chicken Momo", "quantity": 2}],
                phone_number="9801234567",
                delivery_location="Kamaladi",
            )
        self.assertIn("error", result)
        self.assertEqual(Order.objects.count(), 0)

    def test_creates_delivery_order(self):
        self._product()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = self._create(
                items=[{"name": "Chicken Momo", "quantity": 2}],
                phone_number="9801234567",
                delivery_location="Kamaladi, Kathmandu",
            )
        order = Order.objects.get()
        self.assertEqual(result["order_number"], order.order_number)
        self.assertEqual(order.branch_id, self.branch.pk)
        self.assertEqual(order.status, Order.OrderStatus.PENDING)
        self.assertEqual(order.payment_type, Order.PaymentType.COD)
        self.assertEqual(order.phone_number, "9801234567")
        self.assertEqual(order.delivery_location, "Kamaladi, Kathmandu")
        self.assertEqual(order.customer_name, "Sam")
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(order.total_amount, 300.0)

    def test_missing_phone_returns_error(self):
        self._product()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = self._create(
                items=[{"name": "Chicken Momo", "quantity": 1}],
                delivery_location="Kamaladi",
            )
        self.assertIn("phone", result["error"].lower())
        self.assertEqual(Order.objects.count(), 0)

    def test_missing_address_returns_error(self):
        self._product()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = self._create(
                items=[{"name": "Chicken Momo", "quantity": 1}],
                phone_number="9801234567",
            )
        self.assertIn("address", result["error"].lower())
        self.assertEqual(Order.objects.count(), 0)

    def test_unknown_item_returns_error(self):
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = self._create(
                items=[{"name": "Pizza", "quantity": 1}],
                phone_number="9801234567",
                delivery_location="Kamaladi",
            )
        self.assertIn("error", result)
        self.assertEqual(Order.objects.count(), 0)

    def test_ambiguous_item_returns_candidates(self):
        self._product("Chicken Momo")
        self._product("Chicken Chowmein")
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = self._create(
                items=[{"name": "chicken", "quantity": 1}],
                phone_number="9801234567",
                delivery_location="Kamaladi",
            )
        candidates = result["items"][0].get("candidates") or []
        self.assertEqual(sorted(candidates), ["Chicken Chowmein", "Chicken Momo"])
        self.assertEqual(Order.objects.count(), 0)

    def test_takeaway_needs_no_address(self):
        self._product()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = self._create(
                items=[{"name": "Chicken Momo", "quantity": 1}],
                order_type="TAKEAWAY",
            )
        order = Order.objects.get()
        self.assertEqual(order.order_type, Order.OrderType.TAKEAWAY)
        self.assertIn("order_number", result)

    def test_nps_rejected(self):
        self._product()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = self._create(
                items=[{"name": "Chicken Momo", "quantity": 1}],
                phone_number="9801234567",
                delivery_location="Kamaladi",
                payment_type="NPS",
            )
        self.assertIn("error", result)
        self.assertEqual(Order.objects.count(), 0)

    def test_context_dedup_within_generation(self):
        self._product()
        context = self._context()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            first = json.loads(
                execute_tool(
                    "create_order",
                    {
                        "items": [{"name": "Chicken Momo", "quantity": 1}],
                        "phone_number": "9801234567",
                        "delivery_location": "Kamaladi",
                    },
                    branch_id=self.branch.pk,
                    context=context,
                )
            )
            second = json.loads(
                execute_tool(
                    "create_order",
                    {
                        "items": [{"name": "Chicken Momo", "quantity": 1}],
                        "phone_number": "9801234567",
                        "delivery_location": "Kamaladi",
                    },
                    branch_id=self.branch.pk,
                    context=context,
                )
            )
        self.assertEqual(second["order_number"], first["order_number"])
        self.assertEqual(Order.objects.count(), 1)

    def test_window_dedup_reuses_recent_pending_order(self):
        self._product()
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            first = self._create(
                items=[{"name": "Chicken Momo", "quantity": 1}],
                phone_number="9801234567",
                delivery_location="Kamaladi",
            )
            second = self._create(
                items=[{"name": "Chicken Momo", "quantity": 1}],
                phone_number="980 1234567",
                delivery_location="Kamaladi",
            )
        self.assertEqual(second["order_number"], first["order_number"])
        self.assertEqual(Order.objects.count(), 1)


class AiCancelOrderToolTest(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )

    def _order(
        self,
        phone="9801234567",
        status=Order.OrderStatus.PENDING,
        branch=None,
    ):
        return Order.objects.create(
            branch=branch or self.branch,
            customer_name="Sam",
            phone_number=phone,
            delivery_location="Kamaladi, Kathmandu",
            subtotal=300.0,
            payment_type=Order.PaymentType.COD,
            order_type=Order.OrderType.DELIVERY,
            status=status,
        )

    def _cancel(self, order_number, phone=None):
        return json.loads(
            execute_tool(
                "cancel_order",
                {"order_number": order_number, "phone_number": phone},
                branch_id=self.branch.pk,
            )
        )

    def test_disabled_returns_error(self):
        order = self._order()
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=False):
            result = self._cancel(order.order_number, "9801234567")
        self.assertIn("error", result)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PENDING)

    def test_requires_phone(self):
        order = self._order()
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(order.order_number, None)
        self.assertIn("phone", result["error"].lower())
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PENDING)

    def test_unknown_order_returns_error(self):
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel("ORD_000000", "9801234567")
        self.assertIn("error", result)

    def test_phone_mismatch_rejected(self):
        order = self._order(phone="9801234567")
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(order.order_number, "9811111111")
        self.assertIn("error", result)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PENDING)

    def test_branch_mismatch_rejected(self):
        other_branch = Branch.objects.create(
            name="Baneshwor",
            address="Baneshwor, Kathmandu",
            latitude=27.6,
            longitude=85.4,
            phone="9800000001",
        )
        order = self._order(branch=other_branch)
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(order.order_number, "9801234567")
        self.assertIn("error", result)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PENDING)

    def test_already_cancelled_returns_error(self):
        order = self._order(status=Order.OrderStatus.CANCELLED)
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(order.order_number, "9801234567")
        self.assertIn("already been cancelled", result["error"].lower())

    def test_non_cancellable_status_rejected(self):
        order = self._order(status=Order.OrderStatus.DELIVERED)
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(order.order_number, "9801234567")
        self.assertIn("error", result)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.DELIVERED)

    def test_past_window_rejected(self):
        order = self._order()
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(minutes=30)
        )
        with override_settings(
            AI_ORDER_CANCELLATION_ENABLED=True,
            AI_ORDER_CANCELLATION_WINDOW_MINUTES=10,
        ):
            result = self._cancel(order.order_number, "9801234567")
        self.assertIn("error", result)
        self.assertEqual(result.get("window_minutes"), 10)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PENDING)

    def test_successful_cancel(self):
        order = self._order()
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(order.order_number, "9801234567")
        self.assertNotIn("error", result)
        self.assertEqual(result["order_number"], order.order_number)
        self.assertEqual(result["status"], Order.OrderStatus.CANCELLED)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.CANCELLED)
        history = order.status_history.filter(status=Order.OrderStatus.CANCELLED)
        self.assertTrue(history.exists())
        self.assertEqual(
            history.first().comment, "Cancelled by customer via chat"
        )

    def test_matches_phone_with_formatting_differences(self):
        order = self._order(phone="+977 9801234567")
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(order.order_number, "9801234567")
        self.assertNotIn("error", result)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.CANCELLED)

    def test_accepts_prefix_variant(self):
        order = self._order()
        variant = "EAT_" + order.order_number[4:]
        with override_settings(AI_ORDER_CANCELLATION_ENABLED=True):
            result = self._cancel(variant, "9801234567")
        self.assertNotIn("error", result)
        self.assertEqual(result["order_number"], order.order_number)


class MessagingScopingBase(TestCase):
    def setUp(self):
        self.branch_a = Branch.objects.create(
            name="Branch A", address="a", latitude=1.0, longitude=1.0, phone="1"
        )
        self.branch_b = Branch.objects.create(
            name="Branch B", address="b", latitude=2.0, longitude=2.0, phone="2"
        )
        self.account_a = BusinessAccount.objects.create(
            branch=self.branch_a,
            zernio_account_id="acc-a",
            platform="instagram",
            account_name="Account A",
        )
        self.account_b = BusinessAccount.objects.create(
            branch=self.branch_b,
            zernio_account_id="acc-b",
            platform="instagram",
            account_name="Account B",
        )

    def make_staff(self, username="staff", branch=None):
        return User.objects.create_user(
            username=username, password="x", role="staff", branch=branch
        )


class AccountAuthorizationTest(MessagingScopingBase):
    def test_admin_is_authorized_for_any_account(self):
        admin = User.objects.create_superuser(username="root", password="x")
        self.assertTrue(is_authorized_for_account(admin, {"id": 1, "branch_id": self.branch_a.id}))
        self.assertTrue(is_authorized_for_account(admin, {"id": 2, "branch_id": None}))

    def test_staff_only_authorized_for_own_branch_account(self):
        staff = self.make_staff(branch=self.branch_a)
        self.assertTrue(is_authorized_for_account(staff, {"id": 1, "branch_id": self.branch_a.id}))
        self.assertFalse(is_authorized_for_account(staff, {"id": 2, "branch_id": self.branch_b.id}))

    def test_staff_without_branch_is_rejected(self):
        staff = self.make_staff(branch=None)
        self.assertFalse(is_authorized_for_account(staff, {"id": 1, "branch_id": self.branch_a.id}))

    def test_customer_is_rejected(self):
        customer = User.objects.create_user(
            username="cust", password="x", role="customer", branch=self.branch_a
        )
        self.assertFalse(is_authorized_for_account(customer, {"id": 1, "branch_id": self.branch_a.id}))

    def test_none_or_anonymous_is_rejected(self):
        self.assertFalse(is_authorized_for_account(None, {"id": 1, "branch_id": None}))

    def test_account_without_branch_is_admin_only(self):
        staff = self.make_staff(branch=self.branch_a)
        self.assertFalse(is_authorized_for_account(staff, {"id": 1, "branch_id": None}))


class MessagingBroadcasterTest(MessagingScopingBase):
    def make_conversation(self, account, suffix="1"):
        return Conversation.objects.create(
            zernio_conversation_id=f"zc-{suffix}",
            zernio_account_id="acc",
            platform="instagram",
            business_account=account,
        )

    @patch.object(MessagingBroadcaster, "_send_to_channel_layer")
    def test_new_message_targets_only_account_group(self, mock_send):
        conversation = self.make_conversation(self.account_a)
        message = Message.objects.create(
            conversation=conversation, content="Hi", direction="INBOUND"
        )
        MessagingBroadcaster.broadcast_new_message(message, conversation)

        mock_send.assert_called_once()
        group, payload = mock_send.call_args.args
        self.assertEqual(group, f"messaging_unread_account_{self.account_a.id}")
        self.assertNotIn("_all", group)
        self.assertEqual(payload["data"]["business_account_id"], str(self.account_a.id))

    @patch.object(MessagingBroadcaster, "_send_to_channel_layer")
    def test_new_message_without_account_is_not_broadcast(self, mock_send):
        conversation = Conversation.objects.create(
            zernio_conversation_id="zc-orphan",
            zernio_account_id="acc",
            platform="instagram",
        )
        message = Message.objects.create(
            conversation=conversation, content="Hi", direction="INBOUND"
        )
        MessagingBroadcaster.broadcast_new_message(message, conversation)
        mock_send.assert_not_called()

    @patch.object(MessagingBroadcaster, "_send_to_channel_layer")
    def test_conversation_events_target_account_group(self, mock_send):
        conversation = self.make_conversation(self.account_b, suffix="2")
        MessagingBroadcaster.broadcast_conversation_created(conversation)
        MessagingBroadcaster.broadcast_conversation_updated(conversation)

        groups = [call.args[0] for call in mock_send.call_args_list]
        self.assertEqual(
            groups,
            [
                f"messaging_conversations_account_{self.account_b.id}",
                f"messaging_conversations_account_{self.account_b.id}",
            ],
        )

    @patch.object(MessagingBroadcaster, "_send_to_channel_layer")
    def test_unread_counts_broadcast_requires_account(self, mock_send):
        MessagingBroadcaster.broadcast_unread_counts_updated(business_account_id=None)
        mock_send.assert_not_called()

        MessagingBroadcaster.broadcast_unread_counts_updated(
            business_account_id=self.account_a.id
        )
        mock_send.assert_called_once()
        self.assertEqual(
            mock_send.call_args.args[0],
            f"messaging_unread_account_{self.account_a.id}",
        )

    @patch.object(MessagingBroadcaster, "_send_to_channel_layer")
    def test_new_message_payload_is_msgpack_safe(self, mock_send):
        conversation = self.make_conversation(self.account_a)
        message = Message.objects.create(
            conversation=conversation, content="Hi", direction="INBOUND"
        )
        MessagingBroadcaster.broadcast_new_message(message, conversation)

        _, payload = mock_send.call_args.args
        unread_counts = payload["data"]["unread_counts"]
        self.assertEqual(unread_counts, {str(conversation.id): 1})
        self.assertTrue(
            all(isinstance(key, str) for key in unread_counts),
            f"unread_counts keys must be strings: {unread_counts!r}",
        )
        # channels_redis uses msgpack with strict_map_key=True, which rejects
        # integer map keys when the consumer deserializes the message.
        self.assertEqual(msgpack.unpackb(msgpack.packb(payload)), payload)

    @patch.object(MessagingBroadcaster, "_send_to_channel_layer")
    def test_unread_counts_update_payload_is_msgpack_safe(self, mock_send):
        conversation = self.make_conversation(self.account_a)
        Message.objects.create(
            conversation=conversation, direction="INBOUND", is_read=False
        )
        MessagingBroadcaster.broadcast_unread_counts_updated(
            business_account_id=self.account_a.id
        )

        _, payload = mock_send.call_args.args
        unread_counts = payload["data"]["unread_counts"]
        self.assertEqual(unread_counts, {str(conversation.id): 1})
        self.assertEqual(msgpack.unpackb(msgpack.packb(payload)), payload)


class AccountSelectorTest(MessagingScopingBase):
    def test_unread_counts_are_scoped_to_account(self):
        conv_a = Conversation.objects.create(
            zernio_conversation_id="zc-a",
            zernio_account_id="acc-a",
            platform="instagram",
            business_account=self.account_a,
        )
        conv_b = Conversation.objects.create(
            zernio_conversation_id="zc-b",
            zernio_account_id="acc-b",
            platform="instagram",
            business_account=self.account_b,
        )
        Message.objects.create(conversation=conv_a, direction="INBOUND", is_read=False)
        Message.objects.create(conversation=conv_a, direction="INBOUND", is_read=True)
        Message.objects.create(conversation=conv_b, direction="INBOUND", is_read=False)

        counts = get_unread_counts_for_account(self.account_a.id)
        self.assertEqual(counts, {str(conv_a.id): 1})

    def test_unread_counts_for_none_is_empty(self):
        self.assertEqual(get_unread_counts_for_account(None), {})

    def test_conversations_scoped_to_account(self):
        conv_a = Conversation.objects.create(
            zernio_conversation_id="zc-a",
            zernio_account_id="acc-a",
            platform="instagram",
            business_account=self.account_a,
        )
        Conversation.objects.create(
            zernio_conversation_id="zc-b",
            zernio_account_id="acc-b",
            platform="instagram",
            business_account=self.account_b,
        )
        ids = list(get_conversations_for_account(self.account_a.id).values_list("id", flat=True))
        self.assertEqual(ids, [conv_a.id])


class MessagingConsumerAuthTest(TransactionTestCase):
    def setUp(self):
        self.branch_a = Branch.objects.create(
            name="Branch A", address="a", latitude=1.0, longitude=1.0, phone="1"
        )
        self.branch_b = Branch.objects.create(
            name="Branch B", address="b", latitude=2.0, longitude=2.0, phone="2"
        )
        self.account_a = BusinessAccount.objects.create(
            branch=self.branch_a,
            zernio_account_id="acc-a",
            platform="instagram",
        )
        self.account_b = BusinessAccount.objects.create(
            branch=self.branch_b,
            zernio_account_id="acc-b",
            platform="instagram",
        )
        self.staff_a = User.objects.create_user(
            username="staff_a", password="x", role="staff", branch=self.branch_a
        )
        self.staff_b = User.objects.create_user(
            username="staff_b", password="x", role="staff", branch=self.branch_b
        )
        self.admin = User.objects.create_superuser(username="root", password="x")
        self.customer = User.objects.create_user(
            username="cust", password="x", role="customer", branch=self.branch_a
        )
        self.app = URLRouter(websocket_urlpatterns)

    def _url(self, account, user, endpoint="unread"):
        token = str(AccessToken.for_user(user))
        return f"/ws/messaging/{endpoint}/account/{account.id}/?token={token}"

    async def test_authorized_staff_connects_and_receives_initial(self):
        comm = WebsocketCommunicator(self.app, self._url(self.account_a, self.staff_a))
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        message = await comm.receive_json_from()
        self.assertEqual(message["event"], "unread_counts.initial")
        self.assertEqual(message["business_account_id"], str(self.account_a.id))
        await comm.disconnect()

    async def test_staff_cannot_connect_to_other_branch_account(self):
        comm = WebsocketCommunicator(self.app, self._url(self.account_b, self.staff_a))
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_customer_is_rejected(self):
        comm = WebsocketCommunicator(self.app, self._url(self.account_a, self.customer))
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_missing_account_is_rejected(self):
        comm = WebsocketCommunicator(
            self.app,
            f"/ws/messaging/unread/account/999999/"
            f"?token={AccessToken.for_user(self.staff_a)}",
        )
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_conversations_consumer_connects(self):
        comm = WebsocketCommunicator(
            self.app,
            self._url(self.account_a, self.staff_a, endpoint="conversations"),
        )
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        message = await comm.receive_json_from()
        self.assertEqual(message["event"], "conversations.initial")
        await comm.disconnect()


class OrderFeatureFlagsResolverTest(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )

    def test_no_branch_uses_default_reply_delay(self):
        with override_settings(
            AI_REPLY_ENABLED=True,
            AI_ORDER_CREATION_ENABLED=True,
            AI_ORDER_CANCELLATION_ENABLED=False,
            AI_ORDER_CANCELLATION_WINDOW_MINUTES=15,
            AI_ORDER_DEDUP_WINDOW_MINUTES=5,
        ):
            flags = get_order_feature_flags(None)
        self.assertTrue(flags.chat_enabled)
        self.assertEqual(flags.reply_delay_seconds, 120)
        self.assertTrue(flags.creation_enabled)
        self.assertFalse(flags.cancellation_enabled)
        self.assertEqual(flags.cancellation_window_minutes, 15)
        self.assertEqual(flags.dedup_window_minutes, 5)

    def test_branch_without_row_uses_default_reply_delay(self):
        with override_settings(
            AI_REPLY_ENABLED=False,
            AI_ORDER_CREATION_ENABLED=True,
        ):
            flags = get_order_feature_flags(self.branch.pk)
        self.assertFalse(flags.chat_enabled)
        self.assertTrue(flags.creation_enabled)
        self.assertEqual(flags.reply_delay_seconds, 120)

    def test_branch_row_defaults_reply_delay(self):
        settings_row = BranchAISettings.objects.create(branch=self.branch)
        self.assertEqual(settings_row.ai_reply_delay_seconds, 120)
        self.assertEqual(
            get_order_feature_flags(self.branch.pk).reply_delay_seconds, 120
        )

    def test_branch_row_can_disable_chat(self):
        BranchAISettings.objects.create(branch=self.branch, ai_chat_enabled=False)
        with override_settings(AI_REPLY_ENABLED=True):
            flags = get_order_feature_flags(self.branch.pk)
        self.assertFalse(flags.chat_enabled)

    def test_null_chat_inherits_env_default(self):
        BranchAISettings.objects.create(branch=self.branch)
        with override_settings(AI_REPLY_ENABLED=True):
            flags = get_order_feature_flags(self.branch.pk)
        self.assertTrue(flags.chat_enabled)

    def test_global_chat_kill_switch_cannot_be_overridden(self):
        BranchAISettings.objects.create(branch=self.branch, ai_chat_enabled=True)
        with override_settings(AI_REPLY_ENABLED=False):
            flags = get_order_feature_flags(self.branch.pk)
        self.assertFalse(flags.chat_enabled)

    def test_branch_row_overrides_defaults(self):
        BranchAISettings.objects.create(
            branch=self.branch,
            ai_reply_delay_seconds=30,
            ai_order_creation_enabled=True,
            ai_order_cancellation_enabled=True,
            ai_order_cancellation_window_minutes=30,
            ai_order_dedup_window_minutes=2,
        )
        with override_settings(
            AI_ORDER_CREATION_ENABLED=False,
            AI_ORDER_CANCELLATION_ENABLED=False,
            AI_ORDER_CANCELLATION_WINDOW_MINUTES=10,
            AI_ORDER_DEDUP_WINDOW_MINUTES=10,
        ):
            flags = get_order_feature_flags(self.branch.pk)
        self.assertEqual(flags.reply_delay_seconds, 30)
        self.assertTrue(flags.creation_enabled)
        self.assertTrue(flags.cancellation_enabled)
        self.assertEqual(flags.cancellation_window_minutes, 30)
        self.assertEqual(flags.dedup_window_minutes, 2)

    def test_null_fields_inherit_env_defaults(self):
        BranchAISettings.objects.create(
            branch=self.branch,
            ai_reply_delay_seconds=90,
            ai_order_creation_enabled=True,
        )
        with override_settings(
            AI_ORDER_CREATION_ENABLED=False,
            AI_ORDER_CANCELLATION_ENABLED=True,
            AI_ORDER_CANCELLATION_WINDOW_MINUTES=12,
        ):
            flags = get_order_feature_flags(self.branch.pk)
        self.assertEqual(flags.reply_delay_seconds, 90)
        self.assertTrue(flags.creation_enabled)
        self.assertTrue(flags.cancellation_enabled)
        self.assertEqual(flags.cancellation_window_minutes, 12)

    def test_resolve_branch_id_prefers_direct_branch(self):
        conversation = Conversation.objects.create(
            zernio_conversation_id="zc-1",
            zernio_account_id="acc-1",
            platform="instagram",
            branch=self.branch,
        )
        self.assertEqual(resolve_conversation_branch_id(conversation), self.branch.pk)

    def test_resolve_branch_id_falls_back_to_business_account(self):
        account = BusinessAccount.objects.create(
            branch=self.branch,
            zernio_account_id="acc-1",
            platform="instagram",
        )
        conversation = Conversation.objects.create(
            zernio_conversation_id="zc-1",
            zernio_account_id="acc-1",
            platform="instagram",
            business_account=account,
        )
        self.assertEqual(resolve_conversation_branch_id(conversation), self.branch.pk)


class BranchOrderFlagToolGatingTest(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )
        self.product = Product.objects.create(
            name="Chicken Momo", description="momo", price=150.0
        )
        self.context = {
            "conversation_id": "1",
            "participant_name": "Sam",
            "created_order": None,
        }

    def test_branch_override_disables_creation_even_when_env_enabled(self):
        BranchAISettings.objects.create(
            branch=self.branch, ai_order_creation_enabled=False
        )
        with override_settings(AI_ORDER_CREATION_ENABLED=True):
            result = json.loads(
                execute_tool(
                    "create_order",
                    {
                        "items": [{"name": "Chicken Momo", "quantity": 1}],
                        "phone_number": "9801234567",
                        "delivery_location": "Kamaladi",
                    },
                    branch_id=self.branch.pk,
                    context=self.context,
                )
            )
        self.assertIn("error", result)
        self.assertEqual(Order.objects.count(), 0)

    def test_branch_override_enables_creation_even_when_env_disabled(self):
        BranchAISettings.objects.create(
            branch=self.branch, ai_order_creation_enabled=True
        )
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            result = json.loads(
                execute_tool(
                    "create_order",
                    {
                        "items": [{"name": "Chicken Momo", "quantity": 1}],
                        "phone_number": "9801234567",
                        "delivery_location": "Kamaladi",
                    },
                    branch_id=self.branch.pk,
                    context=self.context,
                )
            )
        self.assertNotIn("error", result)
        self.assertEqual(Order.objects.count(), 1)

    def test_tool_schemas_respect_branch_override(self):
        BranchAISettings.objects.create(
            branch=self.branch,
            ai_order_creation_enabled=False,
            ai_order_cancellation_enabled=True,
        )
        with override_settings(
            AI_ORDER_CREATION_ENABLED=True,
            AI_ORDER_CANCELLATION_ENABLED=False,
        ):
            names = {
                s["function"]["name"]
                for s in get_enabled_tool_schemas(branch_id=self.branch.pk)
            }
        self.assertNotIn("create_order", names)
        self.assertIn("cancel_order", names)


class ConversationOrderSettingsAPITest(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            name="Lazimpat",
            address="Lazimpat, Kathmandu",
            latitude=27.7,
            longitude=85.3,
            phone="9800000000",
        )
        self.conversation = Conversation.objects.create(
            zernio_conversation_id="zc-1",
            zernio_account_id="acc-1",
            platform="instagram",
            branch=self.branch,
        )
        self.admin = User.objects.create_user(
            username="admin", password="x", role="admin", branch=self.branch
        )
        self.staff = User.objects.create_user(
            username="staff", password="x", role="staff", branch=self.branch
        )

    def _auth(self, user):
        token = str(AccessToken.for_user(user))
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _url(self):
        return f"/api/conversations/{self.conversation.pk}/ai/order-settings/"

    def test_admin_can_update_settings(self):
        self._auth(self.admin)
        response = self.client.post(
            self._url(),
            data=json.dumps(
                {
                    "ai_chat_enabled": True,
                    "ai_reply_delay_seconds": 45,
                    "ai_order_creation_enabled": True,
                    "ai_order_cancellation_enabled": True,
                    "ai_order_cancellation_window_minutes": 25,
                    "ai_order_dedup_window_minutes": 3,
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ai_chat_enabled"])
        self.assertEqual(response.data["ai_reply_delay_seconds"], 45)
        self.assertTrue(response.data["ai_order_creation_enabled"])
        self.assertTrue(response.data["ai_order_cancellation_enabled"])
        self.assertEqual(response.data["ai_order_cancellation_window_minutes"], 25)
        self.assertEqual(response.data["ai_order_dedup_window_minutes"], 3)

        settings_row = BranchAISettings.objects.get(branch=self.branch)
        self.assertTrue(settings_row.ai_chat_enabled)
        self.assertEqual(settings_row.ai_reply_delay_seconds, 45)
        self.assertTrue(settings_row.ai_order_creation_enabled)
        self.assertEqual(settings_row.ai_order_cancellation_window_minutes, 25)

    def test_null_resets_reply_delay_to_default(self):
        BranchAISettings.objects.create(
            branch=self.branch, ai_reply_delay_seconds=30
        )
        self._auth(self.admin)
        response = self.client.post(
            self._url(),
            data=json.dumps({"ai_reply_delay_seconds": None}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["ai_reply_delay_seconds"], 120)
        settings_row = BranchAISettings.objects.get(branch=self.branch)
        self.assertEqual(settings_row.ai_reply_delay_seconds, 120)

    def test_negative_reply_delay_is_rejected(self):
        self._auth(self.admin)
        response = self.client.post(
            self._url(),
            data=json.dumps({"ai_reply_delay_seconds": -1}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_disabling_chat_cancels_pending_replies(self):
        self.conversation.ai_reply_pending = True
        self.conversation.ai_reply_task_id = "t1"
        self.conversation.ai_reply_due_at = timezone.now() + timedelta(minutes=2)
        self.conversation.save(
            update_fields=[
                "ai_reply_pending",
                "ai_reply_task_id",
                "ai_reply_due_at",
            ]
        )
        self._auth(self.admin)

        with patch("message.tasks.revoke_task") as mock_revoke:
            response = self.client.post(
                self._url(),
                data=json.dumps({"ai_chat_enabled": False}),
                content_type="application/json",
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["ai_chat_enabled"])
        mock_revoke.assert_called_once_with("t1")
        self.conversation.refresh_from_db()
        self.assertFalse(self.conversation.ai_reply_pending)
        self.assertIsNone(self.conversation.ai_reply_task_id)
        self.assertIsNone(self.conversation.ai_reply_due_at)

    def test_null_clears_chat_override(self):
        BranchAISettings.objects.create(branch=self.branch, ai_chat_enabled=False)
        self._auth(self.admin)
        with override_settings(AI_REPLY_ENABLED=True):
            response = self.client.post(
                self._url(),
                data=json.dumps({"ai_chat_enabled": None}),
                content_type="application/json",
                **self.auth_headers,
            )
        self.assertEqual(response.status_code, 200)
        settings_row = BranchAISettings.objects.get(branch=self.branch)
        self.assertIsNone(settings_row.ai_chat_enabled)
        self.assertTrue(response.data["ai_chat_enabled"])

    def test_partial_update_only_changes_provided_fields(self):
        BranchAISettings.objects.create(
            branch=self.branch,
            ai_order_creation_enabled=True,
            ai_order_cancellation_window_minutes=40,
        )
        self._auth(self.admin)
        response = self.client.post(
            self._url(),
            data=json.dumps({"ai_order_cancellation_enabled": True}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        settings_row = BranchAISettings.objects.get(branch=self.branch)
        self.assertTrue(settings_row.ai_order_cancellation_enabled)
        self.assertTrue(settings_row.ai_order_creation_enabled)
        self.assertEqual(settings_row.ai_order_cancellation_window_minutes, 40)

    def test_null_clears_override(self):
        BranchAISettings.objects.create(
            branch=self.branch, ai_order_creation_enabled=True
        )
        self._auth(self.admin)
        with override_settings(AI_ORDER_CREATION_ENABLED=False):
            response = self.client.post(
                self._url(),
                data=json.dumps({"ai_order_creation_enabled": None}),
                content_type="application/json",
                **self.auth_headers,
            )
        self.assertEqual(response.status_code, 200)
        settings_row = BranchAISettings.objects.get(branch=self.branch)
        self.assertIsNone(settings_row.ai_order_creation_enabled)
        self.assertFalse(response.data["ai_order_creation_enabled"])

    def test_non_admin_is_forbidden(self):
        self._auth(self.staff)
        response = self.client.post(
            self._url(),
            data=json.dumps({"ai_order_creation_enabled": True}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            BranchAISettings.objects.filter(branch=self.branch).exists()
        )

    def test_anonymous_is_rejected(self):
        response = self.client.post(
            self._url(),
            data=json.dumps({"ai_order_creation_enabled": True}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_conversation_without_branch_returns_400(self):
        orphan = Conversation.objects.create(
            zernio_conversation_id="zc-orphan",
            zernio_account_id="acc-x",
            platform="instagram",
        )
        self._auth(self.admin)
        response = self.client.post(
            f"/api/conversations/{orphan.pk}/ai/order-settings/",
            data=json.dumps({"ai_order_creation_enabled": True}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
