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


def get_order_by_id_with_relations(order_id: int):
    """
    Optimized selector to retrieve a single order by ID with all related objects
    (branch, user, created_by, assigned rider, offers, promo code, items with products,
    extras, nps transactions, and status history) to prevent N+1 queries.
    """
    return (
        Order.objects
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
        .filter(id=order_id)
        .first()
    )


def get_order_by_number_with_relations(order_number: str):
    """
    Optimized selector to retrieve a single order by order_number with all related objects.
    """
    return (
        Order.objects
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
        .filter(order_number=order_number)
        .first()
    )
