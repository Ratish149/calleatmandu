from django.utils import timezone

from offer.models import Offer, OfferRedemption, PromoCode


class OfferService:
    @staticmethod
    def is_offer_time_valid(offer, now=None):
        if now is None:
            now = timezone.now()

        # Check date range
        if offer.start_datetime and now < offer.start_datetime:
            return False, "Offer has not started yet."
        if offer.end_datetime and now > offer.end_datetime:
            return False, "Offer has expired."

        # Check happy hour time slot
        if offer.start_time and offer.end_time:
            current_time = now.time()
            if not (offer.start_time <= current_time <= offer.end_time):
                return False, f"Offer is only valid between {offer.start_time} and {offer.end_time}."

        return True, None

    @staticmethod
    def is_promo_code_valid(promo_code, user=None, now=None):
        if not promo_code.is_active:
            return False, "Promo code is inactive."

        if now is None:
            now = timezone.now()

        if promo_code.start_datetime and now < promo_code.start_datetime:
            return False, "Promo code is not active yet."
        if promo_code.end_datetime and now > promo_code.end_datetime:
            return False, "Promo code has expired."

        if promo_code.max_total_usage and promo_code.current_usage_count >= promo_code.max_total_usage:
            return False, "Promo code maximum usage limit reached."

        if user and user.is_authenticated:
            user_redemptions = OfferRedemption.objects.filter(
                promo_code=promo_code, user=user
            ).count()
            if user_redemptions >= promo_code.max_usage_per_user:
                return False, f"You have already reached the max usage limit ({promo_code.max_usage_per_user}) for this promo code."

        return True, None

    @classmethod
    def evaluate_cart_offer(cls, cart_items, cart_total, promo_code_str=None, user=None):
        """
        cart_items format:
        [
            {"product_id": 1, "category_id": 2, "subcategory_id": 5, "price": 250.0, "quantity": 2},
            ...
        ]
        """
        now = timezone.now()
        promo_code_obj = None

        if promo_code_str:
            try:
                promo_code_obj = PromoCode.objects.select_related("offer").get(
                    code__iexact=promo_code_str
                )
            except PromoCode.DoesNotExist:
                return {
                    "is_valid": False,
                    "message": "Invalid promo code.",
                    "discount_amount": 0.0,
                    "final_amount": cart_total,
                }

            is_code_valid, err_msg = cls.is_promo_code_valid(promo_code_obj, user=user, now=now)
            if not is_code_valid:
                return {
                    "is_valid": False,
                    "message": err_msg,
                    "discount_amount": 0.0,
                    "final_amount": cart_total,
                }

            offer = promo_code_obj.offer
        else:
            # Look for active auto-applied offer
            offer = Offer.objects.filter(
                is_active=True
            ).order_by("-discount_percentage", "-discount_amount").first()

            if not offer:
                return {
                    "is_valid": False,
                    "message": "No active offer available.",
                    "discount_amount": 0.0,
                    "final_amount": cart_total,
                }

        if not offer.is_active:
            return {
                "is_valid": False,
                "message": "Offer is currently inactive.",
                "discount_amount": 0.0,
                "final_amount": cart_total,
            }

        is_time_ok, time_err = cls.is_offer_time_valid(offer, now=now)
        if not is_time_ok:
            return {
                "is_valid": False,
                "message": time_err,
                "discount_amount": 0.0,
                "final_amount": cart_total,
            }

        # Check minimum order amount constraint
        if cart_total < offer.min_order_amount:
            return {
                "is_valid": False,
                "message": f"Minimum order total of Rs. {offer.min_order_amount} required to use this offer.",
                "discount_amount": 0.0,
                "final_amount": cart_total,
            }

        # Calculate discount based on offer_type and scope
        discount_amount = 0.0
        reward_details = {}

        if offer.offer_type == Offer.OfferType.PERCENTAGE:
            discount_amount = (cart_total * offer.discount_percentage) / 100.0
            if offer.max_discount_amount and discount_amount > offer.max_discount_amount:
                discount_amount = offer.max_discount_amount

        elif offer.offer_type == Offer.OfferType.FLAT:
            discount_amount = min(offer.discount_amount, cart_total)

        elif offer.offer_type == Offer.OfferType.FREE_DELIVERY:
            discount_amount = 0.0
            reward_details["free_delivery"] = True

        elif offer.offer_type == Offer.OfferType.BUY_X_GET_Y:
            # Check if required buy_product exists in cart with buy_quantity
            buy_item = next(
                (item for item in cart_items if item.get("product_id") == offer.buy_product_id),
                None
            )
            if not buy_item or buy_item.get("quantity", 0) < offer.buy_quantity:
                return {
                    "is_valid": False,
                    "message": f"Buy at least {offer.buy_quantity} of {offer.buy_product.name if offer.buy_product else 'required item'} to claim this offer.",
                    "discount_amount": 0.0,
                    "final_amount": cart_total,
                }

            get_product_name = offer.get_product.name if offer.get_product else "reward item"
            reward_details["bogo"] = {
                "get_product_id": offer.get_product_id,
                "get_product_name": get_product_name,
                "get_quantity": offer.get_quantity,
                "discount_percentage": offer.get_discount_percentage,
            }

        final_amount = max(0.0, cart_total - discount_amount)

        return {
            "is_valid": True,
            "message": "Offer applied successfully.",
            "offer_id": offer.id,
            "offer_title": offer.title,
            "promo_code": promo_code_obj.code if promo_code_obj else None,
            "discount_amount": round(discount_amount, 2),
            "final_amount": round(final_amount, 2),
            "reward_details": reward_details,
        }
