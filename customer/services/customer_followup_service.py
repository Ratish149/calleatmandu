import re
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model

from customer.models import CustomerFollowUp
from order.models import Order

User = get_user_model()


class CustomerFollowUpService:
    @staticmethod
    def clean_phone_number(raw_phone: Optional[str]) -> str:
        if not raw_phone:
            raise ValueError("Phone number is required.")
        raw_str = str(raw_phone).strip()
        digits = re.sub(r"\D", "", raw_str)

        if digits.startswith("977"):
            digits = digits[3:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]

        return digits if len(digits) == 10 else raw_str

    @classmethod
    def create_follow_up(
        cls,
        data: Dict[str, Any],
        created_by: Optional[Any] = None,
    ) -> CustomerFollowUp:
        """
        Creates a CustomerFollowUp record:
        - Cleans and normalizes phone number.
        - Automatically resolves customer name from past orders if not explicitly supplied.
        - Automatically resolves registered User account by matching phone number.
        - Associates with staff user and their assigned branch.
        """
        phone_number = cls.clean_phone_number(data.get("phone_number"))

        customer_name = data.get("customer_name")
        user = data.get("user")
        branch = data.get("branch")

        # 1. Resolve registered user by phone if not provided
        if not user:
            user = User.objects.filter(phone_number=phone_number).first()

        # 2. Resolve customer name if not provided
        if not customer_name:
            if user:
                customer_name = user.get_full_name() or user.username
            else:
                latest_order = (
                    Order.objects
                    .filter(phone_number=phone_number)
                    .order_by("-created_at")
                    .first()
                )
                if latest_order and latest_order.customer_name:
                    customer_name = latest_order.customer_name

        # 3. Default branch from staff if not provided
        if not branch and created_by and getattr(created_by, "branch_id", None):
            branch = created_by.branch

        followup = CustomerFollowUp.objects.create(
            phone_number=phone_number,
            customer_name=customer_name or "Valued Customer",
            user=user,
            notes=data.get("notes"),
            created_by=created_by,
            branch=branch,
        )
        return followup
