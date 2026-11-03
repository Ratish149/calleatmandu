from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import BaseModel


class CashExpenditure(BaseModel):
    """
    Model to record cash inflows (additions/deposits) and expenditures (cash outflows/expenses)
    to accurately calculate the total available cash balance.
    """

    class EntryType(models.TextChoices):
        CASH_IN = "CASH_IN", "Cash In / Addition"
        EXPENDITURE = "EXPENDITURE", "Expenditure / Cash Out"
        BOTH = "BOTH", "Both (Cash In & Expenditure)"

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
        help_text="Whether this entry is cash added (CASH_IN), an expense (EXPENDITURE), or both.",
    )
    cash_amount = models.FloatField(
        default=0.0,
        help_text="Amount of cash added / received (Inflow).",
    )
    expenditure_amount = models.FloatField(
        default=0.0,
        help_text="Amount spent on expenditure / expense (Outflow).",
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
        help_text="Additional remarks, invoice number, or vendor details.",
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
        Net contribution of this entry to the cash balance:
        Positive means net cash added; negative means net expense.
        """
        return round(float(self.cash_amount) - float(self.expenditure_amount), 2)
