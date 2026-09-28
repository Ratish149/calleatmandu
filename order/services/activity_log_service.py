import logging
from typing import Any, Dict, Optional, Set

from common.middleware import get_current_ip, get_current_user
from order.models import ActivityLog

logger = logging.getLogger(__name__)

# Fields that should never be tracked in diffs or serialized
SENSITIVE_OR_IGNORED_FIELDS: Set[str] = {
    "password",
    "secret_key",
    "api_password",
    "updated_at",
    "created_at",
    "_pre_save_snapshot",
    "_skip_activity_log",
    "_skip_signal_create",
    "_status_change_comment",
    "_status_changed_by",
    "_order_item_changes",
}


class ActivityLogService:
    """
    Dedicated service handling creation and formatting of system activity logs.
    """

    @classmethod
    def _serialize_value(cls, val: Any) -> Any:
        """Helper to serialize complex values into JSON-friendly primitive values."""
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return round(val, 2)
        if isinstance(val, str):
            return val
        try:
            from decimal import Decimal

            if isinstance(val, Decimal):
                return round(float(val), 2)
        except Exception:
            pass
        return str(val)

    @classmethod
    def get_field_changes(
        cls,
        old_snapshot: Optional[Dict[str, Any]],
        new_instance: Any,
        exclude_fields: Optional[Set[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compares pre-save snapshot with current instance values to compute dirty fields.
        Returns: { 'field_name': { 'old': <value>, 'new': <value> } }
        """
        if not old_snapshot or not new_instance:
            return {}

        excludes = SENSITIVE_OR_IGNORED_FIELDS.union(exclude_fields or set())
        changes: Dict[str, Dict[str, Any]] = {}

        for field in new_instance._meta.fields:
            if field.name in excludes:
                continue

            field_attname = field.attname
            old_val = old_snapshot.get(field.name)
            if old_val is None and field_attname in old_snapshot:
                old_val = old_snapshot.get(field_attname)

            try:
                new_val = getattr(new_instance, field_attname)
            except Exception:
                try:
                    new_val = getattr(new_instance, field.name)
                except Exception:
                    continue

            old_serialized = cls._serialize_value(old_val)
            new_serialized = cls._serialize_value(new_val)

            if old_serialized != new_serialized:
                changes[field.name] = {
                    "old": old_serialized,
                    "new": new_serialized,
                }

        return changes

    @classmethod
    def format_changes_summary(cls, changes: Dict[str, Any]) -> str:
        """
        Formats a dictionary of changes into a human-readable summary string.
        E.g. "price changed from '250.0' to '300.0', stock changed from '100' to '85'"
        """
        if not changes:
            return ""
        parts = []
        for field, diff in changes.items():
            if not isinstance(diff, dict) or "old" not in diff or "new" not in diff:
                continue
            parts.append(
                f"{field} changed from '{diff.get('old')}' to '{diff.get('new')}'"
            )
        return ", ".join(parts)

    @classmethod
    def log_activity(
        cls,
        action_type: str,
        entity_type: str,
        entity_name: str,
        description: str,
        record_id: Optional[str] = None,
        record_repr: Optional[str] = None,
        order: Optional[Any] = None,
        changes: Optional[Dict[str, Any]] = None,
        user: Optional[Any] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[ActivityLog]:
        """
        Records an ActivityLog entry in the database.
        Automatically resolves the active user and client IP if not provided.
        """
        try:
            actor = user or get_current_user()
            ip = ip_address or get_current_ip()

            # Ensure actor is an authenticated user model instance, otherwise treat as System
            if actor and not getattr(actor, "is_authenticated", False):
                actor = None

            return ActivityLog.objects.create(
                user=actor,
                action_type=action_type,
                entity_type=entity_type,
                entity_name=entity_name,
                record_id=str(record_id) if record_id is not None else None,
                record_repr=str(record_repr)[:255] if record_repr is not None else None,
                order=order,
                description=description,
                changes=changes or {},
                ip_address=ip,
            )
        except Exception as exc:
            logger.error(
                "Error logging activity for %s (%s): %s",
                entity_name,
                record_id,
                exc,
                exc_info=True,
            )
            return None
