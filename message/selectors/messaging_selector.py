from typing import Dict, Optional, Union

from django.db.models import Count, Q, QuerySet

from message.models import BusinessAccount, Conversation, Message


def get_conversations_for_branch(
    branch_id: Optional[Union[int, str]] = None, person_id: Optional[str] = None
) -> QuerySet[Conversation]:
    """Retrieve conversations filtered by branch, optimized with select_related.

    Optionally filters by person_id (applicant_id or contact_id).
    """
    queryset = Conversation.objects.select_related("business_account", "branch")

    if branch_id is not None:
        queryset = queryset.filter(
            Q(branch_id=branch_id) | Q(business_account__branch_id=branch_id)
        )

    if person_id:
        queryset = queryset.filter(Q(applicant_id=person_id) | Q(contact_id=person_id))

    return queryset.order_by("-updated_at")


def get_conversation_messages(conversation_id: str) -> QuerySet[Message]:
    """Retrieve all messages for a specific conversation, prefetching attachments and sent_by."""
    return (
        Message.objects
        .filter(conversation_id=conversation_id)
        .select_related("sent_by")
        .prefetch_related("attachments")
        .order_by("created_at")
    )


def get_unread_counts_for_branch(
    branch_id: Optional[Union[int, str]] = None,
) -> Dict[str, int]:
    """Get count of unread inbound messages grouped by conversation_id for a branch."""
    conv_query = Conversation.objects.all()
    if branch_id is not None:
        conv_query = conv_query.filter(
            Q(branch_id=branch_id) | Q(business_account__branch_id=branch_id)
        )

    branch_conversations = conv_query.values_list("id", flat=True)

    if not branch_conversations:
        return {}

    rows = (
        Message.objects
        .filter(
            conversation_id__in=branch_conversations,
            direction="INBOUND",
            is_read=False,
        )
        .values("conversation_id")
        .annotate(unread_count=Count("id"))
    )

    return {row["conversation_id"]: row["unread_count"] for row in rows}


def get_linked_accounts_for_branch(
    branch_id: Optional[Union[int, str]] = None,
) -> QuerySet[BusinessAccount]:
    """Retrieve all linked business accounts for a branch."""
    queryset = BusinessAccount.objects.select_related("branch")
    if branch_id is not None:
        queryset = queryset.filter(branch_id=branch_id)
    return queryset.order_by("-created_at")
