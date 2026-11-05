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

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="transactions",
        db_index=True,
        help_text="The vendor this transaction belongs to.",
    )
    title = models.CharField(
        max_length=200,
        help_text="Short description of the transaction (e.g. 'Vegetable supply bill', 'Cash advance settlement').",
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
            f"{self.date} | {self.vendor.name} - {self.title} "
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
    Model to record general cash inflows (CASH_IN), online inflows (ONLINE_IN),
    and expenditures (EXPENDITURE / Cash Out) to accurately calculate
    the total available cash and online balance.

    Entry Types:
        - CASH_IN    : Physical cash received/added (e.g. cash sales, cash deposited).
        - ONLINE_IN  : Online money received (e.g. eSewa, Khalti, Bank Transfer inflow).
        - EXPENDITURE: Money paid out for general expenses (not vendor-specific).

    For vendor-specific transactions, use VendorTransaction instead.
    """

    class EntryType(models.TextChoices):
        CASH_IN = "CASH_IN", "Cash In / Addition"
        ONLINE_IN = "ONLINE_IN", "Online In / Digital Receipt"
        EXPENDITURE = "EXPENDITURE", "Expenditure / Cash Out"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        ESEWA = "ESEWA", "eSewa"
        KHALTI = "KHALTI", "Khalti"
        CHEQUE = "CHEQUE", "Cheque"
        OTHER = "OTHER", "Other"

    title = models.CharField(
        max_length=200,
        help_text="Short title or description of this cash entry or expenditure.",
    )
    entry_type = models.CharField(
        max_length=20,
        choices=EntryType.choices,
        default=EntryType.EXPENDITURE,
        db_index=True,
        help_text=(
            "CASH_IN: physical cash received. "
            "ONLINE_IN: digital/online money received. "
            "EXPENDITURE: money paid out as a general expense."
        ),
    )
    cash_amount = models.FloatField(
        default=0.0,
        help_text="Amount of cash added / received (Inflow). Used for CASH_IN and ONLINE_IN entries.",
    )
    expenditure_amount = models.FloatField(
        default=0.0,
        help_text="Amount spent on expenditure / expense (Outflow). Used for EXPENDITURE entries.",
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
        help_text="Mode of payment or collection.",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional remarks or invoice reference.",
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
            models.Index(fields=["entry_type", "date"]),
        ]

    def __str__(self):
        return f"{self.date} - {self.title} (+{self.cash_amount} / -{self.expenditure_amount})"

    @property
    def net_amount(self) -> float:
        """
        Net contribution of this entry to the available balance:
          - CASH_IN    →  +cash_amount
          - ONLINE_IN  →  +cash_amount
          - EXPENDITURE → -expenditure_amount
        """
        if self.entry_type == self.EntryType.EXPENDITURE:
            return round(-float(self.expenditure_amount), 2)
        return round(float(self.cash_amount), 2)

    @property
    def is_online(self) -> bool:
        """Returns True if this is an online/digital inflow entry."""
        return self.entry_type == self.EntryType.ONLINE_IN
