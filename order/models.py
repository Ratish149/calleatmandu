import random

from django.conf import settings
from django.db import models

from common.models import BaseModel


def generate_order_number():
    """Generate a unique order number like EAT_482931."""
    while True:
        number = f"ORD_{random.randint(100000, 999999)}"
        if not Order.objects.filter(order_number=number).exists():
            return number


def generate_barcode_number():
    """Generate a unique 12-digit barcode number."""
    while True:
        number = "".join([str(random.randint(0, 9)) for _ in range(12)])
        if not Order.objects.filter(barcode_number=number).exists():
            return number


class Order(BaseModel):
    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PREPARING = "PREPARING", "Preparing"
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for Delivery"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentType(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        NPS = "NPS", "NPS Payment"

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

    # Payment Info
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.COD,
        db_index=True,
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )
    is_paid = models.BooleanField(
        default=False,
        db_index=True,
    )

    order_number = models.CharField(
        max_length=12,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Human-readable order ID, e.g. EAT_482931",
    )
    barcode_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="Unique barcode number for scanning, e.g. 890123456789",
    )
    is_pos_order = models.BooleanField(default=False)

    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_by",
    )
    assigned_to_rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_to_rider",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["payment_type", "is_paid"]),
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None
        status_changed = False

        if not is_new:
            old_order = Order.objects.filter(pk=self.pk).only("status").first()
            if old_order and old_order.status != self.status:
                old_status = old_order.status
                status_changed = True
        else:
            status_changed = True

        if not self.order_number:
            self.order_number = generate_order_number()
        if not self.barcode_number:
            self.barcode_number = generate_barcode_number()

        super().save(*args, **kwargs)

        if status_changed:
            comment = getattr(self, "_status_change_comment", None)
            changed_by = getattr(self, "_status_changed_by", None)
            if is_new and not comment:
                comment = "Order created"
            OrderStatusHistory.objects.create(
                order=self,
                old_status=old_status,
                status=self.status,
                comment=comment,
                changed_by=changed_by,
            )
            if hasattr(self, "_status_change_comment"):
                delattr(self, "_status_change_comment")
            if hasattr(self, "_status_changed_by"):
                delattr(self, "_status_changed_by")

    def __str__(self):
        return f"{self.order_number} - {self.customer_name} ({self.status})"


class OrderStatusHistory(BaseModel):
    """
    Log history of order status changes with optional comments and tracking who made the change.
    """

    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status = models.CharField(
        max_length=30,
        choices=Order.OrderStatus.choices,
        blank=True,
        null=True,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=Order.OrderStatus.choices,
        db_index=True,
    )
    comment = models.TextField(
        blank=True,
        null=True,
        help_text="Optional comment explaining the order status change.",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
    )

    class Meta:
        verbose_name = "Order Status History"
        verbose_name_plural = "Order Status Histories"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        from_str = f"{self.old_status} \u2192 " if self.old_status else ""
        return f"Order #{self.order.order_number}: {from_str}{self.status}"


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
