from typing import Optional

from django.db.models import QuerySet

from order.models import Order
from tracking.models import RiderLocation


def get_active_riders_locations_qs() -> QuerySet[RiderLocation]:
    """
    Returns an optimized QuerySet of all rider locations, selecting
    related user details and assigned branch information to avoid N+1 queries.
    Strictly filters for users with role='rider'.
    """
    return (
        RiderLocation.objects.select_related(
            "rider",
            "rider__branch",
        )
        .filter(rider__role="rider")
        .only(
            "id",
            "latitude",
            "longitude",
            "is_online",
            "last_updated_at",
            "rider__id",
            "rider__username",
            "rider__first_name",
            "rider__last_name",
            "rider__phone_number",
            "rider__role",
            "rider__branch__id",
            "rider__branch__name",
        )
        .order_by("-last_updated_at")
    )


def get_rider_location_by_user(rider_user_id: int) -> Optional[RiderLocation]:
    """
    Retrieves the RiderLocation instance for a given rider user ID.
    Strictly filters for users with role='rider'.
    """
    return (
        RiderLocation.objects.select_related("rider", "rider__branch")
        .only(
            "id",
            "latitude",
            "longitude",
            "is_online",
            "last_updated_at",
            "rider__id",
            "rider__username",
            "rider__first_name",
            "rider__last_name",
            "rider__phone_number",
            "rider__role",
            "rider__branch__id",
            "rider__branch__name",
        )
        .filter(rider_id=rider_user_id, rider__role="rider")
        .first()
    )


def get_customer_order_tracking(order_number: str) -> Optional[Order]:
    """
    Retrieves the Order with related assigned rider, rider location, and branch data
    required for customer real-time tracking.
    """
    return (
        Order.objects.select_related(
            "assigned_to_rider",
            "assigned_to_rider__location",
            "branch",
        )
        .only(
            "id",
            "order_number",
            "customer_name",
            "phone_number",
            "delivery_location",
            "latitude",
            "longitude",
            "status",
            "created_at",
            "assigned_to_rider__id",
            "assigned_to_rider__username",
            "assigned_to_rider__first_name",
            "assigned_to_rider__last_name",
            "assigned_to_rider__phone_number",
            "assigned_to_rider__location__latitude",
            "assigned_to_rider__location__longitude",
            "assigned_to_rider__location__is_online",
            "assigned_to_rider__location__last_updated_at",
            "branch__id",
            "branch__name",
            "branch__latitude",
            "branch__longitude",
        )
        .filter(order_number=order_number)
        .first()
    )


def get_active_orders_for_rider(rider_user_id: int) -> QuerySet[Order]:
    """
    Returns all active (non-delivered, non-cancelled) orders assigned to a rider.
    """
    return (
        Order.objects.filter(assigned_to_rider_id=rider_user_id)
        .exclude(status__in=[Order.OrderStatus.DELIVERED, Order.OrderStatus.CANCELLED])
        .only("id", "order_number", "status", "latitude", "longitude")
    )
