from django.core.management.base import BaseCommand

from message.models import Conversation


class Command(BaseCommand):
    help = (
        "Re-enable AI auto-replies and clear stale pending flags for conversations. "
        "By default only conversations that were handed over to a human "
        "(ai_replies_active=False) are resumed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--conversation-id",
            type=str,
            default=None,
            help="Only resume a single conversation by its primary key.",
        )
        parser.add_argument(
            "--include-active",
            action="store_true",
            help=(
                "Also clear ai_reply_pending on conversations that are still active "
                "(use this to recover conversations stuck mid-generation)."
            ),
        )

    def handle(self, *args, **options):
        queryset = Conversation.objects.all()

        conversation_id = options.get("conversation_id")
        if conversation_id:
            queryset = queryset.filter(pk=conversation_id)
        elif not options.get("include_active"):
            queryset = queryset.filter(ai_replies_active=False)

        updated = queryset.update(
            ai_replies_active=True, ai_reply_pending=False, ai_reply_task_id=None
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Resumed AI replies for {updated} conversation(s)."
            )
        )
