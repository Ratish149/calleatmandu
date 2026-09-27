class RoutingError(Exception):
    """Raised when road distance routing via OSRM fails or no path is available."""

    pass


class DeliveryPricingError(Exception):
    """Raised when active delivery pricing configuration is missing."""

    pass


class DeliveryDistanceExceededError(Exception):
    """Raised when customer is outside the branch's maximum delivery coverage."""

    pass


class BranchNotFoundError(Exception):
    """Raised when no active branch is available to fulfill delivery."""

    pass
