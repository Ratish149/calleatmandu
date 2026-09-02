from django.db import models


class Notification(models.Model):
    """
    Model for storing system notifications for real-time delivery and offline history retrieval.
    """

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
            models.Index(fields=["is_read", "created_at"]),
            models.Index(fields=["notification_type", "is_read"]),
        ]

    def __str__(self):
        return f"Notification({self.title} - Read: {self.is_read})"
