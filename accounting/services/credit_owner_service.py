from typing import Any, Dict, Optional

from rest_framework.exceptions import ValidationError

from accounting.models import CreditOwner


class CreditOwnerService:
    """
    Service layer for CreditOwner CRUD and business logic.
    Branch is auto-resolved from the logged-in user when not provided.
    """

    @classmethod
    def create_credit_owner(
        cls,
        data: Dict[str, Any],
        created_by: Optional[Any] = None,
    ) -> CreditOwner:
        """
        Creates a new CreditOwner.
        Validates name and auto-assigns branch from the logged-in user.
        """
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "Credit owner name is required."})

        branch = data.get("branch")
        if not branch and created_by and hasattr(created_by, "branch") and created_by.branch:
            branch = created_by.branch

        credit_owner = CreditOwner.objects.create(
            name=name,
            phone_number=data.get("phone_number"),
            address=data.get("address"),
            branch=branch,
            notes=data.get("notes"),
        )
        return credit_owner

    @classmethod
    def update_credit_owner(
        cls,
        instance: CreditOwner,
        data: Dict[str, Any],
        updated_by: Optional[Any] = None,
    ) -> CreditOwner:
        """Updates an existing CreditOwner."""
        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                raise ValidationError({"name": "Credit owner name cannot be empty."})
            instance.name = name

        updatable_fields = ["phone_number", "address", "notes"]
        for field in updatable_fields:
            if field in data:
                setattr(instance, field, data[field])

        if "branch" in data and data["branch"] is not None:
            instance.branch = data["branch"]

        instance.save()
        return instance

    @classmethod
    def delete_credit_owner(cls, instance: CreditOwner) -> None:
        """
        Deletes a CreditOwner only if there are no unsettled credits.
        If there is outstanding balance, deletion is blocked.
        """
        remaining_due = instance.remaining_due
        if remaining_due > 0:
            raise ValidationError({
                "non_field_errors": (
                    f"Cannot delete credit owner '{instance.name}' because they have "
                    f"an outstanding balance of Rs. {remaining_due}."
                )
            })
        instance.delete()
