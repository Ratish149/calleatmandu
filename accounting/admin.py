from django.contrib import admin
from django.db import models
from django.db.models.functions import Coalesce
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from accounting.models import (
    CashExpenditure,
    CreditEntry,
    CreditOwner,
    CreditSettlement,
    Vendor,
    VendorTransaction,
)


class VendorTransactionInline(TabularInline):
    model = VendorTransaction
    extra = 0
    show_change_link = True
    fields = (
        "date",
        "transaction_type",
        "amount",
        "payment_method",
        "receipt_type",
        "receipt_image",
        "branch",
        "created_by",
    )
    readonly_fields = ("created_at",)


@admin.register(Vendor)
class VendorAdmin(ModelAdmin):
    list_display = (
        "name",
        "phone_number",
        "branch",
        "get_total_billed",
        "get_total_paid",
        "get_remaining_due",
        "created_at",
    )
    list_filter = (
        "branch",
        "created_at",
    )
    search_fields = (
        "name",
        "phone_number",
        "address",
        "branch__name",
    )
    list_select_related = ("branch",)
    autocomplete_fields = ("branch",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "total_amount_to_be_paid",
        "total_amount_paid",
        "remaining_due",
    )
    inlines = [VendorTransactionInline]
    ordering = ("name",)

    fieldsets = (
        (
            "Vendor Information",
            {
                "fields": (
                    "name",
                    "phone_number",
                    "address",
                    "branch",
                ),
            },
        ),
        (
            "Financial Summary",
            {
                "fields": (
                    "total_amount_to_be_paid",
                    "total_amount_paid",
                    "remaining_due",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("branch").annotate(
            annotated_total_billed=Coalesce(
                models.Sum(
                    "transactions__amount",
                    filter=models.Q(
                        transactions__transaction_type=VendorTransaction.TransactionType.BILL
                    ),
                ),
                models.Value(0.0),
                output_field=models.FloatField(),
            ),
            annotated_total_paid=Coalesce(
                models.Sum(
                    "transactions__amount",
                    filter=models.Q(
                        transactions__transaction_type=VendorTransaction.TransactionType.PAYMENT
                    ),
                ),
                models.Value(0.0),
                output_field=models.FloatField(),
            ),
        )

    @admin.display(description="Total Billed", ordering="annotated_total_billed")
    def get_total_billed(self, obj):
        val = getattr(obj, "annotated_total_billed", obj.total_amount_to_be_paid)
        return f"Rs. {val:,.2f}"

    @admin.display(description="Total Paid", ordering="annotated_total_paid")
    def get_total_paid(self, obj):
        val = getattr(obj, "annotated_total_paid", obj.total_amount_paid)
        return f"Rs. {val:,.2f}"

    @admin.display(description="Remaining Due")
    def get_remaining_due(self, obj):
        billed = getattr(obj, "annotated_total_billed", obj.total_amount_to_be_paid)
        paid = getattr(obj, "annotated_total_paid", obj.total_amount_paid)
        return f"Rs. {(billed - paid):,.2f}"


@admin.register(VendorTransaction)
class VendorTransactionAdmin(ModelAdmin):
    list_display = (
        "date",
        "vendor",
        "transaction_type",
        "amount",
        "payment_method",
        "receipt_type",
        "branch",
        "created_by",
        "created_at",
    )
    list_filter = (
        "transaction_type",
        "payment_method",
        "receipt_type",
        "branch",
        "date",
        "created_at",
    )
    search_fields = (
        "vendor__name",
        "notes",
        "created_by__username",
    )
    list_select_related = (
        "vendor",
        "branch",
        "created_by",
    )
    autocomplete_fields = (
        "vendor",
        "branch",
        "created_by",
    )
    ordering = (
        "-date",
        "-created_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "is_bill",
        "is_payment",
    )

    fieldsets = (
        (
            "Transaction Details",
            {
                "fields": (
                    "vendor",
                    "transaction_type",
                    "amount",
                    "date",
                    "payment_method",
                    "receipt_type",
                ),
            },
        ),
        (
            "Receipt & Notes",
            {
                "fields": (
                    "receipt_image",
                    "notes",
                ),
            },
        ),
        (
            "Branch & Audit",
            {
                "fields": (
                    "branch",
                    "created_by",
                    "is_bill",
                    "is_payment",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )


class CreditEntryInline(StackedInline):
    model = CreditEntry
    extra = 0
    show_change_link = True
    readonly_fields = (
        "created_at",
        "updated_at",
        "amount_settled",
        "amount_remaining",
        "is_fully_settled",
    )


@admin.register(CashExpenditure)
class CashExpenditureAdmin(ModelAdmin):
    list_display = (
        "date",
        "cash_amount",
        "online_amount",
        "credit_amount",
        "delivery_charge",
        "available_balance",
        "total_sales",
        "branch",
        "created_by",
        "created_at",
    )
    list_filter = (
        "branch",
        "date",
        "created_at",
    )
    search_fields = (
        "notes",
        "created_by__username",
    )
    list_select_related = (
        "branch",
        "created_by",
    )
    autocomplete_fields = (
        "branch",
        "created_by",
    )
    ordering = (
        "-date",
        "-created_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "available_balance",
        "total_sales",
        "net_amount",
    )
    inlines = [CreditEntryInline]

    fieldsets = (
        (
            "Entry Information",
            {
                "fields": (
                    "date",
                    "branch",
                    "created_by",
                ),
            },
        ),
        (
            "Financial Details",
            {
                "fields": (
                    "cash_amount",
                    "online_amount",
                    "credit_amount",
                    "delivery_charge",
                ),
            },
        ),
        (
            "Computed Balances",
            {
                "fields": (
                    "available_balance",
                    "total_sales",
                    "net_amount",
                ),
            },
        ),
        (
            "Documentation",
            {
                "fields": (
                    "receipt_image",
                    "notes",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )


class CreditSettlementInline(StackedInline):
    model = CreditSettlement
    extra = 0
    show_change_link = True
    readonly_fields = (
        "created_at",
        "updated_at",
        "total_settled",
        "payment_method",
    )


class CreditEntryForOwnerInline(TabularInline):
    model = CreditEntry
    extra = 0
    show_change_link = True
    fields = (
        "cash_entry",
        "credit_amount",
        "status",
        "amount_settled",
        "amount_remaining",
        "is_fully_settled",
        "created_at",
    )
    readonly_fields = (
        "amount_settled",
        "amount_remaining",
        "is_fully_settled",
        "created_at",
    )


@admin.register(CreditOwner)
class CreditOwnerAdmin(ModelAdmin):
    list_display = (
        "name",
        "phone_number",
        "branch",
        "get_total_credit_amount",
        "get_total_settled_amount",
        "get_remaining_due",
        "created_at",
    )
    list_filter = (
        "branch",
        "created_at",
    )
    search_fields = (
        "name",
        "phone_number",
        "address",
        "notes",
    )
    list_select_related = ("branch",)
    autocomplete_fields = ("branch",)
    ordering = ("name",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "total_credit_amount",
        "total_settled_amount",
        "remaining_due",
        "is_cleared",
    )
    inlines = [CreditEntryForOwnerInline]

    fieldsets = (
        (
            "Owner Information",
            {
                "fields": (
                    "name",
                    "phone_number",
                    "address",
                    "branch",
                ),
            },
        ),
        (
            "Financial Overview",
            {
                "fields": (
                    "total_credit_amount",
                    "total_settled_amount",
                    "remaining_due",
                    "is_cleared",
                ),
            },
        ),
        (
            "Notes & Remarks",
            {
                "fields": ("notes",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Total Credit (Rs.)")
    def get_total_credit_amount(self, obj):
        return f"Rs. {obj.total_credit_amount:,.2f}"

    @admin.display(description="Settled (Rs.)")
    def get_total_settled_amount(self, obj):
        return f"Rs. {obj.total_settled_amount:,.2f}"

    @admin.display(description="Remaining Due (Rs.)")
    def get_remaining_due(self, obj):
        due = obj.remaining_due
        return f"Rs. {due:,.2f}" if due > 0 else "Cleared"


@admin.register(CreditEntry)
class CreditEntryAdmin(ModelAdmin):
    list_display = (
        "date",
        "credit_owner",
        "get_owner_name",
        "credit_amount",
        "status",
        "cash_entry",
        "get_amount_settled",
        "get_amount_remaining",
        "get_is_fully_settled",
        "branch",
        "created_by",
        "created_at",
    )
    list_filter = (
        "status",
        "date",
        "branch",
        "created_at",
    )
    search_fields = (
        "notes",
        "credit_owner__name",
        "credit_owner__phone_number",
        "created_by__username",
        "cash_entry__notes",
    )
    list_select_related = (
        "cash_entry",
        "settlement",
        "branch",
        "created_by",
        "credit_owner",
    )
    autocomplete_fields = (
        "cash_entry",
        "credit_owner",
        "branch",
        "created_by",
    )
    ordering = ("-date", "-created_at")
    readonly_fields = (
        "created_at",
        "updated_at",
        "amount_settled",
        "amount_remaining",
        "is_fully_settled",
        "get_owner_name",
    )
    inlines = [CreditSettlementInline]

    fieldsets = (
        (
            "Credit Details",
            {
                "fields": (
                    "date",
                    "credit_owner",
                    "credit_amount",
                    "status",
                    "cash_entry",
                    "branch",
                    "created_by",
                ),
            },
        ),
        (
            "Settlement Overview",
            {
                "fields": (
                    "amount_settled",
                    "amount_remaining",
                    "is_fully_settled",
                ),
            },
        ),
        (
            "Notes",
            {
                "fields": ("notes",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Credit Owner")
    def get_owner_name(self, obj):
        return obj.owner_name

    @admin.display(description="Amount Settled")
    def get_amount_settled(self, obj):
        return f"Rs. {obj.amount_settled:,.2f}"

    @admin.display(description="Amount Remaining")
    def get_amount_remaining(self, obj):
        return f"Rs. {obj.amount_remaining:,.2f}"

    @admin.display(boolean=True, description="Fully Settled")
    def get_is_fully_settled(self, obj):
        return obj.is_fully_settled


@admin.register(CreditSettlement)
class CreditSettlementAdmin(ModelAdmin):
    list_display = (
        "credit_entry",
        "settled_date",
        "cash_settled",
        "online_settled",
        "get_total_settled",
        "payment_method",
        "branch",
        "created_by",
        "created_at",
    )
    list_filter = (
        "settled_date",
        "branch",
        "created_at",
    )
    search_fields = (
        "notes",
        "created_by__username",
        "credit_entry__notes",
    )
    list_select_related = (
        "credit_entry",
        "credit_entry__cash_entry",
        "branch",
        "created_by",
    )
    autocomplete_fields = (
        "credit_entry",
        "branch",
        "created_by",
    )
    ordering = (
        "-settled_date",
        "-created_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "total_settled",
        "payment_method",
    )

    fieldsets = (
        (
            "Settlement Details",
            {
                "fields": (
                    "credit_entry",
                    "settled_date",
                    "branch",
                    "created_by",
                ),
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "cash_settled",
                    "online_settled",
                    "total_settled",
                    "payment_method",
                ),
            },
        ),
        (
            "Notes",
            {
                "fields": ("notes",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Total Settled")
    def get_total_settled(self, obj):
        return f"Rs. {obj.total_settled:,.2f}"
