from django.utils import timezone
from rest_framework import serializers

from accounting.models import (
    CashExpenditure,
    CreditEntry,
    CreditOwner,
    CreditSettlement,
    Vendor,
    VendorTransaction,
)
from accounting.services.accounting_service import (
    CashExpenditureService,
)
from accounting.services.credit_owner_service import CreditOwnerService
from accounting.services.vendor_service import VendorService, VendorTransactionService


class CashExpenditureSerializer(serializers.ModelSerializer):
    """
    Serializer for recording, updating, and viewing Cash & Expenditure records.
    Fields:
      - cash_amount: physical cash received.
      - online_amount: online/digital payment received.
      - delivery_charge: delivery expense/charge.
      - date: date of entry.
      - available_balance: cash_amount + online_amount - delivery_charge.
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    available_balance = serializers.FloatField(read_only=True)
    net_amount = serializers.FloatField(read_only=True)
    total_sales = serializers.FloatField(read_only=True)
    credit_owner = serializers.PrimaryKeyRelatedField(
        queryset=CreditOwner.objects.all(),
        required=False,
        allow_null=True,
        help_text="Credit owner who owes this amount (required if credit_amount > 0).",
    )
    credit_owner_name = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text="Name of the credit owner linked to this credit transaction.",
    )
    credit_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Remarks/notes for the linked credit entry.",
    )

    class Meta:
        model = CashExpenditure
        fields = [
            "id",
            "cash_amount",
            "online_amount",
            "credit_amount",
            "credit_owner",
            "credit_owner_name",
            "credit_notes",
            "delivery_charge",
            "available_balance",
            "total_sales",
            "net_amount",
            "date",
            "notes",
            "receipt_image",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "credit_owner_name",
            "available_balance",
            "total_sales",
            "net_amount",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def to_internal_value(self, data):
        data_copy = data.copy() if hasattr(data, "copy") else dict(data)
        if "credit_note" in data_copy and "credit_notes" not in data_copy:
            data_copy["credit_notes"] = data_copy["credit_note"]
        return super().to_internal_value(data_copy)

    def validate(self, attrs):
        cash_amount = float(
            attrs.get("cash_amount", getattr(self.instance, "cash_amount", 0.0)) or 0.0
        )
        online_amount = float(
            attrs.get("online_amount", getattr(self.instance, "online_amount", 0.0))
            or 0.0
        )
        credit_amount = float(
            attrs.get("credit_amount", getattr(self.instance, "credit_amount", 0.0))
            or 0.0
        )
        delivery_charge = float(
            attrs.get(
                "delivery_charge",
                getattr(self.instance, "delivery_charge", 0.0),
            )
            or 0.0
        )

        if cash_amount < 0:
            raise serializers.ValidationError({
                "cash_amount": "Cash amount cannot be negative."
            })
        if online_amount < 0:
            raise serializers.ValidationError({
                "online_amount": "Online amount cannot be negative."
            })
        if credit_amount < 0:
            raise serializers.ValidationError({
                "credit_amount": "Credit amount cannot be negative."
            })
        if delivery_charge < 0:
            raise serializers.ValidationError({
                "delivery_charge": "Delivery charge cannot be negative."
            })

        if credit_amount > 0:
            existing_owner = getattr(
                getattr(self.instance, "credit_entry", None), "credit_owner_id", None
            )
            if not attrs.get("credit_owner") and not existing_owner:
                raise serializers.ValidationError({
                    "credit_owner": "Credit owner is required when credit_amount is greater than zero."
                })

        attrs["cash_amount"] = cash_amount
        attrs["online_amount"] = online_amount
        attrs["credit_amount"] = credit_amount
        attrs["delivery_charge"] = delivery_charge

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        return CashExpenditureService.create_entry(validated_data, created_by=user)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        return CashExpenditureService.update_entry(
            instance, validated_data, updated_by=user
        )


class CashBalanceSummarySerializer(serializers.Serializer):
    """
    Balance summary serializer.

    total_cash_amount             = full cash amount collected in entries.
    total_online_amount           = full online amount collected in entries.
    total_cash_available_amount   = full cash + credit settled via cash - vendor payments paid in cash.
    total_online_available_amount = full online + credit settled via online - vendor payments paid online.
    total_credit_amount           = total credit amount given across entries in this period.
    total_delivery_charge         = sum of delivery charges.
    total_vendor_paid_amount      = sum of all payments made to vendors.
    total_vendor_cash_paid        = sum of vendor payments paid in cash.
    total_vendor_online_paid      = sum of vendor payments paid online.
    available_balance             = total_cash_available_amount + total_online_available_amount - total_delivery_charge.
    """

    total_cash_amount = serializers.FloatField(
        help_text="Full/gross physical cash amount collected in Cash & Expenditure entries."
    )
    total_online_amount = serializers.FloatField(
        help_text="Full/gross online amount collected in Cash & Expenditure entries."
    )
    total_cash_available_amount = serializers.FloatField(
        help_text="Available cash amount: full cash + credit settled via cash - vendor payments paid in cash."
    )
    total_online_available_amount = serializers.FloatField(
        help_text="Available online amount: full online + credit settled via online - vendor payments paid online."
    )
    total_credit_amount = serializers.FloatField(
        default=0.0,
        help_text="Total credit amount given across entries in this period.",
    )
    total_delivery_charge = serializers.FloatField(
        help_text="Sum of all delivery charges."
    )
    total_vendor_paid_amount = serializers.FloatField(
        default=0.0,
        help_text="Sum of all payments made to vendors.",
    )
    total_vendor_cash_paid = serializers.FloatField(
        default=0.0,
        required=False,
        help_text="Sum of payments made to vendors in cash.",
    )
    total_vendor_online_paid = serializers.FloatField(
        default=0.0,
        required=False,
        help_text="Sum of payments made to vendors via online/bank transfer.",
    )
    total_available_balance = serializers.FloatField(
        help_text="Net available balance (total_cash_available_amount + total_online_available_amount - total_delivery_charge)."
    )
    available_balance = serializers.FloatField(
        help_text="Alias for total_available_balance."
    )
    total_entries = serializers.IntegerField(
        help_text="Total number of cash entry records."
    )
    start_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Start date filter applied (YYYY-MM-DD).",
    )
    end_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="End date filter applied (YYYY-MM-DD).",
    )


class CreditStatsSerializer(serializers.Serializer):
    """
    Serializer for the dedicated credit statistics endpoint.
    Shows total credit given, how much has been settled, and remaining outstanding.
    """

    total_credit_amount = serializers.FloatField(
        help_text="Total credit amount given across all entries in the period."
    )
    total_credit_settled = serializers.FloatField(
        help_text="Total amount settled/collected from outstanding credits."
    )
    total_credit_remaining = serializers.FloatField(
        help_text="Outstanding credit not yet collected (total_credit_amount - total_credit_settled)."
    )
    settled_count = serializers.IntegerField(
        help_text="Number of fully settled credit entries."
    )
    pending_count = serializers.IntegerField(
        help_text="Number of credit entries still pending settlement."
    )
    total_entries = serializers.IntegerField(
        help_text="Total credit entries in the period."
    )
    start_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Start date filter applied (YYYY-MM-DD).",
    )
    end_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="End date filter applied (YYYY-MM-DD).",
    )


class VendorSerializer(serializers.ModelSerializer):
    """
    Serializer for Vendor CRUD.
    Branch is auto-assigned from the logged-in user on create.
    Includes computed financial summary fields (read-only).
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    total_billed = serializers.FloatField(
        source="total_amount_to_be_paid", read_only=True
    )
    total_paid = serializers.FloatField(source="total_amount_paid", read_only=True)
    remaining_due = serializers.FloatField(read_only=True)

    class Meta:
        model = Vendor
        fields = [
            "id",
            "name",
            "phone_number",
            "address",
            "branch",
            "branch_name",
            "total_billed",
            "total_paid",
            "remaining_due",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "branch",
            "branch_name",
            "total_billed",
            "total_paid",
            "remaining_due",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Vendor name cannot be blank.")
        return str(value).strip()

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        return VendorService.create_vendor(validated_data, created_by=user)

    def update(self, instance, validated_data):
        return VendorService.update_vendor(instance, validated_data)


class VendorTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for VendorTransaction CRUD.
    - transaction_type: BILL (amount owed to vendor) or PAYMENT (amount paid to vendor).
    - amount: single amount field — interpreted based on transaction_type.
    - Branch is auto-assigned from the logged-in user on create.
    """

    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    receipt_type_display = serializers.CharField(
        source="get_receipt_type_display", read_only=True
    )

    class Meta:
        model = VendorTransaction
        fields = [
            "id",
            "vendor",
            "vendor_name",
            "transaction_type",
            "transaction_type_display",
            "amount",
            "date",
            "payment_method",
            "payment_method_display",
            "notes",
            "receipt_image",
            "receipt_type",
            "receipt_type_display",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vendor_name",
            "transaction_type_display",
            "payment_method_display",
            "receipt_type_display",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value is None or float(value) <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_transaction_type(self, value):
        valid = [t.value for t in VendorTransaction.TransactionType]
        if value not in valid:
            raise serializers.ValidationError(
                f"transaction_type must be one of: {', '.join(valid)}."
            )
        return value

    def validate_receipt_type(self, value):
        if value in (None, ""):
            return value
        valid = [r.value for r in VendorTransaction.ReceiptType]
        if value not in valid:
            raise serializers.ValidationError(
                f"receipt_type must be one of: {', '.join(valid)}."
            )
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        # Pass vendor id from the validated FK object
        data = dict(validated_data)
        if "vendor" in data:
            data["vendor_id"] = data.pop("vendor").pk
        return VendorTransactionService.create_transaction(data, created_by=user)

    def update(self, instance, validated_data):
        return VendorTransactionService.update_transaction(instance, validated_data)


class VendorTransactionSummarySerializer(serializers.Serializer):
    """
    Serializer for aggregated VendorTransaction financial summary.
    """

    total_billed = serializers.FloatField(
        help_text="Sum of all BILL-type transaction amounts."
    )
    total_paid = serializers.FloatField(
        help_text="Sum of all PAYMENT-type transaction amounts."
    )
    remaining_due = serializers.FloatField(
        help_text="Remaining balance owed to vendor(s) (total_billed - total_paid)."
    )
    total_entries = serializers.IntegerField(help_text="Total number of transactions.")
    bill_count = serializers.IntegerField(help_text="Number of BILL transactions.")
    payment_count = serializers.IntegerField(
        help_text="Number of PAYMENT transactions."
    )
    start_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Start date filter applied (YYYY-MM-DD).",
    )
    end_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="End date filter applied (YYYY-MM-DD).",
    )


class VendorSummaryResponseSerializer(serializers.Serializer):
    """
    Serializer for the Vendor Summary endpoint.
    Returns aggregated financial summary:
    - Based on all vendors when requested without vendor filter.
    - Based on that specific vendor only when filtered with ?vendor=<id>.
    """

    total_billed = serializers.FloatField(
        help_text="Sum of all BILL-type transaction amounts."
    )
    total_paid = serializers.FloatField(
        help_text="Sum of all PAYMENT-type transaction amounts."
    )
    remaining_due = serializers.FloatField(
        help_text="Remaining balance owed to vendor(s) (total_billed - total_paid)."
    )
    total_entries = serializers.IntegerField(help_text="Total number of transactions.")
    bill_count = serializers.IntegerField(help_text="Number of BILL transactions.")
    payment_count = serializers.IntegerField(
        help_text="Number of PAYMENT transactions."
    )
    vendor_count = serializers.IntegerField(
        help_text="Count of distinct vendors included in this summary."
    )
    vendor_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="Vendor ID if filtered by a specific vendor.",
    )
    vendor_name = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Vendor name if filtered by a specific vendor.",
    )
    start_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Start date filter applied (YYYY-MM-DD).",
    )
    end_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="End date filter applied (YYYY-MM-DD).",
    )


class CreditSettlementSerializer(serializers.ModelSerializer):
    """
    Serializer for recording and viewing a CreditSettlement.
    - cash_settled: Amount paid via cash.
    - online_settled: Amount paid via online.
    - total_settled and payment_method are computed read-only fields.
    """

    total_settled = serializers.FloatField(read_only=True)
    payment_method = serializers.CharField(read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = CreditSettlement
        fields = [
            "id",
            "cash_settled",
            "online_settled",
            "total_settled",
            "payment_method",
            "settled_date",
            "notes",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "total_settled",
            "payment_method",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        cash_settled = float(attrs.get("cash_settled", 0.0) or 0.0)
        online_settled = float(attrs.get("online_settled", 0.0) or 0.0)

        if cash_settled < 0:
            raise serializers.ValidationError({
                "cash_settled": "Cash settled cannot be negative."
            })
        if online_settled < 0:
            raise serializers.ValidationError({
                "online_settled": "Online settled cannot be negative."
            })
        if cash_settled == 0 and online_settled == 0:
            raise serializers.ValidationError(
                "Either cash_settled or online_settled must be greater than zero."
            )
        if cash_settled > 0 and online_settled > 0:
            raise serializers.ValidationError(
                "Settlement must be via either Cash or Online — not both."
            )

        attrs["cash_settled"] = cash_settled
        attrs["online_settled"] = online_settled
        return attrs


class CreditOwnerSimpleSerializer(serializers.ModelSerializer):
    """Lightweight serializer for CreditOwner dropdowns and nested references."""

    class Meta:
        model = CreditOwner
        fields = ["id", "name", "phone_number"]


class CreditOwnerSerializer(serializers.ModelSerializer):
    """
    Serializer for CreditOwner CRUD and financial balance details.
    Branch is auto-assigned from the logged-in user on create if omitted.
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    total_credit_amount = serializers.FloatField(read_only=True)
    total_settled_amount = serializers.FloatField(read_only=True)
    remaining_due = serializers.FloatField(read_only=True)
    is_cleared = serializers.BooleanField(read_only=True)

    class Meta:
        model = CreditOwner
        fields = [
            "id",
            "name",
            "phone_number",
            "address",
            "branch",
            "branch_name",
            "notes",
            "total_credit_amount",
            "total_settled_amount",
            "remaining_due",
            "is_cleared",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "branch_name",
            "total_credit_amount",
            "total_settled_amount",
            "remaining_due",
            "is_cleared",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        return CreditOwnerService.create_credit_owner(validated_data, created_by=user)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        return CreditOwnerService.update_credit_owner(
            instance, validated_data, updated_by=user
        )


class CreditEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for CreditEntry — a credit amount linked to a CreditOwner.
    Optionally linked to a CashExpenditure entry.
    Includes nested settlement details (read-only) and computed balance fields.
    """

    cash_entry = serializers.PrimaryKeyRelatedField(
        queryset=CashExpenditure.objects.all(),
        required=False,
        allow_null=True,
        help_text="Optional linked cash flow entry.",
    )
    date = serializers.DateField(
        required=False,
        default=timezone.now,
        help_text="Date of this credit transaction.",
    )
    cash_entry_date = serializers.DateField(
        source="cash_entry.date", read_only=True, allow_null=True
    )
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    amount_settled = serializers.FloatField(read_only=True)
    amount_remaining = serializers.FloatField(read_only=True)
    is_fully_settled = serializers.BooleanField(read_only=True)
    settlement = CreditSettlementSerializer(read_only=True)
    credit_owner = serializers.PrimaryKeyRelatedField(
        queryset=CreditOwner.objects.all(),
        required=True,
        help_text="Credit owner who owes this amount.",
    )
    credit_owner_details = CreditOwnerSimpleSerializer(
        source="credit_owner", read_only=True
    )
    owner_name = serializers.CharField(read_only=True)
    credit_notes = serializers.CharField(
        source="notes",
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Remarks about this credit.",
    )

    class Meta:
        model = CreditEntry
        fields = [
            "id",
            "date",
            "cash_entry",
            "cash_entry_date",
            "credit_owner",
            "credit_owner_details",
            "owner_name",
            "credit_amount",
            "status",
            "status_display",
            "credit_notes",
            "amount_settled",
            "amount_remaining",
            "is_fully_settled",
            "settlement",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "cash_entry_date",
            "owner_name",
            "status",
            "status_display",
            "amount_settled",
            "amount_remaining",
            "is_fully_settled",
            "settlement",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        branch = getattr(user, "branch", None) if user else None

        cash_entry = validated_data.get("cash_entry")
        entry_date = validated_data.get("date")
        if not entry_date:
            entry_date = cash_entry.date if cash_entry else timezone.now().date()

        credit_entry = CreditEntry.objects.create(
            cash_entry=cash_entry,
            date=entry_date,
            credit_amount=validated_data["credit_amount"],
            credit_owner=validated_data["credit_owner"],
            notes=validated_data.get("notes"),
            branch=branch,
            created_by=user,
        )
        return credit_entry

    def update(self, instance, validated_data):
        if instance.status == CreditEntry.Status.SETTLED:
            raise serializers.ValidationError({
                "non_field_errors": "Settled credit entries cannot be edited."
            })
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class CreditSettleActionSerializer(serializers.Serializer):
    """
    Serializer for the settle action on a CreditEntry.
    Accepts cash_settled, online_settled, settled_date, and notes.
    """

    cash_settled = serializers.FloatField(default=0.0, min_value=0)
    online_settled = serializers.FloatField(default=0.0, min_value=0)
    settled_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        cash_settled = float(attrs.get("cash_settled", 0.0) or 0.0)
        online_settled = float(attrs.get("online_settled", 0.0) or 0.0)
        if cash_settled == 0 and online_settled == 0:
            raise serializers.ValidationError(
                "Either cash_settled or online_settled must be greater than zero."
            )
        if cash_settled > 0 and online_settled > 0:
            raise serializers.ValidationError(
                "Settlement must be via either Cash or Online — not both."
            )
        return attrs
