from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone

from common.models import BaseModel

# Create your models here.


class Category(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    image = models.FileField(upload_to="category/images/", null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Subcategory(BaseModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    category = models.ForeignKey(
        "Category", on_delete=models.SET_NULL, null=True, blank=True
    )
    image = models.FileField(upload_to="subcategory/images/", null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


def product_thumbnail_upload_path(instance, filename):
    folder = instance.slug or (slugify(instance.name) if instance.name else "unnamed")
    return f"product/{folder}/thumbnail/{filename}"


def product_image_upload_path(instance, filename):
    product_name = instance.product.name if instance.product else "unnamed"
    folder = instance.product.slug or (
        slugify(product_name) if product_name else "unnamed"
    )
    return f"product/{folder}/images/{filename}"


class Product(BaseModel):
    class ProductType(models.TextChoices):
        VEG = "VEG", "Veg"
        NON_VEG = "NON_VEG", "Non-Veg"
        DRINK = "DRINK", "Drink"
        LIQUOR = "LIQUOR", "Liquor"

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField()
    price = models.FloatField()
    cost_price = models.FloatField(default=0.0)
    type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        db_index=True,
        null=True,
        blank=True,
    )
    thumbnail_image = models.FileField(upload_to=product_thumbnail_upload_path)
    category = models.ForeignKey(
        "Category", on_delete=models.SET_NULL, null=True, blank=True
    )
    sub_category = models.ForeignKey(
        "Subcategory", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_best_seller = models.BooleanField(default=False)
    prepare_time = models.CharField(
        max_length=10, null=True, blank=True, help_text="in minutes"
    )
    stock = models.PositiveIntegerField(default=100)
    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    take_order = models.BooleanField(default=True)

    @property
    def is_drink_or_liquor(self) -> bool:
        if self.type in (self.ProductType.DRINK, self.ProductType.LIQUOR):
            return True
        keywords = (
            "drink",
            "liquor",
            "beverage",
            "alcohol",
            "wine",
            "beer",
            "whiskey",
            "whisky",
            "vodka",
            "rum",
            "gin",
            "bar",
        )
        cat_name = (getattr(self.category, "name", "") or "").lower()
        cat_slug = (getattr(self.category, "slug", "") or "").lower()
        sub_name = (getattr(self.sub_category, "name", "") or "").lower()
        sub_slug = (getattr(self.sub_category, "slug", "") or "").lower()
        return any(
            kw in cat_name or kw in cat_slug or kw in sub_name or kw in sub_slug
            for kw in keywords
        )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductExtra(BaseModel):
    """
    An optional add-on for a product.
    E.g. "Extra Cheese", "Crispy Fries", "Garlic Sauce"
    """

    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="extras"
    )
    name = models.CharField(max_length=100)  # e.g. "Extra Cheese"
    additional_price = models.FloatField(default=0.0)  # surcharge on top of base price

    class Meta:
        ordering = ["additional_price", "name"]

    def __str__(self):
        return f"{self.product.name} › {self.name} (+{self.additional_price})"


class ProductImage(BaseModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.FileField(upload_to=product_image_upload_path)

    def __str__(self):
        return f"{self.product.name} Image"


# ---------------------------------------------------------------------------
# Kitchen Inventory
# ---------------------------------------------------------------------------


class KitchenInventoryItem(BaseModel):
    """
    Master list of raw ingredients managed by the admin.

    - total_quantity: live current stock, automatically updated whenever
      a KitchenInventoryLog is saved or edited.
    - benchmark_quantity: optional minimum stock level set by admin.
      When set, is_below_benchmark flags low stock.
    """

    class Unit(models.TextChoices):
        KG = "kg", "Kilogram (kg)"
        GRAM = "g", "Gram (g)"
        LITER = "ltr", "Litre (ltr)"
        ML = "ml", "Millilitre (ml)"
        PIECE = "pcs", "Piece (pcs)"
        PACKET = "pkt", "Packet (pkt)"
        BOTTLE = "btl", "Bottle (btl)"
        BOX = "box", "Box (box)"

    name = models.CharField(max_length=150, unique=True, db_index=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KG)
    total_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text=(
            "Current quantity in stock. "
            "Automatically updated when daily logs are submitted."
        ),
    )
    benchmark_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=(
            "Optional. Minimum stock level set by admin. "
            "Used to flag when stock is running low."
        ),
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.unit})"

    @property
    def is_below_benchmark(self) -> bool:
        """True when total_quantity is below the benchmark (if one is set)."""
        if self.benchmark_quantity is None:
            return False
        return self.total_quantity < self.benchmark_quantity


class KitchenInventoryLog(BaseModel):
    """
    Daily record submitted by kitchen staff.

    Staff enter:
      - received_quantity : new stock added / restocked today  (+)
      - consumed_quantity : quantity used / consumed today      (-)

    On save, KitchenInventoryItem.total_quantity is updated atomically:
      total_quantity += received_quantity - consumed_quantity

    Edits are handled correctly: the old net impact is reversed before
    the new net impact is applied.
    """

    item = models.ForeignKey(
        "KitchenInventoryItem",
        on_delete=models.CASCADE,
        related_name="daily_logs",
        db_index=True,
    )
    date = models.DateField(default=timezone.localdate, db_index=True)

    received_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="New stock received / restocked today. Increases total stock.",
    )
    consumed_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Quantity used / consumed today. Decreases total stock.",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_logs",
        help_text="Kitchen staff who submitted this daily update.",
    )
    notes = models.TextField(
        blank=True, null=True, help_text="Optional remarks for the day."
    )

    class Meta:
        # Only one log per item per day
        unique_together = [("item", "date")]
        ordering = ["-date", "item__name"]
        indexes = [
            models.Index(fields=["date", "item"]),
            models.Index(fields=["item", "-date"]),
        ]

    def save(self, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            if self.pk:
                # --- Editing an existing log ---
                # Reverse the old net impact, then apply the new one.
                old = KitchenInventoryLog.objects.select_for_update().get(pk=self.pk)
                old_net = old.received_quantity - old.consumed_quantity
                new_net = self.received_quantity - self.consumed_quantity
                delta = new_net - old_net
            else:
                # --- New log ---
                delta = self.received_quantity - self.consumed_quantity

            super().save(*args, **kwargs)

            # Update total_quantity on the item using F() to avoid race conditions
            KitchenInventoryItem.objects.filter(pk=self.item_id).update(
                total_quantity=models.F("total_quantity") + delta
            )

    def __str__(self):
        return (
            f"{self.item.name} | {self.date} "
            f"| +{self.received_quantity} received "
            f"| -{self.consumed_quantity} consumed"
        )

    @property
    def net_change(self):
        """Positive = stock increased, Negative = stock decreased."""
        return self.received_quantity - self.consumed_quantity

    @property
    def is_below_benchmark(self) -> bool:
        """True when the item's total stock is below the benchmark on this log's date."""
        return self.item.is_below_benchmark
