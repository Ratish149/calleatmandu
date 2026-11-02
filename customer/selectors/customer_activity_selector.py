import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Min, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from order.models import Order

User = get_user_model()


class CustomerOrderActivitySelector:
    """
    Selector for extracting, aggregating, and classifying customer order activity
    directly from the Order table.

    Activity Criteria:
    - Default window: 7 days (or customizable via start_date and end_date / days).
    - Active: Customer who placed an order (or reordered) within the window.
    - Inactive: Customer who placed orders previously but did NOT order within the window.
    - Clean separation of registered customer accounts (User) and phone-based guest customers.
    """

    @staticmethod
    def clean_phone_number(raw_phone: Optional[str]) -> Optional[str]:
        if not raw_phone:
            return None
        raw_str = str(raw_phone).strip()
        if raw_str.upper() in ("N/A", "NONE", "NULL", ""):
            return None

        digits = re.sub(r"\D", "", raw_str)
        if digits.startswith("977"):
            digits = digits[3:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]

        return digits if len(digits) == 10 else raw_str

    @classmethod
    def parse_range_boundaries(
        cls,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        days: int = 7,
    ) -> tuple[datetime, datetime, int]:
        now = timezone.now()

        # Parse end date
        if end_date:
            if isinstance(end_date, str):
                parsed_dt = parse_datetime(end_date)
                if not parsed_dt:
                    pd = parse_date(end_date)
                    parsed_dt = (
                        datetime.combine(pd, time.max) if pd else None
                    )
            else:
                parsed_dt = end_date

            if parsed_dt:
                range_end = (
                    parsed_dt
                    if timezone.is_aware(parsed_dt)
                    else timezone.make_aware(parsed_dt)
                )
            else:
                range_end = now
        else:
            range_end = now

        # Parse start date
        if start_date:
            if isinstance(start_date, str):
                parsed_s_dt = parse_datetime(start_date)
                if not parsed_s_dt:
                    pds = parse_date(start_date)
                    parsed_s_dt = (
                        datetime.combine(pds, time.min) if pds else None
                    )
            else:
                parsed_s_dt = start_date

            if parsed_s_dt:
                range_start = (
                    parsed_s_dt
                    if timezone.is_aware(parsed_s_dt)
                    else timezone.make_aware(parsed_s_dt)
                )
            else:
                range_start = range_end - timedelta(days=days)
        else:
            range_start = range_end - timedelta(days=days)

        if start_date and end_date:
            calc_days = max(1, (range_end.date() - range_start.date()).days)
        else:
            calc_days = days

        return range_start, range_end, calc_days

    @classmethod
    def get_customer_order_activity(
        cls,
        days: int = 7,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
        customer_type: Optional[str] = None,
        search: Optional[str] = None,
        is_reorder: Optional[bool] = None,
        branch_id: Optional[int] = None,
        user: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves a comprehensive customer order activity report:
        - Evaluates order counts, last order date, reorder count, and active status.
        - Respects date range boundaries with 7-day default.
        - Unifies orders by customer account and phone number.
        """
        range_start, range_end, effective_days = cls.parse_range_boundaries(
            start_date=start_date, end_date=end_date, days=days
        )

        base_orders = Order.objects.exclude(status=Order.OrderStatus.CANCELLED)

        # Multi-branch staff scoping
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            base_orders = base_orders.filter(branch_id=user.branch_id)
        elif branch_id:
            base_orders = base_orders.filter(branch_id=branch_id)

        # -------------------------------------------------------------------
        # 1. Registered Customer Aggregations (Order.user is present)
        # -------------------------------------------------------------------
        registered_customers: List[Dict[str, Any]] = []
        user_phone_set = set()

        if customer_type in (None, "all", "registered"):
            u_orders = base_orders.filter(user__isnull=False)

            if search:
                clean_search = search.strip()
                u_orders = u_orders.filter(
                    Q(customer_name__icontains=clean_search)
                    | Q(phone_number__icontains=clean_search)
                    | Q(user__username__icontains=clean_search)
                    | Q(user__email__icontains=clean_search)
                    | Q(user__first_name__icontains=clean_search)
                    | Q(user__last_name__icontains=clean_search)
                )

            u_agg = u_orders.values("user_id").annotate(
                total_orders=Count("id"),
                orders_in_range=Count(
                    "id",
                    filter=Q(created_at__gte=range_start, created_at__lte=range_end),
                ),
                first_order_date=Min("created_at"),
                last_order_date=Max("created_at"),
                total_spent=Sum("total_amount"),
            )

            user_ids = [row["user_id"] for row in u_agg]
            users_map = {
                u.id: u
                for u in User.objects.filter(id__in=user_ids).only(
                    "id", "username", "email", "first_name", "last_name", "phone_number"
                )
            }

            for row in u_agg:
                uid = row["user_id"]
                u_instance = users_map.get(uid)

                # Fetch most recent order for latest customer details
                latest_order = (
                    u_orders.filter(user_id=uid).order_by("-created_at").first()
                )

                phone = None
                if latest_order and latest_order.phone_number:
                    phone = cls.clean_phone_number(latest_order.phone_number)
                if not phone and u_instance and u_instance.phone_number:
                    phone = cls.clean_phone_number(u_instance.phone_number)

                if phone:
                    user_phone_set.add(phone)

                name = None
                if latest_order and latest_order.customer_name:
                    name = latest_order.customer_name.strip()
                if not name and u_instance:
                    name = u_instance.get_full_name() or u_instance.username

                in_range = row["orders_in_range"]
                active_flag = in_range > 0
                total_orders = row["total_orders"]
                reorder_count = max(0, total_orders - 1)
                last_order_dt = row["last_order_date"]
                days_since = (
                    (timezone.now() - last_order_dt).days if last_order_dt else None
                )

                registered_customers.append(
                    {
                        "id": f"user-{uid}",
                        "customer_id": uid,
                        "customer_name": name or "Registered User",
                        "phone_number": phone,
                        "email": getattr(u_instance, "email", None),
                        "username": getattr(u_instance, "username", None),
                        "customer_type": "registered",
                        "total_orders": total_orders,
                        "orders_in_range": in_range,
                        "reorder_count": reorder_count,
                        "is_reorder": total_orders > 1,
                        "first_order_date": row["first_order_date"],
                        "last_order_date": last_order_dt,
                        "days_since_last_order": days_since,
                        "total_spent": round(row["total_spent"] or 0.0, 2),
                        "is_active": active_flag,
                        "status": "active" if active_flag else "inactive",
                    }
                )

        # -------------------------------------------------------------------
        # 2. Guest / Phone-based Customer Aggregations (Order.user is null)
        # -------------------------------------------------------------------
        guest_customers: List[Dict[str, Any]] = []

        if customer_type in (None, "all", "guest"):
            g_orders = (
                base_orders.filter(user__isnull=True)
                .exclude(phone_number__isnull=True)
                .exclude(phone_number__in=["", "N/A", "None", "null", "NULL"])
            )

            if search:
                clean_search = search.strip()
                g_orders = g_orders.filter(
                    Q(customer_name__icontains=clean_search)
                    | Q(phone_number__icontains=clean_search)
                )

            g_agg = g_orders.values("phone_number").annotate(
                total_orders=Count("id"),
                orders_in_range=Count(
                    "id",
                    filter=Q(created_at__gte=range_start, created_at__lte=range_end),
                ),
                first_order_date=Min("created_at"),
                last_order_date=Max("created_at"),
                total_spent=Sum("total_amount"),
            )

            for row in g_agg:
                raw_phone = row["phone_number"]
                cleaned_phone = cls.clean_phone_number(raw_phone)

                # Skip if already unified under registered user with same phone
                if cleaned_phone and cleaned_phone in user_phone_set:
                    continue

                latest_order = (
                    g_orders.filter(phone_number=raw_phone)
                    .order_by("-created_at")
                    .first()
                )
                name = (
                    latest_order.customer_name.strip()
                    if (latest_order and latest_order.customer_name)
                    else "Guest Customer"
                )

                in_range = row["orders_in_range"]
                active_flag = in_range > 0
                total_orders = row["total_orders"]
                reorder_count = max(0, total_orders - 1)
                last_order_dt = row["last_order_date"]
                days_since = (
                    (timezone.now() - last_order_dt).days if last_order_dt else None
                )

                guest_customers.append(
                    {
                        "id": f"guest-{cleaned_phone or raw_phone}",
                        "customer_id": None,
                        "customer_name": name,
                        "phone_number": cleaned_phone or raw_phone,
                        "email": None,
                        "username": None,
                        "customer_type": "guest",
                        "total_orders": total_orders,
                        "orders_in_range": in_range,
                        "reorder_count": reorder_count,
                        "is_reorder": total_orders > 1,
                        "first_order_date": row["first_order_date"],
                        "last_order_date": last_order_dt,
                        "days_since_last_order": days_since,
                        "total_spent": round(row["total_spent"] or 0.0, 2),
                        "is_active": active_flag,
                        "status": "active" if active_flag else "inactive",
                    }
                )

        combined_customers = registered_customers + guest_customers

        # Summary calculations prior to status-specific filtering
        summary = {
            "total_customers": len(combined_customers),
            "active_customers": sum(1 for c in combined_customers if c["is_active"]),
            "inactive_customers": sum(
                1 for c in combined_customers if not c["is_active"]
            ),
            "registered_customers": len(registered_customers),
            "guest_customers": len(guest_customers),
            "window_days": effective_days,
            "start_date": range_start.isoformat(),
            "end_date": range_end.isoformat(),
        }

        # Status & Activity filter
        filtered_customers = combined_customers
        if is_active is not None:
            filtered_customers = [
                c for c in filtered_customers if c["is_active"] == is_active
            ]
        elif status:
            st = str(status).strip().lower()
            if st in ("active", "true", "1", "yes"):
                filtered_customers = [
                    c for c in filtered_customers if c["is_active"]
                ]
            elif st in ("inactive", "false", "0", "no"):
                filtered_customers = [
                    c for c in filtered_customers if not c["is_active"]
                ]

        # Reorder filter
        if is_reorder is not None:
            filtered_customers = [
                c for c in filtered_customers if c["is_reorder"] == is_reorder
            ]

        # Sort: Active customers first, then by latest order date descending
        filtered_customers.sort(
            key=lambda c: (
                c["is_active"],
                c["last_order_date"] or timezone.now(),
            ),
            reverse=True,
        )

        return {
            "summary": summary,
            "customers": filtered_customers,
        }
