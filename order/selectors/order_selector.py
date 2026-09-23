from django.db.models import Q

from account.models import User
from order.models import Order


def get_customer_orders_queryset(customer_id: int):
    """
    Optimized queryset to retrieve all orders for a specific customer.
    Pre-fetches branch, user, created_by, assigned rider, offers, promo code,
    items with products, extras, nps transactions, and status history.
    Also includes any unlinked guest orders matching the customer's registered phone number.
    """
    customer = User.objects.filter(id=customer_id).first()
    if not customer:
        return Order.objects.none()

    q = Q(user_id=customer_id)
    if (
        customer.phone_number
        and customer.phone_number.strip()
        and customer.phone_number.strip() != "N/A"
    ):
        q |= Q(user__isnull=True, phone_number=customer.phone_number.strip())

    return (
        Order.objects
        .filter(q)
        .select_related(
            "branch",
            "user",
            "created_by",
            "assigned_to_rider",
            "offer",
            "promo_code",
        )
        .prefetch_related(
            "items__product",
            "items__selected_extras",
            "nps_transactions",
            "status_history__changed_by",
        )
        .order_by("-created_at")
    )
