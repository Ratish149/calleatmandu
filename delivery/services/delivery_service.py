import math
from decimal import Decimal

import requests

from account.models import Branch
from delivery.constants import (
    ESTIMATED_CITY_SPEED_KMH,
    FALLBACK_ROAD_FACTOR,
    OSRM_TIMEOUT_SECONDS,
    OSRM_URL,
)
from delivery.exceptions import (
    BranchNotFoundError,
    DeliveryPricingError,
    RoutingError,
)
from delivery.selectors.pricing_selector import get_active_delivery_pricing
from order.services.branch_service import BranchAssignmentService


def get_road_distance(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
) -> dict:
    """
    Returns actual road distance (km) and estimated duration (minutes) via OSRM.
    """
    # IMPORTANT: OSRM expects longitude,latitude format
    coordinates = f"{origin_lng},{origin_lat};{destination_lng},{destination_lat}"

    url = f"{OSRM_URL}/{coordinates}"
    params = {"overview": "false"}

    try:
        response = requests.get(
            url,
            params=params,
            timeout=OSRM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RoutingError("Unable to calculate delivery route.") from exc

    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(
            "No route could be found between the restaurant and address."
        )

    route = data["routes"][0]
    distance_meters = route["distance"]
    duration_seconds = route["duration"]

    distance_km = distance_meters / 1000.0
    duration_minutes = duration_seconds / 60.0

    return {
        "distance_km": distance_km,
        "duration_minutes": duration_minutes,
    }


def calculate_delivery_charge(distance_km: float, pricing=None) -> Decimal:
    """
    Calculates delivery charge based on ceil(distance_km) * price_per_km,
    constrained by minimum_charge.
    """
    if pricing is None:
        pricing = get_active_delivery_pricing()

    if not pricing:
        raise DeliveryPricingError("Delivery pricing is not configured.")

    kilometers = math.ceil(distance_km)
    charge = Decimal(kilometers) * pricing.price_per_km

    return max(charge, pricing.minimum_charge)


class DeliveryService:
    @staticmethod
    def get_road_distance(
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
    ) -> dict:
        return get_road_distance(
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            destination_lat=destination_lat,
            destination_lng=destination_lng,
        )

    @staticmethod
    def calculate_delivery_charge(distance_km: float, pricing=None) -> Decimal:
        return calculate_delivery_charge(distance_km=distance_km, pricing=pricing)

    @classmethod
    def estimate_delivery(
        cls,
        destination_lat: float,
        destination_lng: float,
        branch_id: int | None = None,
        allow_fallback: bool = True,
    ) -> dict:
        """
        Calculates road distance, estimated duration, delivery fee, and deliverability
        between branch and customer destination coordinates.
        """
        # 1. Resolve fulfilling branch
        if branch_id:
            branch = Branch.objects.filter(id=branch_id).first()
        else:
            branch = BranchAssignmentService.get_nearest_active_branch(
                destination_lat, destination_lng
            )

        if not branch:
            raise BranchNotFoundError(
                "No active branch is available to fulfill this delivery."
            )

        # 2. Compute road distance with fallback resilience
        routing_method = "road_network"
        try:
            route_info = get_road_distance(
                origin_lat=branch.latitude,
                origin_lng=branch.longitude,
                destination_lat=destination_lat,
                destination_lng=destination_lng,
            )
            distance_km = route_info["distance_km"]
            duration_minutes = route_info["duration_minutes"]
        except RoutingError as exc:
            if not allow_fallback:
                raise exc

            # Resilient fallback using Haversine calculation * road tortuosity factor
            straight_line_km = BranchAssignmentService.calculate_haversine_distance(
                branch.latitude, branch.longitude, destination_lat, destination_lng
            )
            distance_km = straight_line_km * FALLBACK_ROAD_FACTOR
            duration_minutes = (distance_km / ESTIMATED_CITY_SPEED_KMH) * 60.0
            routing_method = "estimated_fallback"

        # 3. Check branch maximum delivery distance limit
        is_deliverable = True
        message = "Delivery available."
        max_dist = (
            float(branch.maximum_delivery_distance_km)
            if branch.maximum_delivery_distance_km
            else None
        )

        if max_dist and distance_km > max_dist:
            is_deliverable = False
            message = f"Delivery address is outside branch coverage range ({max_dist:.1f} km)."

        # 4. Calculate delivery fee
        delivery_charge = calculate_delivery_charge(distance_km=distance_km)

        return {
            "branch_id": branch.id,
            "branch_name": branch.name,
            "branch_address": branch.address,
            "branch_latitude": branch.latitude,
            "branch_longitude": branch.longitude,
            "distance_km": round(distance_km, 2),
            "duration_minutes": round(duration_minutes, 1),
            "delivery_charge": delivery_charge.quantize(Decimal("0.01")),
            "is_deliverable": is_deliverable,
            "routing_method": routing_method,
            "message": message,
        }
