from typing import Optional

from rest_framework import serializers

from ..models import NPSConfig


def get_nps_config(
    raise_exception: bool = True,
) -> Optional[NPSConfig]:
    """
    Retrieves the active NPSConfig.

    If raise_exception=True:
    - Raises serializers.ValidationError if configuration is missing or inactive.

    If raise_exception=False:
    - Returns active NPSConfig or None.
    """
    config = NPSConfig.objects.first()

    if not config:
        if raise_exception:
            raise serializers.ValidationError("NPS payment system is not configured.")
        return None

    if not config.is_enabled:
        if raise_exception:
            raise serializers.ValidationError("NPS payment system is disabled.")
        return None

    return config

