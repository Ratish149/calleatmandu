from typing import Any, Optional, Union

from rest_framework import serializers

from about.models import Franchise

from ..models import NPSConfig


def get_nps_config(
    franchise_identifier: Optional[Union[str, int, Franchise]] = None,
    order: Optional[Any] = None,
    raise_exception: bool = True,
) -> Optional[NPSConfig]:
    """
    Retrieves the NPSConfig strictly by franchise slug (or Franchise instance / order's franchise).

    If raise_exception=True:
    - Raises serializers.ValidationError if configuration for the given franchise slug is missing or inactive.

    If raise_exception=False:
    - Returns active NPSConfig or None.
    """
    franchise_obj = None

    if isinstance(franchise_identifier, Franchise):
        franchise_obj = franchise_identifier
    elif franchise_identifier:
        franchise_slug = str(franchise_identifier).strip()
        # Look up franchise by slug first
        franchise_obj = Franchise.objects.filter(slug=franchise_slug).first()
        if not franchise_obj and franchise_slug.isdigit():
            franchise_obj = Franchise.objects.filter(id=int(franchise_slug)).first()

    if not franchise_obj and order and getattr(order, "franchise", None):
        franchise_obj = order.franchise

    # Query NPSConfig specifically for this franchise (or default unassigned if no franchise)
    config = None
    if franchise_obj:
        config = (
            NPSConfig.objects
            .select_related("franchise")
            .filter(franchise=franchise_obj)
            .first()
        )

    if not config:
        config = (
            NPSConfig.objects
            .select_related("franchise")
            .filter(franchise__isnull=True)
            .first()
        )

    # Fallback to any active/available NPSConfig if no franchise-specific config was found
    if not config:
        config = NPSConfig.objects.select_related("franchise").first()

    if not config:
        if raise_exception:
            raise serializers.ValidationError("NPS payment system is not configured.")
        return None

    if not config.is_enabled:
        if raise_exception:
            raise serializers.ValidationError("NPS payment system is disabled.")
        return None

    return config
