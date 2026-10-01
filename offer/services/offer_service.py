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
                return (
                    False,
                    f"Offer is only valid between {offer.start_time} and {offer.end_time}.",
                )

        return True, None

    @classmethod
    def _enrich_cart_items_categories(cls, cart_items):
        """
        Ensures all cart items have 'category_id' and 'subcategory_id' populated
        by querying Product if missing.
        """
        if not cart_items:
            return cart_items

        missing_product_ids = [
            item["product_id"]
            for item in cart_items
            if item.get("product_id") and not item.get("category_id")
        ]

        if missing_product_ids:
            from product.models import Product

            products = Product.objects.filter(id__in=missing_product_ids).values(
                "id", "category_id", "sub_category_id"
            )
            prod_map = {p["id"]: p for p in products}
            for item in cart_items:
                p_info = prod_map.get(item.get("product_id"))
                if p_info:
                    if not item.get("category_id"):
                        item["category_id"] = p_info["category_id"]
                    if not item.get("subcategory_id"):
                        item["subcategory_id"] = p_info["sub_category_id"]

        return cart_items

    @staticmethod
    def _build_promo_code_reward_details(promo_code):
        """
        Builds the reward details payload for a promo code, including the
        applicable categories or products according to its scope.
        """
        details = {
            "promo_type": promo_code.promo_type,
            "scope": promo_code.scope,
            "amount": promo_code.amount,
        }
        if promo_code.scope == PromoCode.ScopeType.CATEGORY:
            details["categories"] = [
                {"id": cat.id, "name": cat.name}
                for cat in promo_code.categories.all()
            ]
        elif promo_code.scope == PromoCode.ScopeType.PRODUCT:
            details["products"] = [
                {"id": p.id, "name": p.name}
                for p in promo_code.products.all()
            ]
        return details

    @classmethod
    def is_promo_code_valid(
        cls, promo_code, user=None, cart_total=0.0, cart_items=None, now=None
    ):
        if not promo_code.is_active:
            return False, "Promo code is inactive."

        if now is None:
            now = timezone.now()

        if promo_code.start_datetime and now < promo_code.start_datetime:
            return False, "Promo code is not active yet."
        if promo_code.end_datetime and now > promo_code.end_datetime:
            return False, "Promo code has expired."

        if (
            promo_code.max_total_usage
            and promo_code.current_usage_count >= promo_code.max_total_usage
        ):
            return False, "Promo code maximum usage limit reached."

        if promo_code.min_order_amount and cart_total < promo_code.min_order_amount:
            return (
                False,
                f"Minimum order total of Rs. {promo_code.min_order_amount} required to use this promo code.",
            )

        if user and user.is_authenticated:
            has_redeemed = OfferRedemption.objects.filter(
                promo_code=promo_code, user=user
            ).exists()
            if has_redeemed:
                return False, "You have already used this promo code."

        # Validate scope requirements against cart items
        if promo_code.scope == PromoCode.ScopeType.PRODUCT:
            if not cart_items:
                return (
                    False,
                    "You don't have that product in your cart to apply this promo code.",
                )

            target_product_ids = set(promo_code.products.values_list("id", flat=True))
            has_matching_product = any(
                item.get("product_id") in target_product_ids for item in cart_items
            )
            if not has_matching_product:
                return (
                    False,
                    "You don't have that product in your cart to apply this promo code.",
                )

        elif promo_code.scope == PromoCode.ScopeType.CATEGORY:
            if not cart_items:
                return (
                    False,
                    "You don't have that category product in your cart to apply this promo code.",
                )

            cls._enrich_cart_items_categories(cart_items)
            target_category_ids = set(
                promo_code.categories.values_list("id", flat=True)
            )
            has_matching_category = any(
                item.get("category_id") in target_category_ids for item in cart_items
            )
            if not has_matching_category:
                return (
                    False,
                    "You don't have that category product in your cart to apply this promo code.",
                )

        return True, None

    @classmethod
    def check_promo_code_detail(
        cls, code_str, cart_total=0.0, cart_items=None, delivery_charge=0.0, user=None
    ):
        """
        Validates a promo code string and returns its full detail and calculated discount.
        """
        now = timezone.now()
        try:
            promo_code = PromoCode.objects.prefetch_related(
                "categories", "products"
            ).get(code__iexact=code_str.strip())
        except PromoCode.DoesNotExist:
            return {
                "is_valid": False,
                "message": "Invalid promo code.",
                "error": "Invalid promo code.",
                "promo_code": None,
            }

        if cart_items:
            cls._enrich_cart_items_categories(cart_items)

        reward_details = cls._build_promo_code_reward_details(promo_code)

        promo_code_data = {
            "id": promo_code.id,
            "code": promo_code.code,
            "description": promo_code.description,
            "promo_type": promo_code.promo_type,
            "scope": promo_code.scope,
            "amount": promo_code.amount,
            "min_order_amount": promo_code.min_order_amount,
            "max_discount_amount": promo_code.max_discount_amount,
            "max_total_usage": promo_code.max_total_usage,
            "current_usage_count": promo_code.current_usage_count,
            "start_datetime": promo_code.start_datetime,
            "end_datetime": promo_code.end_datetime,
            "is_active": promo_code.is_active,
            "reward_details": reward_details,
        }
        if promo_code.scope == PromoCode.ScopeType.CATEGORY:
            promo_code_data["categories"] = reward_details.get("categories", [])
        elif promo_code.scope == PromoCode.ScopeType.PRODUCT:
            promo_code_data["products"] = reward_details.get("products", [])

        is_valid, err_msg = cls.is_promo_code_valid(
            promo_code,
            user=user,
            cart_total=cart_total,
            cart_items=cart_items,
            now=now,
        )
        if not is_valid:
            promo_code_data["calculated_discount"] = 0.0
            return {
                "is_valid": False,
                "message": err_msg,
                "error": err_msg,
                "promo_code": promo_code_data,
            }

        calculated_discount = (
            promo_code.calculate_discount(
                cart_total=cart_total,
                cart_items=cart_items,
                delivery_charge=delivery_charge,
            )
            if cart_total > 0 or delivery_charge > 0
            else 0.0
        )

        if (cart_total > 0 or delivery_charge > 0) and calculated_discount <= 0:
            if promo_code.scope == PromoCode.ScopeType.PRODUCT:
                err_msg = (
                    "You don't have that product in your cart to apply this promo code."
                )
            elif promo_code.scope == PromoCode.ScopeType.CATEGORY:
                err_msg = "You don't have that category product in your cart to apply this promo code."
            elif promo_code.promo_type == PromoCode.PromoCodeType.DELIVERY_CHARGE:
                err_msg = "Delivery charge is Rs. 0. This promo code cannot be applied."
            else:
                err_msg = "This promo code cannot be applied to the items in your cart."

            promo_code_data["calculated_discount"] = 0.0
            return {
                "is_valid": False,
                "message": err_msg,
                "error": err_msg,
                "promo_code": promo_code_data,
            }

        promo_code_data["calculated_discount"] = calculated_discount

        return {
            "is_valid": True,
            "message": "Promo code is valid.",
            "promo_code": promo_code_data,
        }

    @classmethod
    def evaluate_cart_offer(
        cls, cart_items, cart_total, delivery_charge=0.0, promo_code_str=None, user=None
    ):
        """
        Evaluates a promo code or active offer for a cart.
        """
        now = timezone.now()

        if cart_items:
            cls._enrich_cart_items_categories(cart_items)

        if promo_code_str:
            try:
                promo_code_obj = PromoCode.objects.prefetch_related(
                    "categories", "products"
                ).get(code__iexact=promo_code_str.strip())
            except PromoCode.DoesNotExist:
                return {
                    "is_valid": False,
                    "message": "Invalid promo code.",
                    "error": "Invalid promo code.",
                    "discount_amount": 0.0,
                }

            reward_details = cls._build_promo_code_reward_details(promo_code_obj)

            is_code_valid, err_msg = cls.is_promo_code_valid(
                promo_code_obj,
                user=user,
                cart_total=cart_total,
                cart_items=cart_items,
                now=now,
            )
            if not is_code_valid:
                return {
                    "is_valid": False,
                    "message": err_msg,
                    "error": err_msg,
                    "discount_amount": 0.0,
                    "reward_details": reward_details,
                }

            if (
                promo_code_obj.promo_type == PromoCode.PromoCodeType.DELIVERY_CHARGE
                and delivery_charge <= 0
            ):
                return {
                    "is_valid": False,
                    "message": "Delivery charge is Rs. 0. This promo code cannot be applied.",
                    "error": "Delivery charge is Rs. 0. This promo code cannot be applied.",
                    "discount_amount": 0.0,
                    "reward_details": reward_details,
                }

            discount_amount = promo_code_obj.calculate_discount(
                cart_total=cart_total,
                cart_items=cart_items,
                delivery_charge=delivery_charge,
            )

            if discount_amount <= 0:
                if promo_code_obj.scope == PromoCode.ScopeType.PRODUCT:
                    msg = "You don't have that product in your cart to apply this promo code."
                elif promo_code_obj.scope == PromoCode.ScopeType.CATEGORY:
                    msg = "You don't have that category product in your cart to apply this promo code."
                elif (
                    promo_code_obj.promo_type == PromoCode.PromoCodeType.DELIVERY_CHARGE
                ):
                    msg = "Delivery charge is Rs. 0. This promo code cannot be applied."
                else:
                    msg = "This promo code cannot be applied to the items in your cart."

                return {
                    "is_valid": False,
                    "message": msg,
                    "error": msg,
                    "discount_amount": 0.0,
                    "reward_details": reward_details,
                }

            return {
                "is_valid": True,
                "message": "Promo code applied successfully.",
                "offer_id": None,
                "offer_title": f"Promo Code: {promo_code_obj.code}",
                "promo_code": promo_code_obj.code,
                "discount_amount": discount_amount,
                "reward_details": reward_details,
            }

        # Look for active auto-applied offer
        offer = (
            Offer.objects
            .select_related("category", "subcategory", "buy_product", "get_product")
            .prefetch_related("products")
            .filter(is_active=True)
            .order_by("-discount_percentage", "-discount_amount")
            .first()
        )

        if not offer:
            return {
                "is_valid": False,
                "message": "No active offer available.",
                "error": "No active offer available.",
                "discount_amount": 0.0,
            }

        if not offer.is_active:
            return {
                "is_valid": False,
                "message": "Offer is currently inactive.",
                "error": "Offer is currently inactive.",
                "discount_amount": 0.0,
            }

        is_time_ok, time_err = cls.is_offer_time_valid(offer, now=now)
        if not is_time_ok:
            return {
                "is_valid": False,
                "message": time_err,
                "error": time_err,
                "discount_amount": 0.0,
            }

        # Check minimum order amount constraint
        if cart_total < offer.min_order_amount:
            return {
                "is_valid": False,
                "message": f"Minimum order total of Rs. {offer.min_order_amount} required to use this offer.",
                "error": f"Minimum order total of Rs. {offer.min_order_amount} required to use this offer.",
                "discount_amount": 0.0,
            }

        # Build reward details for auto-applied offer
        reward_details = {
            "scope": offer.scope,
            "offer_type": offer.offer_type,
        }
        if offer.scope == Offer.ScopeType.CATEGORY and offer.category:
            reward_details["categories"] = [
                {"id": offer.category.id, "name": offer.category.name}
            ]
        elif offer.scope == Offer.ScopeType.SUBCATEGORY and offer.subcategory:
            reward_details["subcategories"] = [
                {"id": offer.subcategory.id, "name": offer.subcategory.name}
            ]
        elif offer.scope == Offer.ScopeType.PRODUCT:
            reward_details["products"] = [
                {"id": p.id, "name": p.name}
                for p in offer.products.all()
            ]

        # Calculate eligible subtotal based on offer scope
        eligible_subtotal = cart_total
        if offer.scope == Offer.ScopeType.PRODUCT:
            target_product_ids = set(offer.products.values_list("id", flat=True))
            matching_items = [
                item
                for item in cart_items
                if item.get("product_id") in target_product_ids
            ]
            if not matching_items:
                return {
                    "is_valid": False,
                    "message": "You don't have the required product in your cart to claim this offer.",
                    "error": "You don't have the required product in your cart to claim this offer.",
                    "discount_amount": 0.0,
                    "reward_details": reward_details,
                }
            eligible_subtotal = sum(
                item.get("price", 0.0) * item.get("quantity", 1)
                for item in matching_items
            )
        elif offer.scope == Offer.ScopeType.CATEGORY:
            matching_items = [
                item
                for item in cart_items
                if item.get("category_id") == offer.category_id
            ]
            if not matching_items:
                return {
                    "is_valid": False,
                    "message": "You don't have the required category product in your cart to claim this offer.",
                    "error": "You don't have the required category product in your cart to claim this offer.",
                    "discount_amount": 0.0,
                    "reward_details": reward_details,
                }
            eligible_subtotal = sum(
                item.get("price", 0.0) * item.get("quantity", 1)
                for item in matching_items
            )
        elif offer.scope == Offer.ScopeType.SUBCATEGORY:
            matching_items = [
                item
                for item in cart_items
                if item.get("subcategory_id") == offer.subcategory_id
            ]
            if not matching_items:
                return {
                    "is_valid": False,
                    "message": "You don't have the required subcategory product in your cart to claim this offer.",
                    "error": "You don't have the required subcategory product in your cart to claim this offer.",
                    "discount_amount": 0.0,
                    "reward_details": reward_details,
                }
            eligible_subtotal = sum(
                item.get("price", 0.0) * item.get("quantity", 1)
                for item in matching_items
            )

        # Calculate discount based on offer_type and scope
        discount_amount = 0.0

        if offer.offer_type == Offer.OfferType.PERCENTAGE:
            discount_amount = (eligible_subtotal * offer.discount_percentage) / 100.0
            if (
                offer.max_discount_amount
                and discount_amount > offer.max_discount_amount
            ):
                discount_amount = offer.max_discount_amount

        elif offer.offer_type == Offer.OfferType.FLAT:
            discount_amount = min(offer.discount_amount, eligible_subtotal)

        elif offer.offer_type == Offer.OfferType.FREE_DELIVERY:
            discount_amount = 0.0
            reward_details["free_delivery"] = True

        elif offer.offer_type == Offer.OfferType.BUY_X_GET_Y:
            # Check if required buy_product exists in cart with buy_quantity
            buy_item = next(
                (
                    item
                    for item in cart_items
                    if item.get("product_id") == offer.buy_product_id
                ),
                None,
            )
            if not buy_item or buy_item.get("quantity", 0) < offer.buy_quantity:
                return {
                    "is_valid": False,
                    "message": f"Buy at least {offer.buy_quantity} of {offer.buy_product.name if offer.buy_product else 'required item'} to claim this offer.",
                    "error": f"Buy at least {offer.buy_quantity} of {offer.buy_product.name if offer.buy_product else 'required item'} to claim this offer.",
                    "discount_amount": 0.0,
                    "reward_details": reward_details,
                }

            get_product_name = (
                offer.get_product.name if offer.get_product else "reward item"
            )
            reward_details["bogo"] = {
                "get_product_id": offer.get_product_id,
                "get_product_name": get_product_name,
                "get_quantity": offer.get_quantity,
                "discount_percentage": offer.get_discount_percentage,
            }

        return {
            "is_valid": True,
            "message": "Offer applied successfully.",
            "offer_id": offer.id,
            "offer_title": offer.title,
            "promo_code": None,
            "discount_amount": round(discount_amount, 2),
            "reward_details": reward_details,
        }
