from typing import Any, Dict, Optional

from rest_framework.exceptions import ValidationError

from accounting.models import CashExpenditure
from order.models import ActivityLog
from order.services.activity_log_service import ActivityLogService


class CashExpenditureService:
    """
    Service layer handling business logic and workflows for Cash & Expenditure operations.
    Calculates available balance: cash_amount + online_amount - delivery_charge.
    """

    @classmethod
    def create_entry(
        cls,
        data: Dict[str, Any],
        created_by: Optional[Any] = None,
    ) -> CashExpenditure:
        """
        Creates a new Cash & Expenditure record.
        - cash_amount: Cash received (>= 0).
        - online_amount: Online amount received (>= 0).
        - delivery_charge: Delivery charge spent (>= 0).
        Branch is automatically resolved from the logged-in user's assigned branch.
        An ActivityLog entry is created after successful save.
        """
        cash_amount = float(data.get("cash_amount", 0.0) or 0.0)
        online_amount = float(data.get("online_amount", 0.0) or 0.0)
        delivery_charge = float(data.get("delivery_charge", 0.0) or 0.0)

        if cash_amount < 0:
            raise ValidationError({"cash_amount": "Cash amount cannot be negative."})
        if online_amount < 0:
            raise ValidationError({
                "online_amount": "Online amount cannot be negative."
            })
        if delivery_charge < 0:
            raise ValidationError({
                "delivery_charge": "Delivery charge cannot be negative."
            })

        # Always resolve branch from the logged-in user
        branch = None
        if created_by and hasattr(created_by, "branch") and created_by.branch:
            branch = created_by.branch

        entry = CashExpenditure.objects.create(
            cash_amount=cash_amount,
            online_amount=online_amount,
            delivery_charge=delivery_charge,
            date=data.get("date"),
            notes=data.get("notes"),
            receipt_image=data.get("receipt_image"),
            branch=branch,
            created_by=created_by,
        )

        description = (
            f"Cash entry recorded for {entry.date}: Cash: Rs. {cash_amount}, "
            f"Online: Rs. {online_amount}, Delivery Charge: Rs. {delivery_charge}. "
            f"Available Balance: Rs. {entry.available_balance}."
        )

        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.CASH_EXPENDITURE,
            entity_name="CashExpenditure",
            record_id=entry.pk,
            record_repr=str(entry),
            description=description,
            changes={
                "cash_amount": cash_amount,
                "online_amount": online_amount,
                "delivery_charge": delivery_charge,
                "available_balance": entry.available_balance,
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
        pre_snapshot = {
            "cash_amount": instance.cash_amount,
            "online_amount": instance.online_amount,
            "delivery_charge": instance.delivery_charge,
            "available_balance": instance.available_balance,
            "date": str(instance.date),
            "notes": instance.notes,
        }

        cash_amount = float(data.get("cash_amount", instance.cash_amount) or 0.0)
        online_amount = float(data.get("online_amount", instance.online_amount) or 0.0)
        delivery_charge = float(
            data.get("delivery_charge", instance.delivery_charge) or 0.0
        )

        if cash_amount < 0:
            raise ValidationError({"cash_amount": "Cash amount cannot be negative."})
        if online_amount < 0:
            raise ValidationError({
                "online_amount": "Online amount cannot be negative."
            })
        if delivery_charge < 0:
            raise ValidationError({
                "delivery_charge": "Delivery charge cannot be negative."
            })

        # Apply updates
        updatable_fields = [
            "date",
            "notes",
            "receipt_image",
        ]
        for field in updatable_fields:
            if field in data:
                setattr(instance, field, data[field])

        instance.cash_amount = cash_amount
        instance.online_amount = online_amount
        instance.delivery_charge = delivery_charge
        instance.save()

        post_snapshot = {
            "cash_amount": instance.cash_amount,
            "online_amount": instance.online_amount,
            "delivery_charge": instance.delivery_charge,
            "available_balance": instance.available_balance,
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
                f"Cash entry '{instance}' updated. " + ", ".join(summary_parts) + "."
            )
        else:
            description = (
                f"Cash entry '{instance}' updated (no field changes detected)."
            )

        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.UPDATE,
            entity_type=ActivityLog.EntityType.CASH_EXPENDITURE,
            entity_name="CashExpenditure",
            record_id=instance.pk,
            record_repr=str(instance),
            description=description,
            changes=field_changes,
            user=updated_by,
        )

        return instance
