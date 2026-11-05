from rest_framework import serializers

from accounting.models import CashExpenditure, Vendor, VendorTransaction
from accounting.services.accounting_service import CashExpenditureService
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

    class Meta:
        model = CashExpenditure
        fields = [
            "id",
            "cash_amount",
            "online_amount",
            "delivery_charge",
            "available_balance",
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
            "available_balance",
            "net_amount",
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        cash_amount = float(
            attrs.get("cash_amount", getattr(self.instance, "cash_amount", 0.0)) or 0.0
        )
        online_amount = float(
            attrs.get("online_amount", getattr(self.instance, "online_amount", 0.0))
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
        if delivery_charge < 0:
            raise serializers.ValidationError({
                "delivery_charge": "Delivery charge cannot be negative."
            })

        attrs["cash_amount"] = cash_amount
        attrs["online_amount"] = online_amount
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
    Serializer representing the balance summary:
    Total cash amount, total online amount, total delivery charge,
    vendor payment amount, and net available balance
    (total_cash_amount + total_online_amount - total_delivery_charge - total_vendor_paid_amount).
    """

    total_cash_amount = serializers.FloatField(
        help_text="Sum of all physical cash amounts."
    )
    total_online_amount = serializers.FloatField(
        help_text="Sum of all digital/online amounts."
    )
    total_delivery_charge = serializers.FloatField(
        help_text="Sum of all delivery charges."
    )
    total_vendor_paid_amount = serializers.FloatField(
        default=0.0,
        help_text="Sum of all payments made to vendors.",
    )
    total_available_balance = serializers.FloatField(
        help_text="Net available balance (total_cash_amount + total_online_amount - total_delivery_charge - total_vendor_paid_amount)."
    )
    available_balance = serializers.FloatField(
        help_text="Alias for total_available_balance."
    )
    total_entries = serializers.IntegerField(
        help_text="Total number of transaction records."
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
