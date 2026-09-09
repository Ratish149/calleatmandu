from django.conf import settings
from django.db import models

from common.models import BaseModel


class RiderLocation(BaseModel):
    """
    Stores the current real-time GPS location and status of a delivery rider.
    """

    rider = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location",
        db_index=True,
    )
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField(db_index=True)
    is_online = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether the rider is currently active and available.",
    )
    last_updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = "tracking_rider_location"
        verbose_name = "Rider Location"
        verbose_name_plural = "Rider Locations"
        indexes = [
            models.Index(fields=["is_online", "last_updated_at"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        status_str = "Online" if self.is_online else "Offline"
        return f"Rider #{self.rider_id} ({self.rider.username}) - [{self.latitude}, {self.longitude}] ({status_str})"


class RiderLocationHistory(BaseModel):
    """
    Breadcrumb trail of rider historical GPS locations for route audit and analytics.
    """

    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_history",
        db_index=True,
    )
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        db_table = "tracking_rider_location_history"
        verbose_name = "Rider Location History"
        verbose_name_plural = "Rider Location Histories"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["rider", "created_at"]),
        ]

    def __str__(self):
        return f"History: Rider #{self.rider_id} @ {self.created_at} [{self.latitude}, {self.longitude}]"
