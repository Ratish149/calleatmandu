from typing import Any, Dict, Optional

from rest_framework.exceptions import ValidationError

from accounting.models import CashExpenditure
from order.models import ActivityLog
from order.services.activity_log_service import ActivityLogService


class CashExpenditureService:
    """
    Service layer handling business logic and workflows for Cash & Expenditure operations.
    """

    @classmethod
    def create_entry(
        cls,
        data: Dict[str, Any],
        created_by: Optional[Any] = None,
    ) -> CashExpenditure:
        """
        Creates a new Cash & Expenditure record.
        Branch is automatically resolved from the logged-in user's assigned branch.
        An ActivityLog entry is created after successful save.
        """
        cash_amount = float(data.get("cash_amount", 0.0) or 0.0)
        expenditure_amount = float(data.get("expenditure_amount", 0.0) or 0.0)

        if cash_amount < 0:
            raise ValidationError({"cash_amount": "Cash amount cannot be negative."})
        if expenditure_amount < 0:
            raise ValidationError(
                {"expenditure_amount": "Expenditure amount cannot be negative."}
            )

        if cash_amount == 0 and expenditure_amount == 0:
            raise ValidationError(
                {
                    "non_field_errors": [
                        "Please provide either a cash_amount (Cash In) or an expenditure_amount (Expense)."
                    ]
                }
            )

        # Always resolve branch from the logged-in user
        branch = None
        if created_by and hasattr(created_by, "branch") and created_by.branch:
            branch = created_by.branch

        entry_type = data.get("entry_type", CashExpenditure.EntryType.EXPENDITURE)

        entry = CashExpenditure.objects.create(
            title=data.get("title"),
            entry_type=entry_type,
            cash_amount=cash_amount,
            expenditure_amount=expenditure_amount,
            date=data.get("date"),
            payment_method=data.get(
                "payment_method", CashExpenditure.PaymentMethod.CASH
            ),
            notes=data.get("notes"),
            receipt_image=data.get("receipt_image"),
            branch=branch,
            created_by=created_by,
        )

        # Build human-readable description
        parts = []
        if cash_amount > 0:
            parts.append(f"Cash In: Rs. {cash_amount}")
        if expenditure_amount > 0:
            parts.append(f"Expenditure: Rs. {expenditure_amount}")
        description = (
            f"New {entry.get_entry_type_display()} entry '{entry.title}' recorded. "
            + ", ".join(parts)
            + f". Net: Rs. {entry.net_amount}."
        )

        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.CASH_EXPENDITURE,
            entity_name="CashExpenditure",
            record_id=entry.pk,
            record_repr=entry.title,
            description=description,
            changes={
                "title": entry.title,
                "entry_type": entry.entry_type,
                "cash_amount": cash_amount,
                "expenditure_amount": expenditure_amount,
                "payment_method": entry.payment_method,
                "date": str(entry.date),
                "branch": str(branch) if branch else None,
            },
            user=created_by,
        )

        return entry

    @classmethod
    def update_entry(
        cls,
        instance: CashExpenditure,
        data: Dict[str, Any],
        updated_by: Optional[Any] = None,
    ) -> CashExpenditure:
        """
        Updates an existing Cash & Expenditure record.
        Captures a pre-save snapshot, applies updates, then logs the diff as an ActivityLog.
        """
        # Snapshot before update for diff
        pre_snapshot = {
            "title": instance.title,
            "entry_type": instance.entry_type,
            "cash_amount": instance.cash_amount,
            "expenditure_amount": instance.expenditure_amount,
            "payment_method": instance.payment_method,
            "date": str(instance.date),
            "notes": instance.notes,
        }

        cash_amount = float(data.get("cash_amount", instance.cash_amount) or 0.0)
        expenditure_amount = float(
            data.get("expenditure_amount", instance.expenditure_amount) or 0.0
        )

        if cash_amount < 0:
            raise ValidationError({"cash_amount": "Cash amount cannot be negative."})
        if expenditure_amount < 0:
            raise ValidationError(
                {"expenditure_amount": "Expenditure amount cannot be negative."}
            )

        if cash_amount == 0 and expenditure_amount == 0:
            raise ValidationError(
                {
                    "non_field_errors": [
                        "Please provide either a cash_amount (Cash In) or an expenditure_amount (Expense)."
                    ]
                }
            )

        # Apply updates
        updatable_fields = [
            "title",
            "entry_type",
            "cash_amount",
            "expenditure_amount",
            "date",
            "payment_method",
            "notes",
            "receipt_image",
        ]
        for field in updatable_fields:
            if field in data:
                setattr(instance, field, data[field])

        instance.cash_amount = cash_amount
        instance.expenditure_amount = expenditure_amount
        instance.save()

        # Compute changes for activity log
        post_snapshot = {
            "title": instance.title,
            "entry_type": instance.entry_type,
            "cash_amount": instance.cash_amount,
            "expenditure_amount": instance.expenditure_amount,
            "payment_method": instance.payment_method,
            "date": str(instance.date),
            "notes": instance.notes,
        }

        field_changes = {
            field: {"old": pre_snapshot[field], "new": post_snapshot[field]}
            for field in pre_snapshot
            if str(pre_snapshot[field]) != str(post_snapshot[field])
        }

        if field_changes:
            summary_parts = [
                f"{field} changed from '{diff['old']}' to '{diff['new']}'"
                for field, diff in field_changes.items()
            ]
            description = (
                f"Cash & Expenditure entry '{instance.title}' updated. "
                + ", ".join(summary_parts)
                + "."
            )
        else:
            description = f"Cash & Expenditure entry '{instance.title}' updated (no field changes detected)."

        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.UPDATE,
            entity_type=ActivityLog.EntityType.CASH_EXPENDITURE,
            entity_name="CashExpenditure",
            record_id=instance.pk,
            record_repr=instance.title,
            description=description,
            changes=field_changes,
            user=updated_by,
        )

        return instance
