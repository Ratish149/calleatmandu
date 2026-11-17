from typing import Any, Dict, Optional

from rest_framework.exceptions import ValidationError

from accounting.models import CashExpenditure, CreditEntry, CreditSettlement
from order.models import ActivityLog
from order.services.activity_log_service import ActivityLogService


class CashExpenditureService:
    """
    Service layer handling business logic and workflows for Cash & Expenditure operations.
    Calculates available balance: cash_amount + online_amount - delivery_charge.
    Credit amount is tracked separately and does NOT count towards available balance.
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
        - credit_amount: Amount given on credit (>= 0, not yet collected).
        - delivery_charge: Delivery charge spent (>= 0).
        Branch is automatically resolved from the logged-in user's assigned branch.
        An ActivityLog entry is created after successful save.
        If credit_amount > 0, a CreditEntry is auto-created and linked to the entry.
        """
        cash_amount = float(data.get("cash_amount", 0.0) or 0.0)
        online_amount = float(data.get("online_amount", 0.0) or 0.0)
        credit_amount = float(data.get("credit_amount", 0.0) or 0.0)
        delivery_charge = float(data.get("delivery_charge", 0.0) or 0.0)

        if cash_amount < 0:
            raise ValidationError({"cash_amount": "Cash amount cannot be negative."})
        if online_amount < 0:
            raise ValidationError({
                "online_amount": "Online amount cannot be negative."
            })
        if credit_amount < 0:
            raise ValidationError({
                "credit_amount": "Credit amount cannot be negative."
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
            credit_amount=credit_amount,
            delivery_charge=delivery_charge,
            date=data.get("date"),
            notes=data.get("notes"),
            receipt_image=data.get("receipt_image"),
            branch=branch,
            created_by=created_by,
        )

        # Auto-create CreditEntry when credit_amount > 0
        if credit_amount > 0:
            CreditEntry.objects.create(
                cash_entry=entry,
                credit_amount=credit_amount,
                notes=data.get("credit_notes"),
                branch=branch,
                created_by=created_by,
            )

        description = (
            f"Cash entry recorded for {entry.date}: Cash: Rs. {cash_amount}, "
            f"Online: Rs. {online_amount}, Credit: Rs. {credit_amount}, "
            f"Delivery Charge: Rs. {delivery_charge}. "
            f"Available Balance: Rs. {entry.available_balance}. "
            f"Total Sales: Rs. {entry.total_sales}."
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
                "credit_amount": credit_amount,
                "delivery_charge": delivery_charge,
                "available_balance": entry.available_balance,
                "total_sales": entry.total_sales,
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
        If credit_amount changes, the linked CreditEntry is updated accordingly
        (only if the credit is still PENDING and has no settlement yet).
        """
        pre_snapshot = {
            "cash_amount": instance.cash_amount,
            "online_amount": instance.online_amount,
            "credit_amount": instance.credit_amount,
            "delivery_charge": instance.delivery_charge,
            "available_balance": instance.available_balance,
            "date": str(instance.date),
            "notes": instance.notes,
        }

        cash_amount = float(data.get("cash_amount", instance.cash_amount) or 0.0)
        online_amount = float(data.get("online_amount", instance.online_amount) or 0.0)
        credit_amount = float(data.get("credit_amount", instance.credit_amount) or 0.0)
        delivery_charge = float(
            data.get("delivery_charge", instance.delivery_charge) or 0.0
        )

        if cash_amount < 0:
            raise ValidationError({"cash_amount": "Cash amount cannot be negative."})
        if online_amount < 0:
            raise ValidationError({
                "online_amount": "Online amount cannot be negative."
            })
        if credit_amount < 0:
            raise ValidationError({
                "credit_amount": "Credit amount cannot be negative."
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
        instance.credit_amount = credit_amount
        instance.delivery_charge = delivery_charge
        instance.save()

        # Sync credit_amount change to linked CreditEntry if still editable
        if "credit_amount" in data:
            try:
                credit_entry = instance.credit_entry
                if credit_entry.status == CreditEntry.Status.PENDING and not hasattr(
                    credit_entry, "settlement"
                ):
                    if credit_amount > 0:
                        credit_entry.credit_amount = credit_amount
                        credit_entry.save(update_fields=["credit_amount", "updated_at"])
                    else:
                        # credit removed — delete the pending entry
                        credit_entry.delete()
            except CreditEntry.DoesNotExist:
                # No existing CreditEntry — create one if credit_amount > 0
                if credit_amount > 0:
                    branch = instance.branch
                    CreditEntry.objects.create(
                        cash_entry=instance,
                        credit_amount=credit_amount,
                        branch=branch,
                        created_by=updated_by,
                    )

        post_snapshot = {
            "cash_amount": instance.cash_amount,
            "online_amount": instance.online_amount,
            "credit_amount": instance.credit_amount,
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


class CreditEntryService:
    """
    Service layer for CreditEntry and CreditSettlement operations.
    """

    @classmethod
    def settle_credit(
        cls,
        credit_entry: CreditEntry,
        data: Dict[str, Any],
        created_by: Optional[Any] = None,
    ) -> CreditSettlement:
        """
        Records a settlement for a CreditEntry.
        - cash_settled: Amount paid via cash (>= 0).
        - online_settled: Amount paid via online (>= 0).
        - Exactly one of cash_settled or online_settled must be > 0 (not both).
        - Total settled amount must equal the full credit_amount.
        - A CreditEntry can only be settled once (OneToOne).
        """
        # Guard: already settled
        try:
            existing = credit_entry.settlement
            raise ValidationError({
                "credit_entry": "This credit entry has already been settled."
            })
        except CreditSettlement.DoesNotExist:
            pass

        cash_settled = float(data.get("cash_settled", 0.0) or 0.0)
        online_settled = float(data.get("online_settled", 0.0) or 0.0)

        if cash_settled < 0:
            raise ValidationError({"cash_settled": "Cash settled cannot be negative."})
        if online_settled < 0:
            raise ValidationError({
                "online_settled": "Online settled cannot be negative."
            })
        if cash_settled == 0 and online_settled == 0:
            raise ValidationError(
                "Either cash_settled or online_settled must be greater than zero."
            )
        if cash_settled > 0 and online_settled > 0:
            raise ValidationError(
                "Settlement must be via either Cash or Online — not both."
            )

        total = round(cash_settled + online_settled, 2)
        credit_amount = round(float(credit_entry.credit_amount or 0.0), 2)
        if total > credit_amount:
            raise ValidationError({
                "non_field_errors": (
                    f"Settled amount (Rs. {total}) cannot exceed "
                    f"the credit amount (Rs. {credit_amount})."
                )
            })

        branch = None
        if created_by and hasattr(created_by, "branch") and created_by.branch:
            branch = created_by.branch

        settlement = CreditSettlement.objects.create(
            credit_entry=credit_entry,
            cash_settled=cash_settled,
            online_settled=online_settled,
            settled_date=data.get("settled_date"),
            notes=data.get("notes"),
            branch=branch,
            created_by=created_by,
        )

        # Credit is always fully settled on settlement (single payment)
        credit_entry.status = CreditEntry.Status.SETTLED
        credit_entry.save(update_fields=["status", "updated_at"])

        return settlement
