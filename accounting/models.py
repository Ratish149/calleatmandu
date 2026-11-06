from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import BaseModel


class Vendor(BaseModel):
    """
    Represents a supplier or vendor associated with a specific branch.
    Financial transactions (amount to be paid vs amount paid) are tracked
    in the separate VendorTransaction model.
    """

    name = models.CharField(
        max_length=200,
        help_text="Full name of the vendor or business.",
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Primary contact phone number of the vendor.",
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Physical or mailing address of the vendor.",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendors",
        db_index=True,
        help_text="Branch this vendor is associated with.",
    )

    class Meta:
        db_table = "accounting_vendor"
        ordering = ["name"]
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"
        indexes = [
            models.Index(fields=["branch"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.branch})"

    @property
    def total_amount_to_be_paid(self) -> float:
        """Total billed amount from BILL-type transactions for this vendor."""
        result = self.transactions.filter(
            transaction_type=VendorTransaction.TransactionType.BILL
        ).aggregate(total=models.Sum("amount"))
        return round(result["total"] or 0.0, 2)

    @property
    def total_amount_paid(self) -> float:
        """Total amount actually paid to this vendor via PAYMENT-type transactions."""
        result = self.transactions.filter(
            transaction_type=VendorTransaction.TransactionType.PAYMENT
        ).aggregate(total=models.Sum("amount"))
        return round(result["total"] or 0.0, 2)

    @property
    def remaining_due(self) -> float:
        """
        Outstanding amount owed to this vendor.
        Positive = pending payment owed to vendor.
        Zero = fully settled.
        Negative = advance paid / credit balance.
        """
        return round(self.total_amount_to_be_paid - self.total_amount_paid, 2)


class VendorTransaction(BaseModel):
    """
    Records individual transactions for a vendor.
    Each transaction is either:
      - BILL    : An invoice or payable amount owed to the vendor.
      - PAYMENT : An actual cash or online payment made to the vendor.
    A single `amount` field holds the value; `transaction_type` determines its nature.
    """

    class TransactionType(models.TextChoices):
        BILL = "BILL", "Bill (Amount to be Paid)"
        PAYMENT = "PAYMENT", "Payment (Amount Paid)"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        ESEWA = "ESEWA", "eSewa"
        KHALTI = "KHALTI", "Khalti"
        CHEQUE = "CHEQUE", "Cheque"
        OTHER = "OTHER", "Other"

    class ReceiptType(models.TextChoices):
        VAT = "VAT", "VAT Receipt"
        NON_VAT = "NON_VAT", "Non-VAT Receipt"

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="transactions",
        db_index=True,
        help_text="The vendor this transaction belongs to.",
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        db_index=True,
        null=True,
        blank=True,
        help_text="BILL: amount owed to vendor. PAYMENT: actual amount paid to vendor.",
    )
    amount = models.FloatField(
        default=0.0,
        help_text="Transaction amount. Interpreted as a bill or payment based on transaction_type.",
    )
    date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Date when this transaction occurred.",
    )
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        db_index=True,
        help_text="Mode of payment (applicable for PAYMENT type transactions).",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Invoice number, bill reference, or remarks.",
    )
    receipt_image = models.FileField(
        upload_to="accounting/vendor_receipts/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional uploaded bill, voucher, or receipt for this transaction.",
    )
    receipt_type = models.CharField(
        max_length=10,
        choices=ReceiptType.choices,
        null=True,
        blank=True,
        db_index=True,
        help_text="Indicates whether the receipt is VAT or Non-VAT.",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_transactions",
        db_index=True,
        help_text="Branch associated with this transaction.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_vendor_transactions",
        db_index=True,
        help_text="Staff or user who recorded this transaction.",
    )

    class Meta:
        db_table = "accounting_vendor_transaction"
        ordering = ["-date", "-created_at"]
        verbose_name = "Vendor Transaction"
        verbose_name_plural = "Vendor Transactions"
        indexes = [
            models.Index(fields=["vendor", "date"]),
            models.Index(fields=["vendor", "transaction_type"]),
            models.Index(fields=["branch", "date"]),
            models.Index(fields=["date", "-created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.date} | {self.vendor.name} "
            f"({self.get_transaction_type_display()}: {self.amount})"
        )

    @property
    def is_bill(self) -> bool:
        """Returns True if this transaction is a bill (amount to be paid)."""
        return self.transaction_type == self.TransactionType.BILL

    @property
    def is_payment(self) -> bool:
        """Returns True if this transaction is a payment (amount paid)."""
        return self.transaction_type == self.TransactionType.PAYMENT


class CashExpenditure(BaseModel):
    """
    Model to record cash amount, online amount, and delivery charge
    for a given date so that available balance can be calculated:
    available_balance = cash_amount + online_amount - delivery_charge.
    """

    cash_amount = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Physical cash amount received/collected.",
    )
    online_amount = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Online or digital amount received (eSewa, Khalti, Bank Transfer, etc.).",
    )
    credit_amount = models.FloatField(
        default=0.0,
        db_index=True,
        help_text=(
            "Amount given on credit (not yet collected). "
            "Total sales = cash + online + credit - delivery_charge."
        ),
    )
    delivery_charge = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Delivery charge amount.",
    )
    date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Date when this transaction occurred.",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional remarks or notes.",
    )
    receipt_image = models.FileField(
        upload_to="accounting/receipts/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional uploaded bill, voucher, or receipt document.",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_expenditures",
        db_index=True,
        help_text="Branch associated with this transaction.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_cash_expenditures",
        db_index=True,
        help_text="Staff or operational user who recorded this transaction.",
    )

    class Meta:
        db_table = "accounting_cash_expenditure"
        ordering = ["-date", "-created_at"]
        verbose_name = "Cash & Expenditure Entry"
        verbose_name_plural = "Cash & Expenditure Entries"
        indexes = [
            models.Index(fields=["date", "-created_at"]),
            models.Index(fields=["branch", "date"]),
        ]

    def __str__(self):
        return (
            f"{self.date} - Cash: {self.cash_amount}, Online: {self.online_amount}, "
            f"Delivery: {self.delivery_charge} (Available: {self.available_balance})"
        )

    @property
    def available_balance(self) -> float:
        """
        Calculates available (collected) balance — credit is excluded
        because it has not been collected yet:
        cash_amount + online_amount - delivery_charge
        """
        return round(
            float(self.cash_amount or 0.0)
            + float(self.online_amount or 0.0)
            - float(self.delivery_charge or 0.0),
            2,
        )

    @property
    def total_sales(self) -> float:
        """
        Total sales amount for the entry including credit (uncollected):
        cash_amount + online_amount + credit_amount - delivery_charge
        """
        return round(
            float(self.cash_amount or 0.0)
            + float(self.online_amount or 0.0)
            + float(self.credit_amount or 0.0)
            - float(self.delivery_charge or 0.0),
            2,
        )

    @property
    def net_amount(self) -> float:
        """Alias for available_balance."""
        return self.available_balance


class CreditEntry(BaseModel):
    """
    Records a credit amount linked to a CashExpenditure entry.
    Credit represents sales that were not collected on the day —
    the customer owes this amount and it will be settled later.

    Total sales = cash_amount + online_amount + credit_amount - delivery_charge.
    Available (collected) balance = cash_amount + online_amount - delivery_charge.

    One CashExpenditure entry can have at most one CreditEntry.
    Settlement is tracked in CreditSettlement.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SETTLED = "SETTLED", "Settled"

    cash_entry = models.OneToOneField(
        CashExpenditure,
        on_delete=models.CASCADE,
        related_name="credit_entry",
        db_index=True,
        help_text="The cash entry this credit is associated with.",
    )
    credit_amount = models.FloatField(
        help_text="Total credit amount given (amount yet to be collected).",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Settlement status: PENDING or SETTLED.",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Remarks about this credit (e.g. who owes, reason).",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_entries",
        db_index=True,
        help_text="Branch this credit belongs to.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_credit_entries",
        db_index=True,
        help_text="Staff who recorded this credit.",
    )

    class Meta:
        db_table = "accounting_credit_entry"
        ordering = ["-created_at"]
        verbose_name = "Credit Entry"
        verbose_name_plural = "Credit Entries"
        indexes = [
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return (
            f"Credit Rs. {self.credit_amount} on {self.cash_entry.date} "
            f"[{self.get_status_display()}]"
        )

    @property
    def amount_settled(self) -> float:
        """Total amount settled so far from CreditSettlement."""
        result = (
            self.settlement.aggregate(
                total=models.Sum(
                    models.ExpressionWrapper(
                        models.F("cash_settled") + models.F("online_settled"),
                        output_field=models.FloatField(),
                    )
                )
            )
            if hasattr(self, "settlement")
            else {"total": None}
        )
        # settlement is OneToOne so wrap safely
        try:
            s = self.settlement
            return round(
                float(s.cash_settled or 0.0) + float(s.online_settled or 0.0), 2
            )
        except CreditSettlement.DoesNotExist:
            return 0.0

    @property
    def amount_remaining(self) -> float:
        """Outstanding credit amount not yet settled."""
        return round(float(self.credit_amount or 0.0) - self.amount_settled, 2)

    @property
    def is_fully_settled(self) -> bool:
        """True when the full credit amount has been settled."""
        return self.amount_remaining <= 0.0


class CreditSettlement(BaseModel):
    """
    Records the settlement of a CreditEntry.
    One CreditEntry has exactly one CreditSettlement.
    Settlement can be split between cash and online payments.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        ONLINE = "ONLINE", "Online"

    credit_entry = models.OneToOneField(
        CreditEntry,
        on_delete=models.CASCADE,
        related_name="settlement",
        db_index=True,
        help_text="The credit entry being settled.",
    )
    cash_settled = models.FloatField(
        default=0.0,
        help_text="Amount settled via cash.",
    )
    online_settled = models.FloatField(
        default=0.0,
        help_text="Amount settled via online/digital payment.",
    )
    settled_date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Date when the credit was settled.",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Remarks about this settlement.",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_settlements",
        db_index=True,
        help_text="Branch this settlement belongs to.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_credit_settlements",
        db_index=True,
        help_text="Staff who recorded this settlement.",
    )

    class Meta:
        db_table = "accounting_credit_settlement"
        ordering = ["-settled_date", "-created_at"]
        verbose_name = "Credit Settlement"
        verbose_name_plural = "Credit Settlements"
        indexes = [
            models.Index(fields=["branch", "settled_date"]),
            models.Index(fields=["settled_date", "-created_at"]),
        ]

    def __str__(self):
        return (
            f"Settlement for Credit #{self.credit_entry_id} on {self.settled_date}: "
            f"Cash Rs. {self.cash_settled}, Online Rs. {self.online_settled}"
        )

    @property
    def total_settled(self) -> float:
        """Total amount settled (cash + online)."""
        return round(
            float(self.cash_settled or 0.0) + float(self.online_settled or 0.0), 2
        )

    @property
    def payment_method(self) -> str:
        """Derived payment method: CASH or ONLINE based on how the settlement was paid."""
        if float(self.online_settled or 0.0) > 0:
            return self.PaymentMethod.ONLINE
        return self.PaymentMethod.CASH
