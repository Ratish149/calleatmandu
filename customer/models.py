from django.conf import settings
from django.db import models

from common.models import BaseModel


class CustomerFollowUp(BaseModel):
    """
    Model to track and save follow-up notes for customers based on phone number.
    """

    phone_number = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Customer phone number (e.g., 10-digit mobile number).",
    )
    customer_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        help_text="Customer name at the time of follow-up.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_followups",
        help_text="Associated registered user account if customer is registered.",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes and remarks from the follow-up.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_followups",
        help_text="Staff or operational user who recorded this follow-up.",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_followups",
        help_text="Branch associated with this follow-up.",
    )

    class Meta:
        db_table = "customer_followup"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
            models.Index(fields=["branch", "-created_at"]),
        ]

    def __str__(self):
        created_str = (
            self.created_at.strftime("%Y-%m-%d") if self.created_at else ""
        )
        return f"FollowUp({self.phone_number} on {created_str})"
