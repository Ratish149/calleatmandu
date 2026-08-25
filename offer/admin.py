from django.contrib import admin
from unfold.admin import ModelAdmin

from offer.models import Offer, OfferRedemption, PromoCode


@admin.register(Offer)
class OfferAdmin(ModelAdmin):
    list_display = [
        "title",
        "offer_type",
        "scope",
        "discount_percentage",
        "discount_amount",
        "is_active",
        "start_datetime",
        "end_datetime",
        "created_at",
    ]
    list_filter = ["offer_type", "scope", "is_active", "created_at"]
    search_fields = ["title", "description"]
    filter_horizontal = ["products"]
    ordering = ["-created_at"]


@admin.register(PromoCode)
class PromoCodeAdmin(ModelAdmin):
    list_display = [
        "code",
        "promo_type",
        "amount",
        "max_total_usage",
        "max_usage_per_user",
        "current_usage_count",
        "is_active",
        "start_datetime",
        "end_datetime",
        "created_at",
    ]
    list_filter = ["promo_type", "is_active", "created_at"]
    search_fields = ["code", "description"]
    ordering = ["-created_at"]


@admin.register(OfferRedemption)
class OfferRedemptionAdmin(ModelAdmin):
    list_display = [
        "offer",
        "promo_code",
        "user",
        "order_id",
        "discount_applied",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["offer__title", "promo_code__code", "user__email", "order_id"]
    ordering = ["-created_at"]
