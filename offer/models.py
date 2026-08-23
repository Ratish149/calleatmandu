from django.conf import settings
from django.db import models

from common.models import BaseModel


class PromoCode(BaseModel):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    offer = models.ForeignKey(
        "Offer",
        on_delete=models.CASCADE,
        related_name="promo_codes",
        help_text="The offer linked to this promo code.",
    )
    max_total_usage = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum times this promo code can be used in total",
    )
    max_usage_per_user = models.PositiveIntegerField(
        default=1, help_text="Maximum times a single user can use this promo code"
    )
    current_usage_count = models.PositiveIntegerField(default=0)
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["code", "is_active"]),
            models.Index(fields=["is_active", "start_datetime", "end_datetime"]),
        ]

    def __str__(self):
        return f"{self.code} -> {self.offer.title}"


class Offer(BaseModel):
    class OfferType(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Percentage Discount"
        FLAT = "FLAT", "Flat Amount Discount"
        BUY_X_GET_Y = "BUY_X_GET_Y", "Buy X Get Y (BOGO)"
        FREE_DELIVERY = "FREE_DELIVERY", "Free Delivery"
        COMBO = "COMBO", "Combo Deal"

    class ScopeType(models.TextChoices):
        CART = "CART", "Entire Cart / Order"
        CATEGORY = "CATEGORY", "Specific Category"
        SUBCATEGORY = "SUBCATEGORY", "Specific Subcategory"
        PRODUCT = "PRODUCT", "Specific Product(s)"

    # Basic Info
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    banner_image = models.FileField(upload_to="offers/banners/", blank=True, null=True)

    # Core Offer Type & Scope
    offer_type = models.CharField(
        max_length=30, choices=OfferType.choices, db_index=True
    )
    scope = models.CharField(
        max_length=30, choices=ScopeType.choices, default=ScopeType.CART, db_index=True
    )

    # Scoped Targets
    category = models.ForeignKey(
        "product.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offers",
    )
    subcategory = models.ForeignKey(
        "product.Subcategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offers",
    )
    products = models.ManyToManyField(
        "product.Product",
        blank=True,
        related_name="offers",
        help_text="Products targeted by this offer.",
    )

    # Discount Mechanics
    discount_percentage = models.FloatField(
        default=0.0, help_text="Used when offer_type is PERCENTAGE"
    )
    discount_amount = models.FloatField(
        default=0.0, help_text="Used when offer_type is FLAT"
    )
    max_discount_amount = models.FloatField(
        null=True,
        blank=True,
        help_text="Cap maximum discount amount for percentage offers",
    )

    # Buy X Get Y Mechanics
    buy_product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buy_x_offers",
        help_text="Required product to buy for Buy X Get Y",
    )
    buy_quantity = models.PositiveIntegerField(default=1)
    get_product = models.ForeignKey(
        "product.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="get_y_offers",
        help_text="Product given as reward/discounted item",
    )
    get_quantity = models.PositiveIntegerField(default=1)
    get_discount_percentage = models.FloatField(
        default=100.0, help_text="100% means free item, 50% means half price"
    )

    # Order Eligibility & Constraints
    min_order_amount = models.FloatField(
        default=0.0, help_text="Minimum order total required to apply offer"
    )
    min_item_quantity = models.PositiveIntegerField(
        default=1, help_text="Minimum quantity of targeted item in cart"
    )

    # Usage & Limits (for auto-applied offers without a promo code)
    max_total_usage = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total overall uses available for auto-applied offer",
    )
    max_usage_per_user = models.PositiveIntegerField(
        default=1, help_text="Max times a single user can redeem auto-applied offer"
    )
    current_usage_count = models.PositiveIntegerField(default=0)

    # Time Schedule / Happy Hours
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    start_time = models.TimeField(
        null=True, blank=True, help_text="Happy hour start time (e.g. 12:00:00)"
    )
    end_time = models.TimeField(
        null=True, blank=True, help_text="Happy hour end time (e.g. 15:00:00)"
    )

    # Status
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "start_datetime", "end_datetime"]),
            models.Index(fields=["offer_type", "scope", "is_active"]),
        ]

    def __str__(self):
        return f"{self.title} [{self.offer_type}]"


class OfferRedemption(BaseModel):
    offer = models.ForeignKey(
        "Offer", on_delete=models.CASCADE, related_name="redemptions"
    )
    promo_code = models.ForeignKey(
        "PromoCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redemptions",
        help_text="The specific promo code redeemed, if applicable.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="offer_redemptions",
    )
    order_id = models.CharField(max_length=100, null=True, blank=True)
    discount_applied = models.FloatField(default=0.0)

    class Meta:
        indexes = [
            models.Index(fields=["offer", "user"]),
            models.Index(fields=["promo_code", "user"]),
        ]

    def __str__(self):
        return f"{self.user} redeemed {self.offer.title}"
