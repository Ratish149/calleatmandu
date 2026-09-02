from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    Model for storing user notifications for real-time delivery and offline history retrieval.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50,
        default="order_update",
        db_index=True,
    )
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["is_read", "created_at"]),
        ]

    def __str__(self):
        user_label = self.user.username if self.user else "Global"
        return f"Notification({user_label} - {self.title} - Read: {self.is_read})"
