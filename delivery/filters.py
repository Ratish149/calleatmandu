import django_filters

from delivery.models import DeliveryPricing


class DeliveryPricingFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(field_name="is_active")
    min_price_per_km = django_filters.NumberFilter(
        field_name="price_per_km", lookup_expr="gte"
    )
    max_price_per_km = django_filters.NumberFilter(
        field_name="price_per_km", lookup_expr="lte"
    )
    min_minimum_charge = django_filters.NumberFilter(
        field_name="minimum_charge", lookup_expr="gte"
    )
    max_minimum_charge = django_filters.NumberFilter(
        field_name="minimum_charge", lookup_expr="lte"
    )

    class Meta:
        model = DeliveryPricing
        fields = [
            "is_active",
            "min_price_per_km",
            "max_price_per_km",
            "min_minimum_charge",
            "max_minimum_charge",
        ]
