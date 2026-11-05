from typing import Literal

from django.db.models import Q

from order.models import Order

# Number of prepaid orders placed AFTER the last cancellation
# that are needed to flip a RED flag back to GREEN.
PREPAID_REDEMPTION_THRESHOLD = 3


FlagType = Literal["GREEN", "RED"]


def get_customer_flag(phone_number: str) -> dict:
    """
    Evaluates a customer's order history by phone number and returns a
    trust flag (GREEN / RED) with a human-readable reason.

    Rules (applied in order):
      1. No orders at all           → GREEN  (new customer, no risk)
      2. No cancellations           → GREEN  (clean record)
      3. Has 1+ cancellations       → RED
         Exception: if the customer placed >= PREPAID_REDEMPTION_THRESHOLD
         prepaid orders AFTER their last cancellation → GREEN (redeemed trust)

    Returns:
        {
            "flag": "GREEN" | "RED",
            "reason": str,
            "total_orders": int,
            "delivered_orders": int,
            "cancelled_orders": int,
            "prepaid_orders_after_last_cancellation": int,
        }
    """
    orders = (
        Order.objects.filter(phone_number=phone_number)
        .only("id", "status", "is_prepaid", "created_at")
        .order_by("created_at")
    )

    total_orders = orders.count()

    if total_orders == 0:
        return _build_result(
            flag="GREEN",
            reason="New customer — no order history.",
            total_orders=0,
            delivered=0,
            cancelled=0,
            prepaid_after_cancel=0,
        )

    cancelled_orders = orders.filter(status=Order.OrderStatus.CANCELLED)
    cancelled_count = cancelled_orders.count()
    delivered_count = orders.filter(status=Order.OrderStatus.DELIVERED).count()

    if cancelled_count == 0:
        return _build_result(
            flag="GREEN",
            reason="Clean record — no cancellations.",
            total_orders=total_orders,
            delivered=delivered_count,
            cancelled=0,
            prepaid_after_cancel=0,
        )

    # Customer has at least one cancellation — check for prepaid redemption.
    last_cancellation = cancelled_orders.order_by("-created_at").values("created_at").first()
    last_cancel_at = last_cancellation["created_at"]

    prepaid_after_cancel = orders.filter(
        created_at__gt=last_cancel_at,
        is_prepaid=True,
    ).count()

    if prepaid_after_cancel >= PREPAID_REDEMPTION_THRESHOLD:
        return _build_result(
            flag="GREEN",
            reason=(
                f"Trust redeemed — {prepaid_after_cancel} prepaid order(s) placed "
                f"after last cancellation (threshold: {PREPAID_REDEMPTION_THRESHOLD})."
            ),
            total_orders=total_orders,
            delivered=delivered_count,
            cancelled=cancelled_count,
            prepaid_after_cancel=prepaid_after_cancel,
        )

    return _build_result(
        flag="RED",
        reason=(
            f"Has {cancelled_count} cancellation(s). "
            f"Only {prepaid_after_cancel} prepaid order(s) placed after last cancellation "
            f"(need {PREPAID_REDEMPTION_THRESHOLD} to redeem)."
        ),
        total_orders=total_orders,
        delivered=delivered_count,
        cancelled=cancelled_count,
        prepaid_after_cancel=prepaid_after_cancel,
    )


def _build_result(
    flag: FlagType,
    reason: str,
    total_orders: int,
    delivered: int,
    cancelled: int,
    prepaid_after_cancel: int,
) -> dict:
    return {
        "flag": flag,
        "reason": reason,
        "total_orders": total_orders,
        "delivered_orders": delivered,
        "cancelled_orders": cancelled,
        "prepaid_orders_after_last_cancellation": prepaid_after_cancel,
    }
