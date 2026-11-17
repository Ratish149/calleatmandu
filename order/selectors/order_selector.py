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


def get_orders_for_user_queryset(user, status_filter=None):
    """
    Optimized selector to retrieve orders tailored to the authenticated user's role and branch scope.

    Role-based scoping rules:
    - If user is a rider:
      - If requesting status READY_FOR_PICKUP: returns all READY_FOR_PICKUP orders of the rider's branch
        (so the rider can see available orders and self-assign).
        If the rider has no assigned branch, returns all READY_FOR_PICKUP orders.
      - Without any status filter, or with filters like OUT_FOR_DELIVERY, DELIVERED, etc.:
        returns only their own assigned orders (assigned_to_rider=user).
    - If user has an assigned branch (user.branch_id):
      - If user is admin (or superuser): returns orders belonging to user.branch PLUS any orders linked to that admin (created_by or user).
      - If user is customer: returns only orders placed by this user.
      - If user is operational branch staff (kitchen, reception, etc.): returns orders belonging to user.branch.
    - If user does not have an assigned branch:
      - If user is superuser: returns all orders.
      - If user is admin: returns orders linked to that admin (created_by or user).
      - If user is customer / other: returns only orders placed by this user.
    - If unauthenticated: returns empty queryset.
    """
    base_queryset = (
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
        .order_by("-created_at")
    )

    if not (user and user.is_authenticated):
        return base_queryset.none()

    is_admin = user.is_superuser or getattr(user, "role", None) == "admin"
    user_role = getattr(user, "role", None)
    branch_id = getattr(user, "branch_id", None)

    # ── Rider-specific scoping ────────────────────────────────────────────────
    if user_role == "rider":
        is_ready_for_pickup = False
        if status_filter:
            cleaned_status = str(status_filter).strip().upper()
            is_ready_for_pickup = cleaned_status == Order.OrderStatus.READY_FOR_PICKUP

        if is_ready_for_pickup:
            if branch_id:
                return base_queryset.filter(
                    branch_id=branch_id,
                    status=Order.OrderStatus.READY_FOR_PICKUP,
                )
            return base_queryset.filter(status=Order.OrderStatus.READY_FOR_PICKUP)

        return base_queryset.filter(assigned_to_rider=user)

    # ── Scoping for other roles with an assigned branch ───────────────────────
    if branch_id:
        if is_admin:
            return base_queryset.filter(
                Q(branch_id=branch_id) | Q(created_by=user) | Q(user=user)
            )
        if user_role == "customer":
            return base_queryset.filter(user=user)
        return base_queryset.filter(branch_id=branch_id)

    # ── Scoping for users without an assigned branch ──────────────────────────
    if user.is_superuser:
        return base_queryset

    if is_admin:
        return base_queryset.filter(Q(created_by=user) | Q(user=user))

    return base_queryset.filter(user=user)
