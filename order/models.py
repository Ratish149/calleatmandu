from django.db import models

from common.models import BaseModel


class Order(BaseModel):
    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PREPARING = "PREPARING", "Preparing"
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for Delivery"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    branch = models.ForeignKey(
        "account.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text="Nearest branch assigned to fulfill this order.",
    )

    # Customer Details
    customer_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20)
    delivery_location = models.CharField(max_length=255)
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField(db_index=True)
    special_note = models.TextField(blank=True, null=True)

    # Financial & Offer Info
    subtotal = models.FloatField(default=0.0)
    discount_amount = models.FloatField(default=0.0)
    delivery_fee = models.FloatField(default=0.0)
    total_amount = models.FloatField(default=0.0)
    promo_code = models.ForeignKey(
        "offer.PromoCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    offer = models.ForeignKey(
        "offer.Offer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name} ({self.status})"


class OrderItem(BaseModel):
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "product.Product", on_delete=models.CASCADE, related_name="order_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.FloatField()
    subtotal = models.FloatField()

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order #{self.order_id})"
