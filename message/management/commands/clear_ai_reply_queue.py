import logging

from celery import current_app
from django.core.management.base import BaseCommand

from message.models import Conversation
from message.services.messaging_broadcaster import MessagingBroadcaster
from message.tasks import revoke_task

logger = logging.getLogger(__name__)


def purge_broker_queues():
    """Delete ready Celery messages without requiring a running worker."""
    with current_app.connection_for_write() as connection:
        channel = connection.default_channel
        return sum(
            channel.queue_purge(queue_name)
            for queue_name in current_app.amqp.queues
        )


class Command(BaseCommand):
    help = (
        "Cancel pending AI replies and clear their database state. Use "
        "--purge-broker to also delete all queued Celery messages."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--conversation-id",
            type=str,
            default=None,
            help="Only clear a single conversation by its primary key.",
        )
        parser.add_argument(
            "--purge-broker",
            action="store_true",
            help=(
                "Also purge all messages from the Celery broker queue. This "
                "removes queued tasks for every conversation, not just one."
            ),
        )

    def handle(self, *args, **options):
        queryset = Conversation.objects.filter(ai_reply_pending=True)
        conversation_id = options.get("conversation_id")
        if conversation_id:
            queryset = queryset.filter(pk=conversation_id)

        pending = list(queryset)
        task_ids = [
            conversation.ai_reply_task_id
            for conversation in pending
            if conversation.ai_reply_task_id
        ]

        if options.get("purge_broker"):
            purged = purge_broker_queues()
            self.stdout.write(
                self.style.WARNING(f"Purged {purged} queued Celery message(s).")
            )

        queryset.update(
            ai_reply_pending=False,
            ai_reply_task_id=None,
            ai_reply_due_at=None,
        )

        for task_id in task_ids:
            revoke_task(task_id)

        for conversation in pending:
            conversation.ai_reply_pending = False
            conversation.ai_reply_task_id = None
            conversation.ai_reply_due_at = None
            try:
                MessagingBroadcaster.broadcast_conversation_updated(conversation)
            except Exception:
                logger.exception(
                    "Failed to broadcast conversation update after clearing "
                    "AI reply for conversation %s",
                    conversation.pk,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared pending AI replies for {len(pending)} conversation(s)."
            )
        )
