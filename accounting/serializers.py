from rest_framework import serializers

from accounting.models import CashExpenditure
from accounting.services.accounting_service import CashExpenditureService


class CashExpenditureSerializer(serializers.ModelSerializer):
    """
    Serializer for recording, updating, and viewing Cash & Expenditure records.
    Branch is automatically assigned from the logged-in user — not required in payload.
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    net_amount = serializers.FloatField(read_only=True)

    class Meta:
        model = CashExpenditure
        fields = [
            "id",
            "title",
            "entry_type",
            "cash_amount",
            "expenditure_amount",
            "net_amount",
            "date",
            "payment_method",
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
            "branch",
            "branch_name",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        cash_amount = attrs.get(
            "cash_amount", getattr(self.instance, "cash_amount", 0.0)
        )
        expenditure_amount = attrs.get(
            "expenditure_amount", getattr(self.instance, "expenditure_amount", 0.0)
        )

        if cash_amount < 0:
            raise serializers.ValidationError(
                {"cash_amount": "Cash amount cannot be negative."}
            )
        if expenditure_amount < 0:
            raise serializers.ValidationError(
                {"expenditure_amount": "Expenditure amount cannot be negative."}
            )

        if cash_amount == 0 and expenditure_amount == 0:
            raise serializers.ValidationError(
                "Please enter a valid cash_amount (Cash In) or expenditure_amount (Expense)."
            )

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
    Total cash added, total expenditure spent, and current available balance.
    """

    total_cash_amount = serializers.FloatField(
        help_text="Sum of all cash additions and deposits."
    )
    total_expenditure_amount = serializers.FloatField(
        help_text="Sum of all expenditures and expenses."
    )
    total_available_balance = serializers.FloatField(
        help_text="Total available cash balance (total_cash_amount - total_expenditure_amount)."
    )
    total_entries = serializers.IntegerField(
        help_text="Total number of transaction records."
    )
    cash_in_entries_count = serializers.IntegerField(
        help_text="Count of entries with cash additions."
    )
    expenditure_entries_count = serializers.IntegerField(
        help_text="Count of entries with expenditures."
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
