from django.db import transaction

from notification.services.notification_service import NotificationService
from offer.models import Offer, OfferRedemption, PromoCode
from offer.services.offer_service import OfferService
from order.models import ActivityLog, Order, OrderItem, OrderItemExtra
from order.services.activity_log_service import ActivityLogService
from order.services.branch_service import BranchAssignmentService
from order.services.order_websocket_service import OrderWebSocketService
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
        lat = order_data.get("latitude")
        lon = order_data.get("longitude")
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

        payload_delivery_fee = order_data.get("delivery_fee")
        delivery_fee = 0.0
        if payload_delivery_fee is not None:
            try:
                delivery_fee = max(0.0, round(float(payload_delivery_fee), 2))
            except (ValueError, TypeError):
                delivery_fee = 0.0

        order_type = order_data.get("order_type", Order.OrderType.DELIVERY)
        if order_type == Order.OrderType.DELIVERY and nearest_branch:
            if payload_delivery_fee is None or delivery_fee == 0.0:
                try:
                    from delivery.services.delivery_service import DeliveryService

                    delivery_estimate = DeliveryService.estimate_delivery(
                        destination_lat=lat,
                        destination_lng=lon,
                        branch_id=nearest_branch.id,
                        allow_fallback=True,
                    )
                    delivery_fee = float(delivery_estimate["delivery_charge"])
                except Exception:
                    pass
        elif order_type in (Order.OrderType.TAKEAWAY, Order.OrderType.DINEIN):
            delivery_fee = 0.0

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
                delivery_charge=delivery_fee,
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

        # If discount_amount is explicitly provided in the payload from frontend, save it
        payload_discount = order_data.get("discount_amount")
        if payload_discount is not None:
            try:
                parsed_discount = float(payload_discount)
                if parsed_discount > 0:
                    discount_amount = parsed_discount
            except (ValueError, TypeError):
                pass

        discount_amount = round(min(discount_amount, subtotal), 2)

        total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

        # 6. Create Order record
        order = Order(
            user=user if user and user.is_authenticated else None,
            branch=nearest_branch,
            customer_name=order_data.get("customer_name"),
            phone_number=order_data.get("phone_number"),
            delivery_location=order_data.get("delivery_location"),
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
            order_type=order_data.get("order_type", Order.OrderType.DELIVERY),
            transaction_id=order_data.get("transaction_id"),
            is_paid=order_data.get("is_paid", False),
        )
        order._skip_signal_create = True
        order._skip_activity_log = True
        order.save()

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

        # Record single consolidated activity log for order creation
        item_reprs = []
        for item in processed_items:
            extra_names = [ex.name for ex in item.get("extras", [])]
            extras_str = f" (+{', '.join(extra_names)})" if extra_names else ""
            item_reprs.append(f"{item['quantity']}x {item['product'].name}{extras_str}")

        items_summary = (
            f" with {len(item_reprs)} item(s) ({', '.join(item_reprs)})"
            if item_reprs
            else ""
        )
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.ORDER,
            entity_name="Order",
            record_id=str(order.pk),
            record_repr=f"Order #{order.order_number}",
            order=order,
            description=(
                f"Order #{order.order_number} created{items_summary} for customer "
                f"'{order.customer_name or 'Walk-in'}' (Status: {order.status}, "
                f"Type: {order.order_type}, Total: Rs. {order.total_amount})."
            ),
            changes={
                "order_number": order.order_number,
                "status": order.status,
                "order_type": order.order_type,
                "payment_type": order.payment_type,
                "total_amount": order.total_amount,
                "customer_name": order.customer_name,
                "phone_number": order.phone_number,
                "items": item_reprs,
            },
        )
        order._skip_activity_log = False

        # 9. Trigger notification and WebSocket broadcast after transaction commit
        order_id = order.id
        transaction.on_commit(
            lambda: NotificationService.send_order_notification(order)
        )
        transaction.on_commit(
            lambda: OrderWebSocketService.broadcast_order_created(order_id)
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
        # Determine customer_name and phone_number from payload or customer_user
        raw_customer_name = str(order_data.get("customer_name") or "").strip()
        raw_phone_number = str(order_data.get("phone_number") or "").strip()

        if raw_customer_name:
            customer_name = raw_customer_name
        elif customer_user:
            full_name = customer_user.get_full_name().strip()
            customer_name = full_name if full_name else customer_user.username
        else:
            customer_name = "POS Customer"

        if raw_phone_number:
            phone_number = raw_phone_number
        elif customer_user:
            phone_number = getattr(customer_user, "phone_number", "") or "N/A"
        else:
            phone_number = "N/A"

        # Determine target branch
        assigned_branch = branch
        if not assigned_branch and hasattr(created_by, "branch"):
            assigned_branch = created_by.branch

        # Determine location parameters from payload, branch, or defaults
        raw_delivery_location = str(order_data.get("delivery_location") or "").strip()
        if raw_delivery_location:
            delivery_location = raw_delivery_location
        elif assigned_branch:
            delivery_location = assigned_branch.address or "POS Counter"
        else:
            delivery_location = "POS Counter"

        lat = order_data.get("latitude")
        if lat is None:
            lat = (
                assigned_branch.latitude
                if (assigned_branch and assigned_branch.latitude is not None)
                else 0.0
            )
        else:
            try:
                lat = float(lat)
            except (ValueError, TypeError):
                lat = 0.0

        lon = order_data.get("longitude")
        if lon is None:
            lon = (
                assigned_branch.longitude
                if (assigned_branch and assigned_branch.longitude is not None)
                else 0.0
            )
        else:
            try:
                lon = float(lon)
            except (ValueError, TypeError):
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

        # If discount_amount is explicitly provided in the payload from frontend, save it
        payload_discount = order_data.get("discount_amount")
        if payload_discount is not None:
            try:
                parsed_discount = float(payload_discount)
                if parsed_discount > 0:
                    discount_amount = parsed_discount
            except (ValueError, TypeError):
                pass

        discount_amount = round(min(discount_amount, subtotal), 2)

        # Delivery fee from payload if provided
        payload_delivery_fee = order_data.get("delivery_fee")
        delivery_fee = 0.0
        if payload_delivery_fee is not None:
            try:
                delivery_fee = max(0.0, round(float(payload_delivery_fee), 2))
            except (ValueError, TypeError):
                delivery_fee = 0.0

        total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

        # Create Order
        order = Order(
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
            order_type=order_data.get("order_type", Order.OrderType.DINEIN),
            transaction_id=order_data.get("transaction_id"),
            is_paid=order_data.get("is_paid", False),
            status=Order.OrderStatus.CONFIRMED,
        )
        order._skip_signal_create = True
        order._skip_activity_log = True
        order.save()

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

        # Record single consolidated activity log for POS order creation
        item_reprs = []
        for item in processed_items:
            extra_names = [ex.name for ex in item.get("extras", [])]
            extras_str = f" (+{', '.join(extra_names)})" if extra_names else ""
            item_reprs.append(f"{item['quantity']}x {item['product'].name}{extras_str}")

        items_summary = (
            f" with {len(item_reprs)} item(s) ({', '.join(item_reprs)})"
            if item_reprs
            else ""
        )
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.ORDER,
            entity_name="Order",
            record_id=str(order.pk),
            record_repr=f"Order #{order.order_number}",
            order=order,
            description=(
                f"POS Order #{order.order_number} created{items_summary} for customer "
                f"'{order.customer_name or 'Walk-in'}' (Status: {order.status}, "
                f"Type: {order.order_type}, Total: Rs. {order.total_amount})."
            ),
            changes={
                "order_number": order.order_number,
                "status": order.status,
                "order_type": order.order_type,
                "payment_type": order.payment_type,
                "total_amount": order.total_amount,
                "customer_name": order.customer_name,
                "phone_number": order.phone_number,
                "items": item_reprs,
            },
        )
        order._skip_activity_log = False

        # Trigger notification and WebSocket broadcast
        order_id = order.id
        transaction.on_commit(
            lambda: NotificationService.send_order_notification(order)
        )
        transaction.on_commit(
            lambda: OrderWebSocketService.broadcast_order_created(order_id)
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
        order.save(update_fields=["assigned_to_rider", "updated_at"])

        # Trigger notification creation and WebSocket push
        notification_title = (
            f"Rider Assigned to Order #{order.order_number}"
            if rider
            else f"Rider Unassigned from Order #{order.order_number}"
        )
        notification_msg = (
            f"Rider {rider.get_full_name() or rider.username} has been assigned to your order."
            if rider
            else "Rider assignment has been removed from your order."
        )

        transaction.on_commit(
            lambda: NotificationService.create_notification(
                title=notification_title,
                message=notification_msg,
                notification_type="rider_assigned" if rider else "rider_unassigned",
                data={
                    "order_number": order.order_number,
                    "status": order.status,
                    "rider_id": rider.id if rider else None,
                },
            )
        )

        return order

    @classmethod
    @transaction.atomic
    def update_order_status(cls, order, new_status, comment=None, changed_by=None):
        """
        Updates the status of an order.
        - Validates that a comment is provided if new_status is CANCELLED.
        - Attaches optional comment and changed_by attributes to trigger automatic
          OrderStatusHistory creation upon save().
        - Triggers notification.
        """
        if new_status == Order.OrderStatus.CANCELLED and (
            not comment or not comment.strip()
        ):
            raise ValueError("A comment/reason is required when cancelling an order.")

        old_status = order.status
        order.status = new_status
        if comment:
            order._status_change_comment = comment.strip()
        if changed_by:
            order._status_changed_by = changed_by

        order.save()

        # Trigger notification creation and WebSocket push
        transaction.on_commit(
            lambda: NotificationService.create_notification(
                title=f"Order #{order.order_number} {order.get_status_display()}",
                message=f"Order status updated to {order.get_status_display()}."
                + (f" Reason: {comment}" if comment else ""),
                notification_type="order_status_update",
                data={
                    "order_number": order.order_number,
                    "status": order.status,
                    "old_status": old_status,
                },
            )
        )

        return order

    @classmethod
    def broadcast_order_created(cls, order_or_id):
        """Dispatches order.created WebSocket event."""
        return OrderWebSocketService.broadcast_order_created(order_or_id)

    @classmethod
    def broadcast_order_ready_for_pickup(cls, order_or_id):
        """Dispatches order.ready_for_pickup WebSocket event."""
        return OrderWebSocketService.broadcast_order_ready_for_pickup(order_or_id)

    @classmethod
    @transaction.atomic
    def update_order_items(cls, order, cart_items_data, save_order=True):
        """
        Updates items on an existing order with the provided cart_items_data.

        Performs a smart differential update:
        1. Compares incoming items with existing items on the order.
           If items have NOT changed (same products, quantities, extras), this is a no-op!
        2. If items changed:
           - Existing matching items have their quantity/prices updated in-place (no delete+recreate).
           - New items are created.
           - Removed items are deleted.
        3. Recalculates subtotal and total_amount.
        4. If save_order is True, saves the order and logs the activity.
        """
        # Normalise: accept both "product_id" and "product" as the product key
        normalised = []
        for item in cart_items_data:
            p_val = item.get("product_id") or item.get("product")
            if isinstance(p_val, dict):
                p_id = p_val.get("id")
            else:
                p_id = p_val

            try:
                p_id = int(p_id)
            except (TypeError, ValueError):
                continue

            try:
                qty = int(item.get("quantity", 1))
            except (TypeError, ValueError):
                qty = 1

            extras_input = item.get("extras") or item.get("selected_extras") or []
            normalised_extras = []
            for ex in extras_input:
                if isinstance(ex, dict):
                    ex_id = ex.get("extra_id") or ex.get("extra") or ex.get("id")
                else:
                    ex_id = ex
                try:
                    if ex_id is not None:
                        normalised_extras.append(int(ex_id))
                except (TypeError, ValueError):
                    continue

            normalised.append({
                "product_id": p_id,
                "quantity": qty,
                "extra_ids": tuple(sorted(normalised_extras)),
            })

        existing_items = list(order.items.prefetch_related("selected_extras").all())

        def _existing_item_signature(it):
            extras_tuple = tuple(
                sorted(ex.extra_id for ex in it.selected_extras.all() if ex.extra_id)
            )
            return (it.product_id, extras_tuple, it.quantity)

        def _incoming_item_signature(it):
            return (it["product_id"], it["extra_ids"], it["quantity"])

        existing_sig = sorted([_existing_item_signature(it) for it in existing_items])
        incoming_sig = sorted([_incoming_item_signature(it) for it in normalised])

        # If existing items and incoming items are completely identical, do nothing!
        if existing_sig == incoming_sig:
            return order

        product_ids = [item["product_id"] for item in normalised]
        products_map = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        # Validate all products exist
        missing = set(product_ids) - set(products_map.keys())
        if missing:
            raise ValueError(f"Products not found: {missing}")

        all_extra_ids = [ex_id for item in normalised for ex_id in item["extra_ids"]]
        extras_map = (
            {e.id: e for e in ProductExtra.objects.filter(id__in=all_extra_ids)}
            if all_extra_ids
            else {}
        )

        # Index existing items by (product_id, extra_ids)
        existing_by_key = {}
        for it in existing_items:
            extras_tuple = tuple(
                sorted(ex.extra_id for ex in it.selected_extras.all() if ex.extra_id)
            )
            key = (it.product_id, extras_tuple)
            existing_by_key.setdefault(key, []).append(it)

        # Perform smart in-place update or create
        items_added = []
        items_updated = []
        items_removed = []
        subtotal = 0.0

        for item in normalised:
            key = (item["product_id"], item["extra_ids"])
            product = products_map[item["product_id"]]
            qty = item["quantity"]
            unit_price = float(product.price)
            extras_price_per_unit = sum(
                float(extras_map[eid].additional_price)
                for eid in item["extra_ids"]
                if eid in extras_map
            )
            item_subtotal = round((unit_price + extras_price_per_unit) * qty, 2)
            item_extras_total = round(extras_price_per_unit * qty, 2)
            subtotal += item_subtotal

            if key in existing_by_key and existing_by_key[key]:
                matched_item = existing_by_key[key].pop(0)
                # In-place update only if dirty
                if (
                    matched_item.quantity != qty
                    or matched_item.unit_price != unit_price
                    or matched_item.subtotal != item_subtotal
                ):
                    old_qty = matched_item.quantity
                    matched_item.quantity = qty
                    matched_item.unit_price = unit_price
                    matched_item.extras_price = item_extras_total
                    matched_item.subtotal = item_subtotal
                    matched_item.save(
                        update_fields=[
                            "quantity",
                            "unit_price",
                            "extras_price",
                            "subtotal",
                            "updated_at",
                        ]
                    )
                    items_updated.append(
                        f"{product.name} (qty: {old_qty} \u2192 {qty})"
                    )
            else:
                # Brand new item added to the order
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=qty,
                    unit_price=unit_price,
                    extras_price=item_extras_total,
                    subtotal=item_subtotal,
                )
                extra_objs = [
                    extras_map[eid] for eid in item["extra_ids"] if eid in extras_map
                ]
                if extra_objs:
                    OrderItemExtra.objects.bulk_create([
                        OrderItemExtra(
                            order_item=order_item,
                            extra=ex,
                            extra_name=ex.name,
                            additional_price=ex.additional_price,
                        )
                        for ex in extra_objs
                    ])
                extra_names = [ex.name for ex in extra_objs]
                extras_str = f" (+{', '.join(extra_names)})" if extra_names else ""
                items_added.append(f"{qty}x {product.name}{extras_str}")

        # Delete any items that were removed in the new cart
        for remaining_list in existing_by_key.values():
            for remaining_item in remaining_list:
                prod_name = getattr(
                    remaining_item.product,
                    "name",
                    f"Product #{remaining_item.product_id}",
                )
                extra_names = [
                    ex.extra_name for ex in remaining_item.selected_extras.all()
                ]
                extras_str = f" (+{', '.join(extra_names)})" if extra_names else ""
                items_removed.append(
                    f"{remaining_item.quantity}x {prod_name}{extras_str}"
                )
                remaining_item.delete()

        subtotal = round(subtotal, 2)
        delivery_fee = float(order.delivery_fee or 0.0)
        discount_amount = float(order.discount_amount or 0.0)
        total_amount = max(0.0, round(subtotal - discount_amount + delivery_fee, 2))

        # Update order financials
        order.subtotal = subtotal
        order.total_amount = total_amount

        # Attach item changes for single unified activity logging
        order._order_item_changes = {
            "items_added": items_added,
            "items_updated": items_updated,
            "items_removed": items_removed,
        }

        if save_order:
            order.save(update_fields=["subtotal", "total_amount", "updated_at"])

        return order
