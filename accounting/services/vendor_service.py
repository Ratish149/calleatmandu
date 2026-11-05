from typing import Any, Dict, Optional

from rest_framework.exceptions import ValidationError

from accounting.models import Vendor, VendorTransaction


class VendorService:
    """
    Service layer for Vendor CRUD business logic.
    Branch is auto-resolved from the logged-in user.
    """

    @classmethod
    def create_vendor(
        cls,
        data: Dict[str, Any],
        created_by: Optional[Any] = None,
    ) -> Vendor:
        """Creates a new Vendor, auto-assigning the branch from the logged-in user."""
        branch = None
        if created_by and hasattr(created_by, "branch") and created_by.branch:
            branch = created_by.branch

        vendor = Vendor.objects.create(
            name=data.get("name"),
            phone_number=data.get("phone_number"),
            address=data.get("address"),
            branch=branch,
        )
        return vendor

    @classmethod
    def update_vendor(
        cls,
        instance: Vendor,
        data: Dict[str, Any],
    ) -> Vendor:
        """Updates an existing Vendor."""
        updatable_fields = ["name", "phone_number", "address"]
        for field in updatable_fields:
            if field in data:
                setattr(instance, field, data[field])
        instance.save()
        return instance


class VendorTransactionService:
    """
    Service layer for VendorTransaction CRUD business logic.
    Branch is auto-resolved from the logged-in user.
    """

    @classmethod
    def create_transaction(
        cls,
        data: Dict[str, Any],
        created_by: Optional[Any] = None,
    ) -> VendorTransaction:
        """
        Creates a new VendorTransaction.
        Validates that amount is positive and transaction_type is provided.
        Branch is auto-resolved from the logged-in user.
        """
        amount = float(data.get("amount", 0.0) or 0.0)
        if amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})

        transaction_type = data.get("transaction_type")
        if not transaction_type:
            raise ValidationError({
                "transaction_type": "transaction_type is required (BILL or PAYMENT)."
            })

        branch = None
        if created_by and hasattr(created_by, "branch") and created_by.branch:
            branch = created_by.branch

        transaction = VendorTransaction.objects.create(
            vendor_id=data.get("vendor") or data.get("vendor_id"),
            transaction_type=transaction_type,
            amount=amount,
            date=data.get("date"),
            payment_method=data.get(
                "payment_method", VendorTransaction.PaymentMethod.CASH
            ),
            notes=data.get("notes"),
            receipt_image=data.get("receipt_image"),
            branch=branch,
            created_by=created_by,
        )
        return transaction

    @classmethod
    def update_transaction(
        cls,
        instance: VendorTransaction,
        data: Dict[str, Any],
    ) -> VendorTransaction:
        """Updates an existing VendorTransaction."""
        if "amount" in data:
            amount = float(data["amount"] or 0.0)
            if amount <= 0:
                raise ValidationError({"amount": "Amount must be greater than zero."})
            instance.amount = amount

        updatable_fields = [
            "transaction_type",
            "date",
            "payment_method",
            "notes",
            "receipt_image",
        ]
        for field in updatable_fields:
            if field in data:
                setattr(instance, field, data[field])

        instance.save()
        return instance
