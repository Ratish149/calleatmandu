from django_filters import rest_framework as filters

from offer.models import Offer, PromoCode


class OfferFilter(filters.FilterSet):
    title = filters.CharFilter(lookup_expr="icontains")
    offer_type = filters.ChoiceFilter(choices=Offer.OfferType.choices)
    scope = filters.ChoiceFilter(choices=Offer.ScopeType.choices)
    is_active = filters.BooleanFilter()
    category = filters.NumberFilter(field_name="category__id")
    subcategory = filters.NumberFilter(field_name="subcategory__id")
    min_order_amount_lte = filters.NumberFilter(
        field_name="min_order_amount", lookup_expr="lte"
    )

    class Meta:
        model = Offer
        fields = [
            "title",
            "offer_type",
            "scope",
            "is_active",
            "category",
            "subcategory",
            "min_order_amount_lte",
        ]


class PromoCodeFilter(filters.FilterSet):
    code = filters.CharFilter(lookup_expr="icontains")
    is_active = filters.BooleanFilter()
    offer = filters.NumberFilter(field_name="offer__id")

    class Meta:
        model = PromoCode
        fields = ["code", "is_active", "offer"]
