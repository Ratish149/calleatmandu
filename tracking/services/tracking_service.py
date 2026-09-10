import logging
import math
from typing import Tuple

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from account.models import User
from tracking.models import RiderLocation, RiderLocationHistory
from tracking.selectors.tracking_selector import get_active_orders_for_rider

logger = logging.getLogger(__name__)

# Threshold for ignoring mobile GPS micro-jitter (0.00005 degrees ~ 5.5 meters)
GPS_JITTER_THRESHOLD = 0.00005


def update_rider_location(
    rider: User,
    latitude: float,
    longitude: float,
    save_history: bool = True,
) -> Tuple[RiderLocation, bool]:
    """
    Updates or creates a RiderLocation record and broadcasts the live GPS update
    via Django Channels to the Admin group and active Customer order groups.
    """
    location, created = RiderLocation.objects.get_or_create(
        rider=rider,
        defaults={
            "latitude": latitude,
            "longitude": longitude,
            "is_online": True,
        },
    )

    if not created:
        location.latitude = latitude
        location.longitude = longitude
        location.save(update_fields=["latitude", "longitude", "last_updated_at"])

    # Create historical breadcrumb record for route audit if location has changed significantly
    if save_history:
        recent_history = (
            RiderLocationHistory.objects
            .filter(rider=rider)
            .only("latitude", "longitude")
            .first()
        )
        is_same_location = (
            recent_history is not None
            and math.isclose(
                recent_history.latitude, latitude, abs_tol=GPS_JITTER_THRESHOLD
            )
            and math.isclose(
                recent_history.longitude, longitude, abs_tol=GPS_JITTER_THRESHOLD
            )
        )
        if not is_same_location:
            RiderLocationHistory.objects.create(
                rider=rider,
                latitude=latitude,
                longitude=longitude,
            )

    # Broadcast real-time location to WebSocket channel groups
    _broadcast_rider_location_update(location, rider)

    return location, created


def toggle_rider_online_status(rider: User, is_online: bool) -> RiderLocation:
    """
    Toggles rider online/offline availability and broadcasts the status update to admin consumers.
    """
    location, _ = RiderLocation.objects.get_or_create(
        rider=rider,
        defaults={
            "latitude": 0.0,
            "longitude": 0.0,
            "is_online": is_online,
        },
    )
    location.is_online = is_online
    location.save(update_fields=["is_online", "last_updated_at"])

    # Broadcast status change to admin group
    channel_layer = get_channel_layer()
    if channel_layer:
        rider_name = f"{rider.first_name} {rider.last_name}".strip() or rider.username
        async_to_sync(channel_layer.group_send)(
            "admin_rider_tracking",
            {
                "type": "rider_status_changed",
                "data": {
                    "rider_id": rider.id,
                    "rider_name": rider_name,
                    "phone_number": getattr(rider, "phone_number", ""),
                    "is_online": is_online,
                    "last_updated_at": location.last_updated_at.isoformat(),
                },
            },
        )

    return location


def _broadcast_rider_location_update(location: RiderLocation, rider: User) -> None:
    """
    Internal helper to send location update events over channel layers.
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    rider_name = f"{rider.first_name} {rider.last_name}".strip() or rider.username
    payload = {
        "rider_id": rider.id,
        "rider_name": rider_name,
        "phone_number": getattr(rider, "phone_number", ""),
        "branch_id": getattr(rider, "branch_id", None),
        "latitude": location.latitude,
        "longitude": location.longitude,
        "is_online": location.is_online,
        "last_updated_at": location.last_updated_at.isoformat(),
    }

    # 1. Send update to Admin tracking room
    try:
        async_to_sync(channel_layer.group_send)(
            "admin_rider_tracking",
            {
                "type": "rider_location_updated",
                "data": payload,
            },
        )
    except Exception as e:
        logger.error(f"Error broadcasting rider location to admin stream: {e}")

    # 2. Send update to active Customer order tracking rooms
    try:
        active_orders = get_active_orders_for_rider(rider.id)
        for order in active_orders:
            async_to_sync(channel_layer.group_send)(
                f"order_tracking_{order.order_number}",
                {
                    "type": "rider_location_updated",
                    "data": {
                        "order_number": order.order_number,
                        "order_status": order.status,
                        "rider_id": rider.id,
                        "rider_name": rider_name,
                        "phone_number": getattr(rider, "phone_number", ""),
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "last_updated_at": location.last_updated_at.isoformat(),
                    },
                },
            )
    except Exception as e:
        logger.error(f"Error broadcasting rider location to customer stream: {e}")
