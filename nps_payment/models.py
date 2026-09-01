from django.db import models

from .constants import TRANSACTION_STATUS_CHOICES


class NPSConfig(models.Model):
    merchant_id = models.CharField(max_length=100)
    merchant_name = models.CharField(max_length=100)
    api_username = models.CharField(max_length=100)
    api_password = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    is_sandbox = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "NPS Configuration"
        verbose_name_plural = "NPS Configurations"

    def __str__(self):
        return f"{self.merchant_name} ({'Sandbox' if self.is_sandbox else 'Live'})"


class NPSTransaction(models.Model):
    order = models.ForeignKey(
        "order.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nps_transactions",
    )
    merchant_txn_id = models.CharField(max_length=100, unique=True, db_index=True)
    process_id = models.CharField(max_length=255, null=True, blank=True)
    gateway_txn_id = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    service_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default="Pending",
        db_index=True,
    )
    institution = models.CharField(max_length=150, null=True, blank=True)
    instrument = models.CharField(max_length=150, null=True, blank=True)
    transaction_remarks = models.TextField(null=True, blank=True)
    cbs_message = models.TextField(null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True, null=True)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["merchant_txn_id"]),
        ]

    def __str__(self):
        return f"NPS {self.merchant_txn_id} - Npr {self.amount} ({self.status})"
