from django.db.models import QuerySet

from delivery.models import DeliveryPricing


def get_delivery_pricing() -> DeliveryPricing:
    """
    Returns the singleton DeliveryPricing instance.
    """
    return DeliveryPricing.get_instance()


def get_active_delivery_pricing() -> DeliveryPricing | None:
    """
    Fetches the active singleton DeliveryPricing configuration.
    Returns None if delivery pricing is currently inactive.
    """
    pricing = get_delivery_pricing()
    return pricing if pricing.is_active else None


def get_delivery_pricing_queryset() -> QuerySet[DeliveryPricing]:
    """
    Returns queryset containing the singleton DeliveryPricing instance.
    """
    return DeliveryPricing.objects.filter(pk=1)
