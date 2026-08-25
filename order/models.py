import random

from django.conf import settings
from django.db import models

from common.models import BaseModel


def generate_order_number():
    """Generate a unique order number like EAT_482931."""
    while True:
        number = f"EAT_{random.randint(100000, 999999)}"
        if not Order.objects.filter(order_number=number).exists():
            return number


class Order(BaseModel):
    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PREPARING = "PREPARING", "Preparing"
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for Delivery"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
        null=True,
        blank=True,
    )
    branch = models.ForeignKey(
        "user_account.Branch",
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

    order_number = models.CharField(
        max_length=12,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Human-readable order ID, e.g. EAT_482931",
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

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_order_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.customer_name} ({self.status})"


class OrderItem(BaseModel):
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "product.Product", on_delete=models.CASCADE, related_name="order_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.FloatField()
    extras_price = models.FloatField(
        default=0.0
    )  # total surcharge from selected extras
    subtotal = models.FloatField()  # (unit_price + extras_price) * quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order #{self.order_id})"


class OrderItemExtra(BaseModel):
    """
    Records which extras were selected for a specific OrderItem.
    Prices are snapshotted at order time so historical data stays accurate
    even if the menu changes later.
    """

    order_item = models.ForeignKey(
        "OrderItem", on_delete=models.CASCADE, related_name="selected_extras"
    )
    extra = models.ForeignKey(
        "product.ProductExtra",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_item_extras",
    )
    # Snapshot of extra name & price at the time the order was placed
    extra_name = models.CharField(max_length=100)
    additional_price = models.FloatField(default=0.0)

    class Meta:
        indexes = [
            models.Index(fields=["order_item"]),
        ]

    def __str__(self):
        return f"{self.order_item} \u203a {self.extra_name} (+{self.additional_price})"
