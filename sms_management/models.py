from django.conf import settings
from django.db import models


class SMSSettings(models.Model):
    """
    Per-branch post-delivery SMS config.
    Only branches with is_enabled=True send SMS, using their own message template.
    """

    DEFAULT_MESSAGE = (
        "Dear {customer_name}, how was your CallEatMandu order #{order_number}? "
        "We hope you enjoyed your meal. Thank you!"
    )

    branch = models.OneToOneField(
        "user_account.Branch",
        on_delete=models.CASCADE,
        related_name="sms_settings",
        help_text="Branch this SMS configuration belongs to.",
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Approve this branch for post-delivery SMS. "
            "If unchecked, orders from this branch will not trigger SMS."
        ),
    )
    delay_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Minutes to wait after delivery before sending the SMS.",
    )
    message_template = models.TextField(
        default=DEFAULT_MESSAGE,
        help_text=(
            "Message body for this branch. Placeholders: {customer_name}, {order_number}. "
            "Max ~720 characters for NestSMS text encoding."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SMS Settings"
        verbose_name_plural = "SMS Settings"
        ordering = ["branch__name"]

    def __str__(self):
        state = "Enabled" if self.is_enabled else "Disabled"
        branch_name = getattr(self.branch, "name", self.branch_id)
        return f"{branch_name} SMS ({state}, delay={self.delay_minutes}m)"

    @classmethod
    def get_for_branch(cls, branch):
        """Return SMS settings for a branch, or None if not configured."""
        if not branch:
            return None
        branch_id = getattr(branch, "pk", branch)
        return cls.objects.filter(branch_id=branch_id).select_related("branch").first()


class SMSLog(models.Model):
    """Tracks post-delivery SMS messages scheduled/sent via NestSMS."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    order = models.ForeignKey(
        "order.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_logs",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_logs",
        help_text="Branch that owned the order when SMS was scheduled.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    sender_id = models.CharField(max_length=50, blank=True, default="")
    job_id = models.CharField(max_length=100, blank=True, default="")
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this SMS should be sent after delivery.",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    cost = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    response_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_logs_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "status"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["status", "scheduled_at"]),
        ]
        verbose_name = "SMS Log"
        verbose_name_plural = "SMS Logs"

    def __str__(self):
        order_ref = getattr(self.order, "order_number", None) if self.order_id else None
        label = f"Order #{order_ref}" if order_ref else "SMS"
        return f"{label} → {self.phone_number} [{self.status}]"
