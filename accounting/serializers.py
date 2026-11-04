from rest_framework import serializers

from accounting.models import CashExpenditure
from accounting.services.accounting_service import CashExpenditureService


class CashExpenditureSerializer(serializers.ModelSerializer):
    """
    Serializer for recording, updating, and viewing Cash & Expenditure records.
    Branch is automatically assigned from the logged-in user — not required in payload.
    Supports EntryTypes:
      - CASH_IN: Physical cash additions (requires cash_amount > 0).
      - ONLINE_IN: Digital receipts / inflows (requires cash_amount > 0).
      - EXPENDITURE: Outflows / expenses (requires expenditure_amount > 0).
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    entry_type_display = serializers.CharField(
        source="get_entry_type_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    net_amount = serializers.FloatField(read_only=True)

    class Meta:
        model = CashExpenditure
        fields = [
            "id",
            "title",
            "entry_type",
            "entry_type_display",
            "cash_amount",
            "expenditure_amount",
            "net_amount",
            "date",
            "payment_method",
            "payment_method_display",
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
            "net_amount",
            "entry_type_display",
            "payment_method_display",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        entry_type = attrs.get(
            "entry_type",
            getattr(self.instance, "entry_type", CashExpenditure.EntryType.EXPENDITURE),
        )
        cash_amount = float(
            attrs.get("cash_amount", getattr(self.instance, "cash_amount", 0.0))
            or 0.0
        )
        expenditure_amount = float(
            attrs.get(
                "expenditure_amount",
                getattr(self.instance, "expenditure_amount", 0.0),
            )
            or 0.0
        )

        if cash_amount < 0:
            raise serializers.ValidationError(
                {"cash_amount": "Cash amount cannot be negative."}
            )
        if expenditure_amount < 0:
            raise serializers.ValidationError(
                {"expenditure_amount": "Expenditure amount cannot be negative."}
            )

        if entry_type in (
            CashExpenditure.EntryType.CASH_IN,
            CashExpenditure.EntryType.ONLINE_IN,
        ):
            if cash_amount <= 0:
                raise serializers.ValidationError(
                    {
                        "cash_amount": f"cash_amount must be greater than zero for {entry_type}."
                    }
                )
            attrs["cash_amount"] = cash_amount
            attrs["expenditure_amount"] = 0.0
        elif entry_type == CashExpenditure.EntryType.EXPENDITURE:
            if expenditure_amount <= 0:
                raise serializers.ValidationError(
                    {
                        "expenditure_amount": "expenditure_amount must be greater than zero for EXPENDITURE."
                    }
                )
            attrs["expenditure_amount"] = expenditure_amount
            attrs["cash_amount"] = 0.0

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
    Serializer representing the comprehensive balance summary:
    Total cash in, total online in, total expenditure, cash vs online expenses,
    and net available balances.
    """

    total_cash_in = serializers.FloatField(
        help_text="Sum of all physical cash additions (CASH_IN)."
    )
    total_online_in = serializers.FloatField(
        help_text="Sum of all digital/online additions (ONLINE_IN)."
    )
    total_cash_amount = serializers.FloatField(
        help_text="Total inflow across physical cash and online (total_cash_in + total_online_in)."
    )
    total_expenditure_amount = serializers.FloatField(
        help_text="Sum of all expenditures and expenses."
    )
    cash_expenditure_amount = serializers.FloatField(
        help_text="Total expenditures paid via physical cash."
    )
    online_expenditure_amount = serializers.FloatField(
        help_text="Total expenditures paid via online/digital methods."
    )
    total_available_balance = serializers.FloatField(
        help_text="Net available balance across cash and online (total_cash_amount - total_expenditure_amount)."
    )
    available_cash_balance = serializers.FloatField(
        help_text="Available physical cash balance (total_cash_in - cash_expenditure_amount)."
    )
    available_online_balance = serializers.FloatField(
        help_text="Available online balance (total_online_in - online_expenditure_amount)."
    )
    total_entries = serializers.IntegerField(
        help_text="Total number of transaction records."
    )
    cash_in_entries_count = serializers.IntegerField(
        help_text="Count of entries with physical cash additions (CASH_IN)."
    )
    online_in_entries_count = serializers.IntegerField(
        help_text="Count of entries with digital/online additions (ONLINE_IN)."
    )
    expenditure_entries_count = serializers.IntegerField(
        help_text="Count of entries with expenditures (EXPENDITURE)."
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



from accounting.models import Vendor, VendorTransaction
from accounting.services.vendor_service import VendorService, VendorTransactionService


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

    class Meta:
        model = VendorTransaction
        fields = [
            "id",
            "vendor",
            "vendor_name",
            "title",
            "transaction_type",
            "transaction_type_display",
            "amount",
            "date",
            "payment_method",
            "payment_method_display",
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
            "vendor_name",
            "transaction_type_display",
            "payment_method_display",
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


