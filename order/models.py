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
        READY_FOR_PICKUP = "READY_FOR_PICKUP", "Ready for Pickup"
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for Delivery"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentType(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        NPS = "NPS", "NPS Payment"

    class OrderType(models.TextChoices):
        DELIVERY = "DELIVERY", "Delivery"
        TAKEAWAY = "TAKEAWAY", "Takeaway"
        DINEIN = "DINEIN", "Dine in"

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
    customer_name = models.CharField(max_length=150, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    delivery_location = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.FloatField(db_index=True, null=True, blank=True)
    longitude = models.FloatField(db_index=True, null=True, blank=True)
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
    order_type = models.CharField(
        max_length=20,
        choices=OrderType.choices,
        db_index=True,
        null=True,
        blank=True,
        default=OrderType.DELIVERY,
    )

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

        # Recalculate total_amount on save to guarantee consistency across all update paths
        subtotal = float(self.subtotal or 0.0)
        delivery_fee = float(self.delivery_fee or 0.0)
        discount_amount = float(self.discount_amount or 0.0)
        self.total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            update_fields = set(kwargs["update_fields"])
            update_fields.add("total_amount")
            kwargs["update_fields"] = list(update_fields)

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
        return f"{self.order_item} › {self.extra_name} (+{self.additional_price})"


class ActivityLog(BaseModel):
    """
    Audit and activity log recording changes to order details, orders, products,
    categories, users, settings, and other critical business records.
    """

    class ActionType(models.TextChoices):
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"

    class EntityType(models.TextChoices):
        ORDER = "ORDER", "Order"
        ORDER_DETAIL = "ORDER_DETAIL", "Order Detail"
        PRODUCT = "PRODUCT", "Product"
        CATEGORY = "CATEGORY", "Category"
        USER = "USER", "User"
        SETTING = "SETTING", "Setting"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        help_text="User who triggered this action (if authenticated).",
    )
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        db_index=True,
        help_text="Type of action performed: CREATE, UPDATE, DELETE.",
    )
    entity_type = models.CharField(
        max_length=30,
        choices=EntityType.choices,
        db_index=True,
        help_text="Category of the entity affected.",
    )
    entity_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Target model or entity name (e.g. Order, OrderItem, Product, Category, User, DeliveryPricing).",
    )
    record_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Primary key/identifier of the affected record.",
    )
    record_repr = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Human-readable title or label of the affected record.",
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        help_text="Associated Order if this activity relates to an order or its items.",
    )
    description = models.TextField(
        help_text="Human-readable summary of the change or event.",
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dictionary detailing changed fields with their previous and new values.",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address where the action originated.",
    )

    class Meta:
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["order", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["entity_name", "record_id"]),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "System"
        return f"[{self.action_type}] {self.entity_name} ({self.record_repr or self.record_id}) by {user_str}"
