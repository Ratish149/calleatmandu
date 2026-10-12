import json
from unittest.mock import patch

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from message.routing import websocket_urlpatterns

from account.models import Branch, User
from faq.models import Faq
from product.models import Product
from message.consumers import (
    ConversationsConsumer,
    UnreadMessagesConsumer,
    is_authorized_for_account,
)
from message.models import BusinessAccount, Conversation, Message
from message.selectors.messaging_selector import (
    get_conversations_for_account,
    get_unread_counts_for_account,
)
from message.services.ai_reply_service import AIReplyService
from message.services.ai_tools import execute_tool
from message.services.messaging_broadcaster import MessagingBroadcaster
from message.services.messaging_service import MessagingService
from message.services.ollama_service import OllamaError, OllamaService

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


class MessagingTestCase(TestCase):
    def setUp(self):
        patcher = patch("message.services.messaging_service.ZernioService")
        self.mock_zernio_cls = patcher.start()
        self.addCleanup(patcher.stop)

    def make_conversation(self, conversation_id="zc-1", active=True, pending=False):
        return Conversation.objects.create(
            zernio_conversation_id=conversation_id,
            zernio_account_id="acc-1",
            platform="instagram",
            participant_name="Sam",
            ai_replies_active=active,
            ai_reply_pending=pending,
        )


class ZernioWebhookAITest(MessagingTestCase):
    @patch("message.services.messaging_service.AIReplyService.maybe_schedule_reply")
    def test_webhook_creates_conversation_and_schedules_reply(self, mock_schedule):
        response = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(webhook_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        conversation = Conversation.objects.get(zernio_conversation_id="zc-1")
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


class ScheduleReplyTest(MessagingTestCase):
    def test_disabled_setting_skips(self):
        conversation = self.make_conversation()
        with override_settings(AI_REPLY_ENABLED=False):
            scheduled = AIReplyService.maybe_schedule_reply(conversation)
        self.assertFalse(scheduled)
        conversation.refresh_from_db()
        self.assertFalse(conversation.ai_reply_pending)

    def test_already_pending_skips(self):
        conversation = self.make_conversation(pending=True)
        self.assertFalse(AIReplyService.maybe_schedule_reply(conversation))

    def test_inactive_conversation_skips(self):
        conversation = self.make_conversation(active=False)
        self.assertFalse(AIReplyService.maybe_schedule_reply(conversation))

    def test_happy_path_sets_pending_and_starts_thread(self):
        conversation = self.make_conversation()
        with patch("message.services.ai_reply_service.threading.Thread") as mock_thread:
            scheduled = AIReplyService.maybe_schedule_reply(conversation)

        self.assertTrue(scheduled)
        mock_thread.return_value.start.assert_called_once()
        conversation.refresh_from_db()
        self.assertTrue(conversation.ai_reply_pending)


class GenerateAndSendTest(MessagingTestCase):
    def test_ai_reply_is_generated_and_sent(self):
        conversation = self.make_conversation(pending=True)
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
        self.assertEqual(outbound.content, "Yes, we deliver!")
        self.assertTrue(outbound.is_ai_generated)
        self.assertIsNone(outbound.sent_by)

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
        self.assertEqual(counts, {conv_a.id: 1})

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
