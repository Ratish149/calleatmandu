from django.db import transaction

from notification.services.notification_service import NotificationService
from offer.models import Offer, OfferRedemption, PromoCode
from offer.services.offer_service import OfferService
from order.models import Order, OrderItem, OrderItemExtra
from order.services.branch_service import BranchAssignmentService
from product.models import Product, ProductExtra


class OrderService:
    @classmethod
    @transaction.atomic
    def create_order(cls, user, order_data, cart_items_data):
        """
        Creates an order, automatically assigns the nearest branch using latitude/longitude,
        evaluates offers/promo codes, creates order items (with extras), and records
        offer redemptions.
        """
        lat = order_data["latitude"]
        lon = order_data["longitude"]
        promo_code_str = order_data.get("promo_code")

        # 1. Automatically find nearest active branch
        nearest_branch = BranchAssignmentService.get_nearest_active_branch(
            latitude=lat, longitude=lon
        )

        # 2. Fetch products
        product_ids = [item["product_id"] for item in cart_items_data]
        products_map = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        # 3. Fetch all requested extras in one query
        all_extra_ids = [
            ex["extra_id"] for item in cart_items_data for ex in item.get("extras", [])
        ]
        extras_map = (
            {e.id: e for e in ProductExtra.objects.filter(id__in=all_extra_ids)}
            if all_extra_ids
            else {}
        )

        # 4. Calculate subtotal (product prices + extras)
        subtotal = 0.0
        processed_items = []

        for item in cart_items_data:
            p_id = item["product_id"]
            qty = item["quantity"]
            product = products_map.get(p_id)
            if not product:
                raise ValueError(f"Product with ID {p_id} does not exist.")

            unit_price = product.price

            # Resolve & validate extras for this item
            resolved_extras = []
            extras_price_per_unit = 0.0
            for ex_data in item.get("extras", []):
                extra = extras_map.get(ex_data["extra_id"])
                if not extra:
                    raise ValueError(
                        f"Extra with ID {ex_data['extra_id']} does not exist."
                    )
                if extra.product_id != p_id:
                    raise ValueError(
                        f"Extra '{extra.name}' does not belong to product '{product.name}'."
                    )
                extras_price_per_unit += extra.additional_price
                resolved_extras.append(extra)

            extras_price_per_unit = round(extras_price_per_unit, 2)
            item_subtotal = round((unit_price + extras_price_per_unit) * qty, 2)
            subtotal += item_subtotal

            processed_items.append({
                "product": product,
                "quantity": qty,
                "unit_price": unit_price,
                "extras_price": extras_price_per_unit,
                "subtotal": item_subtotal,
                "extras": resolved_extras,
            })

        subtotal = round(subtotal, 2)

        # 5. Evaluate offer / promo code if provided
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
                    promo_code_obj = PromoCode.objects.filter(
                        code__iexact=offer_res["promo_code"]
                    ).first()

        delivery_fee = order_data.get("delivery_fee", 0.0)
        total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

        # 6. Create Order record
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
            payment_type=order_data.get("payment_type", Order.PaymentType.COD),
            transaction_id=order_data.get("transaction_id"),
            is_paid=order_data.get("is_paid", False),
        )

        # 6b. Automatically link NPSTransaction if transaction_id is provided
        tx_id = order_data.get("transaction_id")
        if tx_id:
            from nps_payment.models import NPSTransaction

            nps_txn = NPSTransaction.objects.filter(merchant_txn_id=tx_id).first()
            if nps_txn:
                nps_txn.order = order
                nps_txn.save(update_fields=["order"])
                if nps_txn.status == "Success":
                    order.is_paid = True
                    order.status = Order.OrderStatus.CONFIRMED
                    order.payment_type = Order.PaymentType.NPS
                    order.save(update_fields=["is_paid", "status", "payment_type"])

        # 7. Create OrderItem records then bulk-create extras
        for item in processed_items:
            order_item = OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                extras_price=item["extras_price"],
                subtotal=item["subtotal"],
            )

            if item["extras"]:
                OrderItemExtra.objects.bulk_create([
                    OrderItemExtra(
                        order_item=order_item,
                        extra=extra,
                        extra_name=extra.name,
                        additional_price=extra.additional_price,
                    )
                    for extra in item["extras"]
                ])

        # 8. Record offer/promo redemption if applied
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

        # 9. Trigger notification after transaction commit
        transaction.on_commit(
            lambda: NotificationService.send_order_notification(order)
        )

        return order

    @classmethod
    @transaction.atomic
    def create_pos_order(
        cls, created_by, customer_user, branch, order_data, cart_items_data
    ):
        """
        Creates a POS order:
        - `created_by`: Staff/user creating the order (tracked via token).
        - `customer_user`: Optional customer User instance to extract customer_name and phone_number.
        - `branch`: Target branch for POS order (or staff's assigned branch).
        - `is_pos_order`: Set to True automatically.
        - `delivery_location`, `latitude`, `longitude`: Derived from branch (or POS counter defaults).
        """
        # Determine customer_name and phone_number from customer_user
        if customer_user:
            full_name = customer_user.get_full_name().strip()
            customer_name = full_name if full_name else customer_user.username
            phone_number = getattr(customer_user, "phone_number", "") or ""
        else:
            customer_name = "POS Customer"
            phone_number = "N/A"

        # Determine target branch
        assigned_branch = branch
        if not assigned_branch and hasattr(created_by, "branch"):
            assigned_branch = created_by.branch

        # Determine location parameters from branch or defaults
        if assigned_branch:
            delivery_location = assigned_branch.address or "POS Counter"
            lat = assigned_branch.latitude or 0.0
            lon = assigned_branch.longitude or 0.0
        else:
            delivery_location = "POS Counter"
            lat = 0.0
            lon = 0.0

        promo_code_str = order_data.get("promo_code")

        # Fetch products
        product_ids = [item["product_id"] for item in cart_items_data]
        products_map = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        # Fetch extras
        all_extra_ids = [
            ex["extra_id"] for item in cart_items_data for ex in item.get("extras", [])
        ]
        extras_map = (
            {e.id: e for e in ProductExtra.objects.filter(id__in=all_extra_ids)}
            if all_extra_ids
            else {}
        )

        # Calculate subtotal
        subtotal = 0.0
        processed_items = []

        for item in cart_items_data:
            p_id = item["product_id"]
            qty = item["quantity"]
            product = products_map.get(p_id)
            if not product:
                raise ValueError(f"Product with ID {p_id} does not exist.")

            unit_price = product.price

            resolved_extras = []
            extras_price_per_unit = 0.0
            for ex_data in item.get("extras", []):
                extra = extras_map.get(ex_data["extra_id"])
                if not extra:
                    raise ValueError(
                        f"Extra with ID {ex_data['extra_id']} does not exist."
                    )
                if extra.product_id != p_id:
                    raise ValueError(
                        f"Extra '{extra.name}' does not belong to product '{product.name}'."
                    )
                extras_price_per_unit += extra.additional_price
                resolved_extras.append(extra)

            extras_price_per_unit = round(extras_price_per_unit, 2)
            item_subtotal = round((unit_price + extras_price_per_unit) * qty, 2)
            subtotal += item_subtotal

            processed_items.append({
                "product": product,
                "quantity": qty,
                "unit_price": unit_price,
                "extras_price": extras_price_per_unit,
                "subtotal": item_subtotal,
                "extras": resolved_extras,
            })

        subtotal = round(subtotal, 2)

        # Evaluate offer / promo code
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
                user=customer_user
                if customer_user and customer_user.is_authenticated
                else None,
            )

            if offer_res["is_valid"]:
                discount_amount = offer_res["discount_amount"]
                if offer_res.get("offer_id"):
                    offer_obj = Offer.objects.filter(id=offer_res["offer_id"]).first()

                if offer_res.get("promo_code"):
                    promo_code_obj = PromoCode.objects.filter(
                        code__iexact=offer_res["promo_code"]
                    ).first()

        delivery_fee = order_data.get("delivery_fee", 0.0)
        total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

        # Create Order
        order = Order.objects.create(
            user=customer_user
            if customer_user and customer_user.is_authenticated
            else None,
            created_by=created_by,
            branch=assigned_branch,
            customer_name=customer_name,
            phone_number=phone_number,
            delivery_location=delivery_location,
            latitude=lat,
            longitude=lon,
            special_note=order_data.get("special_note", ""),
            subtotal=subtotal,
            discount_amount=discount_amount,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            offer=offer_obj,
            promo_code=promo_code_obj,
            is_pos_order=True,
            payment_type=order_data.get("payment_type", Order.PaymentType.COD),
            transaction_id=order_data.get("transaction_id"),
            is_paid=order_data.get("is_paid", False),
            status=Order.OrderStatus.CONFIRMED,
        )

        tx_id = order_data.get("transaction_id")
        if tx_id:
            from nps_payment.models import NPSTransaction

            nps_txn = NPSTransaction.objects.filter(merchant_txn_id=tx_id).first()
            if nps_txn:
                nps_txn.order = order
                nps_txn.save(update_fields=["order"])
                if nps_txn.status == "Success":
                    order.is_paid = True
                    order.payment_type = Order.PaymentType.NPS
                    order.save(update_fields=["is_paid", "payment_type"])

        # Create items and extras
        for item in processed_items:
            order_item = OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                extras_price=item["extras_price"],
                subtotal=item["subtotal"],
            )

            if item["extras"]:
                OrderItemExtra.objects.bulk_create([
                    OrderItemExtra(
                        order_item=order_item,
                        extra=extra,
                        extra_name=extra.name,
                        additional_price=extra.additional_price,
                    )
                    for extra in item["extras"]
                ])

        # Record offer redemption
        if (
            (offer_obj or promo_code_obj)
            and customer_user
            and customer_user.is_authenticated
        ):
            OfferRedemption.objects.create(
                offer=offer_obj,
                promo_code=promo_code_obj,
                user=customer_user,
                order_id=str(order.id),
                discount_applied=discount_amount,
            )
            if promo_code_obj:
                promo_code_obj.current_usage_count += 1
                promo_code_obj.save(update_fields=["current_usage_count"])

        # Trigger notification
        transaction.on_commit(
            lambda: NotificationService.send_order_notification(order)
        )

        return order

    @classmethod
    @transaction.atomic
    def assign_rider(cls, barcode_number=None, order_number=None, rider=None):
        """
        Assigns a rider to an order identified by either `barcode_number` or `order_number`.
        Updates order status to OUT_FOR_DELIVERY if currently PENDING, CONFIRMED, or PREPARING.
        """
        order = None
        if barcode_number:
            order = Order.objects.filter(barcode_number=barcode_number).first()
            if not order:
                raise ValueError(f"Order with barcode '{barcode_number}' not found.")
        elif order_number:
            order = Order.objects.filter(order_number=order_number).first()
            if not order:
                raise ValueError(f"Order with order number '{order_number}' not found.")
        else:
            raise ValueError("Either barcode_number or order_number must be provided.")

        order.assigned_to_rider = rider
        if order.status in [
            Order.OrderStatus.PENDING,
            Order.OrderStatus.CONFIRMED,
            Order.OrderStatus.PREPARING,
        ]:
            order.status = Order.OrderStatus.OUT_FOR_DELIVERY

        order.save(update_fields=["assigned_to_rider", "status", "updated_at"])
        return order
