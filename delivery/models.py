from django.db import models
from django.utils import timezone

from common.models import BaseModel


class DeliveryPricing(BaseModel):
    price_per_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50.00,
        help_text="Delivery charge per kilometer based on road distance.",
    )
    minimum_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50.00,
        help_text="Base/minimum delivery fee applied regardless of distance.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether delivery calculation is active.",
    )

    class Meta:
        verbose_name = "Delivery Pricing"
        verbose_name_plural = "Delivery Pricing"

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"Rs. {self.price_per_km}/km (Min: Rs. {self.minimum_charge}) - {status}"

    def save(self, *args, **kwargs):
        self.pk = 1
        existing_created_at = (
            DeliveryPricing.objects
            .filter(pk=1)
            .values_list("created_at", flat=True)
            .first()
        )
        if existing_created_at and not self.created_at:
            self.created_at = existing_created_at
        elif not self.created_at:
            self.created_at = timezone.now()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion of the singleton instance
        pass

    @classmethod
    def get_instance(cls):
        """
        Retrieves or initializes the singleton instance.
        """
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "price_per_km": 50.00,
                "minimum_charge": 50.00,
                "is_active": True,
            },
        )
        return obj
