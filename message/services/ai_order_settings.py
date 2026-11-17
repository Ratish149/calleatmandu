"""Resolves the effective AI chat and order capabilities for a branch.

Environment variables in ``settings`` act as the defaults; a nullable
``BranchAISettings`` row (managed from the admin UI) overrides individual
values per branch. Branches without a row keep the previous env-driven
behaviour.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Union

from django.conf import settings

logger = logging.getLogger(__name__)


def resolve_conversation_branch_id(conversation) -> Optional[Union[int, str]]:
    """Best-effort branch id for a conversation (direct FK or account's branch)."""
    branch_id = getattr(conversation, "branch_id", None)
    if branch_id is not None:
        return branch_id
    business_account = getattr(conversation, "business_account", None)
    return getattr(business_account, "branch_id", None)


@dataclass(frozen=True)
class OrderFeatureFlags:
    chat_enabled: bool
    reply_delay_seconds: int
    creation_enabled: bool
    cancellation_enabled: bool
    cancellation_window_minutes: int
    dedup_window_minutes: int


def _env_defaults() -> OrderFeatureFlags:
    return OrderFeatureFlags(
        chat_enabled=getattr(settings, "AI_REPLY_ENABLED", True),
        reply_delay_seconds=int(getattr(settings, "AI_REPLY_DELAY_SECONDS", 120)),
        creation_enabled=getattr(settings, "AI_ORDER_CREATION_ENABLED", False),
        cancellation_enabled=getattr(settings, "AI_ORDER_CANCELLATION_ENABLED", False),
        cancellation_window_minutes=int(
            getattr(settings, "AI_ORDER_CANCELLATION_WINDOW_MINUTES", 10)
        ),
        dedup_window_minutes=int(
            getattr(settings, "AI_ORDER_DEDUP_WINDOW_MINUTES", 10)
        ),
    )


def get_order_feature_flags(
    branch_id: Optional[Union[int, str]] = None,
) -> OrderFeatureFlags:
    """Return the effective AI chat and order flags for ``branch_id``.

    Falls back to the environment defaults when no branch id is supplied or no
    ``BranchAISettings`` row exists. Any ``None`` field on an existing row
    inherits the corresponding env default. ``AI_REPLY_ENABLED`` remains a
    global kill switch: a branch cannot force AI chat on when it is false.
    """
    defaults = _env_defaults()
    if branch_id is None:
        return defaults

    try:
        from message.models import BranchAISettings

        branch_settings = BranchAISettings.objects.filter(branch_id=branch_id).first()
    except Exception:  # pragma: no cover - defensive; never block a reply
        logger.exception("Failed to load BranchAISettings for branch %s", branch_id)
        return defaults

    if branch_settings is None:
        return defaults

    def pick(value, fallback):
        return fallback if value is None else value

    return OrderFeatureFlags(
        chat_enabled=defaults.chat_enabled
        and pick(branch_settings.ai_chat_enabled, True),
        reply_delay_seconds=pick(
            branch_settings.ai_reply_delay_seconds, defaults.reply_delay_seconds
        ),
        creation_enabled=pick(
            branch_settings.ai_order_creation_enabled, defaults.creation_enabled
        ),
        cancellation_enabled=pick(
            branch_settings.ai_order_cancellation_enabled, defaults.cancellation_enabled
        ),
        cancellation_window_minutes=pick(
            branch_settings.ai_order_cancellation_window_minutes,
            defaults.cancellation_window_minutes,
        ),
        dedup_window_minutes=pick(
            branch_settings.ai_order_dedup_window_minutes, defaults.dedup_window_minutes
        ),
    )
