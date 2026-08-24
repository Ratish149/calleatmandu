from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from offer.models import Offer, OfferRedemption, PromoCode


class PromoCodeInline(TabularInline):
    model = PromoCode
    extra = 0


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
    inlines = [PromoCodeInline]
    ordering = ["-created_at"]


@admin.register(PromoCode)
class PromoCodeAdmin(ModelAdmin):
    list_display = [
        "code",
        "offer",
        "max_total_usage",
        "current_usage_count",
        "is_active",
        "start_datetime",
        "end_datetime",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["code", "offer__title", "description"]
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
