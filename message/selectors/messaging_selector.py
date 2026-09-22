from typing import Dict, Optional

from django.db.models import Count, Q, QuerySet

from message.models import BusinessAccount, Conversation, Message


def get_conversations_for_org(
    org_id: str, person_id: Optional[str] = None
) -> QuerySet[Conversation]:
    """Retrieve conversations for an organization, optimized with select_related.

    Optionally filters by person_id (applicant_id or contact_id).
    """
    queryset = Conversation.objects.filter(
        business_account__organization_id=org_id
    ).select_related("business_account")

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


def get_unread_counts_for_org(org_id: str) -> Dict[str, int]:
    """Get count of unread inbound messages grouped by conversation_id for an organization."""
    org_conversations = Conversation.objects.filter(
        business_account__organization_id=org_id
    ).values_list("id", flat=True)

    if not org_conversations:
        return {}

    rows = (
        Message.objects
        .filter(
            conversation_id__in=org_conversations,
            direction="INBOUND",
            is_read=False,
        )
        .values("conversation_id")
        .annotate(unread_count=Count("id"))
    )

    return {row["conversation_id"]: row["unread_count"] for row in rows}


def get_linked_accounts_for_org(organization_id: str) -> QuerySet[BusinessAccount]:
    """Retrieve all linked business accounts for an organization."""
    return BusinessAccount.objects.filter(organization_id=organization_id).order_by(
        "-created_at"
    )
