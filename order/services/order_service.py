from django.db import transaction

from offer.models import Offer, OfferRedemption, PromoCode
from offer.services.offer_service import OfferService
from order.models import Order, OrderItem
from order.services.branch_service import BranchAssignmentService
from product.models import Product


class OrderService:
    @classmethod
    @transaction.atomic
    def create_order(cls, user, order_data, cart_items_data):
        """
        Creates an order, automatically assigns the nearest branch using latitude/longitude,
        evaluates offers/promo codes, creates order items, and records offer redemptions.
        """
        lat = order_data["latitude"]
        lon = order_data["longitude"]
        promo_code_str = order_data.get("promo_code")

        # 1. Automatically find nearest active branch
        nearest_branch = BranchAssignmentService.get_nearest_active_branch(
            latitude=lat, longitude=lon
        )

        # 2. Fetch products and calculate subtotal
        product_ids = [item["product_id"] for item in cart_items_data]
        products_map = {
            p.id: p for p in Product.objects.filter(id__in=product_ids)
        }

        subtotal = 0.0
        processed_items = []
        for item in cart_items_data:
            p_id = item["product_id"]
            qty = item["quantity"]
            product = products_map.get(p_id)
            if not product:
                raise ValueError(f"Product with ID {p_id} does not exist.")

            unit_price = product.price
            item_subtotal = round(unit_price * qty, 2)
            subtotal += item_subtotal

            processed_items.append({
                "product": product,
                "quantity": qty,
                "unit_price": unit_price,
                "subtotal": item_subtotal,
            })

        subtotal = round(subtotal, 2)

        # 3. Evaluate offer / promo code if provided
        discount_amount = 0.0
        offer_obj = None
        promo_code_obj = None

        if promo_code_str or Offer.objects.filter(is_active=True).exists():
            formatted_cart_items = [
                {
                    "product_id": item["product"].id,
                    "category_id": item["product"].category_id,
                    "subcategory_id": item["product"].sub_category_id,
                    "price": item["unit_price"],
                    "quantity": item["quantity"],
                }
                for item in processed_items
            ]

            offer_res = OfferService.evaluate_cart_offer(
                cart_items=formatted_cart_items,
                cart_total=subtotal,
                promo_code_str=promo_code_str,
                user=user if user and user.is_authenticated else None,
            )

            if offer_res["is_valid"]:
                discount_amount = offer_res["discount_amount"]
                if offer_res.get("offer_id"):
                    offer_obj = Offer.objects.filter(id=offer_res["offer_id"]).first()

                if offer_res.get("promo_code"):
                    promo_code_obj = PromoCode.objects.filter(code__iexact=offer_res["promo_code"]).first()

        delivery_fee = order_data.get("delivery_fee", 0.0)
        total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

        # 4. Create Order record
        order = Order.objects.create(
            user=user if user and user.is_authenticated else None,
            branch=nearest_branch,
            customer_name=order_data["customer_name"],
            phone_number=order_data["phone_number"],
            delivery_location=order_data["delivery_location"],
            latitude=lat,
            longitude=lon,
            special_note=order_data.get("special_note", ""),
            subtotal=subtotal,
            discount_amount=discount_amount,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            offer=offer_obj,
            promo_code=promo_code_obj,
        )

        # 5. Create OrderItem records
        order_items = [
            OrderItem(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                subtotal=item["subtotal"],
            )
            for item in processed_items
        ]
        OrderItem.objects.bulk_create(order_items)

        # 6. Record offer/promo redemption if applied
        if (offer_obj or promo_code_obj) and user and user.is_authenticated:
            OfferRedemption.objects.create(
                offer=offer_obj,
                promo_code=promo_code_obj,
                user=user,
                order_id=str(order.id),
                discount_applied=discount_amount,
            )
            if promo_code_obj:
                promo_code_obj.current_usage_count += 1
                promo_code_obj.save(update_fields=["current_usage_count"])

        return order
