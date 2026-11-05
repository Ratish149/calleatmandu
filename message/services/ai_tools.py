import inspect
import json
import logging
from typing import Any, Dict, Optional

from django.db.models import Q

logger = logging.getLogger(__name__)

# Generic intent words that carry no dish/FAQ meaning. When a customer asks
# "can I see the menu?" the model calls search_menu(query="menu"); without this
# filter the naive icontains match would return nothing.
_QUERY_STOPWORDS = {
    "menu",
    "full",
    "show",
    "list",
    "all",
    "food",
    "dishes",
    "dish",
    "items",
    "item",
    "please",
    "what",
    "whats",
    "do",
    "does",
    "you",
    "your",
    "have",
    "has",
    "the",
    "a",
    "an",
    "me",
    "my",
    "i",
    "we",
    "us",
    "our",
    "can",
    "could",
    "would",
    "is",
    "are",
    "of",
    "on",
    "in",
    "to",
    "for",
    "and",
    "or",
    "any",
    "there",
    "get",
    "give",
    "see",
    "look",
    "looking",
    "available",
    "serve",
    "served",
    "sell",
    "selling",
    "offer",
    "offers",
    "options",
    "option",
    "today",
    "now",
    "restaurant",
    "order",
    "orders",
    "price",
    "prices",
    "cost",
    "how",
    "much",
    "many",
    "with",
    "without",
    "some",
    "this",
    "that",
}


def _meaningful_terms(query: str):
    """Extract searchable keywords, dropping generic intent words."""
    terms = []
    for word in str(query or "").lower().split():
        cleaned = "".join(ch for ch in word if ch.isalnum())
        if len(cleaned) > 1 and cleaned not in _QUERY_STOPWORDS:
            terms.append(cleaned)
    return terms[:5]


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_faq",
            "description": "Search the restaurant's frequently asked questions and answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to search for in FAQ questions/answers.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_menu",
            "description": (
                "Search the restaurant menu for dishes/products, with prices. "
                "Call it with a dish name or keyword to search; call it with an "
                "empty query to list the full menu."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Dish name or keyword to search for. Leave empty to "
                            "return the full menu."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Look up an order by its order number (e.g. ORD_123456) and return its status and details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_number": {
                        "type": "string",
                        "description": "The order number to look up.",
                    }
                },
                "required": ["order_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_wise_menu",
            "description": "Get the menu items for a specific category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {
                        "type": "string",
                        "description": "The name of the category to get menu items for.",
                    }
                },
                "required": ["category_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": (
                "Place a real order for the customer. Only call this after you "
                "know the exact menu item names with their quantities, and — for "
                "a delivery order — the customer's phone number and delivery "
                "address. Never invent items, prices or addresses."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Exact menu item name as shown on the menu.",
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "Quantity of the menu item.",
                                },
                            },
                            "required": ["name", "quantity"],
                        },
                        "description": "List of menu items to be ordered.",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's name, if known.",
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "Customer's phone number (required for delivery orders).",
                    },
                    "delivery_location": {
                        "type": "string",
                        "description": "Delivery address (required for delivery orders).",
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["DELIVERY", "TAKEAWAY"],
                        "description": "DELIVERY or TAKEAWAY. Defaults to DELIVERY.",
                    },
                    "special_note": {
                        "type": "string",
                        "description": "Any special instructions from the customer.",
                    },
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": (
                "Cancel one of the customer's own orders. Requires the order "
                "number and the phone number the order was placed with, for "
                "verification. Only call this after the customer has explicitly "
                "confirmed they want to cancel. Orders can only be cancelled "
                "within a short time window after they are placed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_number": {
                        "type": "string",
                        "description": "The order number to cancel, e.g. ORD_123456.",
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "The phone number the order was placed with.",
                    },
                },
                "required": ["order_number", "phone_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_recent_orders",
            "description": "Find a customer's recent orders by their phone number (for the branch of this conversation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "The customer's phone number.",
                    }
                },
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_branch_info",
            "description": "Get the branch's name, address, phone number and opening hours.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_offers",
            "description": "List currently active discounts and promotional offers.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def search_faq(query: str = "", limit: int = 5):
    from faq.models import Faq

    terms = _meaningful_terms(query)
    if terms:
        condition = Q()
        for word in terms:
            condition |= Q(question__icontains=word) | Q(answer__icontains=word)
        filtered = Faq.objects.filter(condition)
        # Fall back to all FAQs when a generic query matches nothing.
        queryset = filtered if filtered.exists() else Faq.objects.all()
    else:
        queryset = Faq.objects.all()
    return [
        {"question": faq.question, "answer": faq.answer} for faq in queryset[:limit]
    ]


def search_menu(query: str = "", limit: int = 8):
    from offer.selectors.offer_selector import calculate_product_offer_price, get_active_offers
    from product.models import Product

    queryset = Product.objects.select_related("category", "sub_category").order_by(
        "category__name", "name"
    )

    products = None
    terms = _meaningful_terms(query)
    if terms:
        condition = Q()
        for word in terms:
            condition |= Q(name__icontains=word) | Q(description__icontains=word)
        products = list(queryset.filter(condition)[:limit])
    # Generic query (e.g. "menu") or no match: return the full menu instead of
    # an empty list so the assistant can still answer.
    if not products:
        products = list(queryset[:limit])

    active_offers = get_active_offers()
    results = []
    for product in products:
        offer_price = calculate_product_offer_price(product, active_offers)
        results.append(
            {
                "name": product.name,
                "price": product.price,
                "offer_price": offer_price,
                "type": product.type,
                "category": product.category.name if product.category else None,
                "description": (product.description or "")[:200],
                "prepare_time": product.prepare_time,
                "in_stock": product.stock > 0,
            }
        )
    return results


def get_order_status(order_number: str = ""):
    from order.selectors.order_selector import get_order_by_number_with_relations

    order_number = str(order_number or "").strip()
    if not order_number:
        return {"error": "order_number is required"}

    candidates = [order_number]
    upper = order_number.upper()
    if upper.startswith("ORD_"):
        candidates.append("EAT_" + upper[4:])
    elif upper.startswith("EAT_"):
        candidates.append("ORD_" + upper[4:])

    order = None
    for candidate in candidates:
        order = get_order_by_number_with_relations(candidate)
        if order:
            break

    if not order:
        return {"error": "Order not found", "searched": candidates}

    return {
        "order_number": order.order_number,
        "status": order.status,
        "customer_name": order.customer_name,
        "total_amount": order.total_amount,
        "order_type": order.order_type,
        "delivery_location": order.delivery_location,
        "created_at": order.created_at,
        "items": [
            {
                "name": item.product.name if item.product else None,
                "quantity": item.quantity,
                "price": item.unit_price,
            }
            for item in order.items.all()
        ],
    }


def find_recent_orders(phone: str = "", branch_id=None, limit: int = 5):
    from order.models import Order

    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) < 7:
        return {"error": "A phone number with at least 7 digits is required"}

    queryset = Order.objects.all()
    if branch_id is not None:
        queryset = queryset.filter(branch_id=branch_id)

    matches = queryset.filter(phone_number__icontains=digits)
    if not matches.exists() and len(digits) > 7:
        matches = queryset.filter(phone_number__icontains=digits[-7:])

    return [
        {
            "order_number": order.order_number,
            "status": order.status,
            "total_amount": order.total_amount,
            "created_at": order.created_at,
        }
        for order in matches.order_by("-created_at")[:limit]
    ]


def get_branch_info(branch_id=None):
    from account.models import Branch

    queryset = Branch.objects.all()
    if branch_id is not None:
        queryset = queryset.filter(pk=branch_id)
    branch = queryset.first()
    if not branch:
        return {"error": "Branch not found"}

    return {
        "name": branch.name,
        "address": branch.address,
        "phone": branch.phone,
        "opening_time": branch.opening_time,
        "closing_time": branch.closing_time,
        "maximum_delivery_distance_km": branch.maximum_delivery_distance_km,
    }


def get_active_offers():
    from offer.selectors.offer_selector import get_active_offers as _get_active_offers

    return [
        {
            "title": offer.title,
            "offer_type": offer.offer_type,
            "discount_percentage": offer.discount_percentage,
            "discount_amount": offer.discount_amount,
            "min_order_amount": offer.min_order_amount,
            "start_datetime": offer.start_datetime,
            "end_datetime": offer.end_datetime,
        }
        for offer in _get_active_offers()[:10]
    ]


def _resolve_order_items(items):
    """Resolve requested menu item names to ``(Product, quantity)`` pairs.

    Returns ``(resolved, errors)``. Unmatched or ambiguous names are reported in
    ``errors`` with candidate names so the model can ask the customer to clarify
    instead of guessing.
    """
    from product.models import Product

    resolved = []
    errors = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        try:
            quantity = int(entry.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0
        if not name or quantity < 1:
            errors.append(
                {
                    "item": name or "(missing)",
                    "error": "A name and a quantity of at least 1 are required.",
                }
            )
            continue

        matches = list(Product.objects.filter(name__iexact=name)[:5])
        if not matches:
            terms = _meaningful_terms(name)
            if terms:
                condition = Q()
                for word in terms:
                    condition |= Q(name__icontains=word) | Q(
                        description__icontains=word
                    )
                matches = list(Product.objects.filter(condition)[:5])

        if not matches:
            errors.append({"item": name, "error": "No matching menu item."})
            continue

        exact = [p for p in matches if p.name.lower() == name.lower()]
        if len(matches) == 1:
            resolved.append((matches[0], quantity))
        elif len(exact) == 1:
            resolved.append((exact[0], quantity))
        else:
            errors.append(
                {
                    "item": name,
                    "error": "Ambiguous menu item.",
                    "candidates": [p.name for p in matches],
                }
            )
    return resolved, errors


def _order_summary(order):
    return {
        "order_number": order.order_number,
        "status": order.status,
        "order_type": order.order_type,
        "payment_type": order.payment_type,
        "total_amount": order.total_amount,
        "delivery_location": order.delivery_location,
        "items": [
            {
                "name": item.product.name if item.product else None,
                "quantity": item.quantity,
                "price": item.unit_price,
            }
            for item in order.items.all()
        ],
    }


def create_order(
    items=None,
    customer_name=None,
    phone_number=None,
    delivery_location=None,
    order_type="DELIVERY",
    payment_type="COD",
    special_note="",
    branch_id=None,
    context=None,
):
    """Create a real order on behalf of a chatting customer.

    Resolves menu item names to products, validates the contact details required
    for delivery, then delegates to ``OrderService.create_order`` so the normal
    notifications, activity log and WebSocket broadcasts fire.
    """
    from message.services.ai_order_settings import get_order_feature_flags

    flags = get_order_feature_flags(branch_id)

    if not flags.creation_enabled:
        return {"error": "Order creation is currently unavailable."}

    if not items:
        return {"error": "No items were provided."}

    order_type = str(order_type or "DELIVERY").upper()
    if order_type not in ("DELIVERY", "TAKEAWAY"):
        order_type = "DELIVERY"

    payment_type = str(payment_type or "COD").upper()
    if payment_type != "COD":
        return {
            "error": (
                "Only cash on delivery is supported from chat. Tell the customer "
                "they can pay in cash on delivery."
            )
        }

    phone = "".join(ch for ch in str(phone_number or "") if ch.isdigit())
    delivery_location = str(delivery_location or "").strip()
    if order_type == "DELIVERY":
        if len(phone) < 7:
            return {
                "error": (
                    "A phone number is required for delivery. Ask the customer "
                    "for their phone number."
                )
            }
        if not delivery_location:
            return {
                "error": (
                    "A delivery address is required for delivery. Ask the "
                    "customer for their delivery address."
                )
            }

    # Avoid duplicating an order created earlier in the same reply.
    if context is not None:
        existing_summary = context.get("created_order")
        if existing_summary:
            return {
                **existing_summary,
                "note": "This order was already created; do not create it again.",
            }

    from datetime import timedelta

    from django.utils import timezone

    from order.models import Order

    # Cross-turn duplicate guard within a short window (no conversation link).
    if phone:
        window = flags.dedup_window_minutes
        filters = {
            "phone_number__icontains": phone,
            "status": Order.OrderStatus.PENDING,
            "order_type": order_type,
            "created_at__gte": timezone.now() - timedelta(minutes=window),
        }
        if branch_id is not None:
            filters["branch_id"] = branch_id
        duplicate = Order.objects.filter(**filters).order_by("-created_at").first()
        if duplicate:
            summary = _order_summary(duplicate)
            if context is not None:
                context["created_order"] = summary
            return {
                **summary,
                "note": "An identical pending order already exists; do not create another.",
            }

    resolved, errors = _resolve_order_items(items)
    if errors:
        return {"error": "Could not resolve all items.", "items": errors}

    order_data = {
        "customer_name": (
            str(customer_name).strip()
            if customer_name
            else (context or {}).get("participant_name")
        ),
        "phone_number": phone or None,
        "delivery_location": delivery_location or None,
        "special_note": str(special_note or ""),
        "order_type": order_type,
        "payment_type": "COD",
    }
    if branch_id is not None:
        from account.models import Branch

        order_data["branch"] = Branch.objects.filter(pk=branch_id).first()

    cart_items_data = [
        {"product_id": product.id, "quantity": quantity}
        for product, quantity in resolved
    ]

    from order.services.order_service import OrderService

    order = OrderService.create_order(
        user=None, order_data=order_data, cart_items_data=cart_items_data
    )
    summary = _order_summary(order)
    if context is not None:
        context["created_order"] = summary
    return summary


def _find_order_by_number(order_number):
    """Look up an order by number, trying ORD_/EAT_ prefix variants."""
    from order.selectors.order_selector import get_order_by_number_with_relations

    order_number = str(order_number or "").strip()
    if not order_number:
        return None

    candidates = [order_number]
    upper = order_number.upper()
    if upper.startswith("ORD_"):
        candidates.append("EAT_" + upper[4:])
    elif upper.startswith("EAT_"):
        candidates.append("ORD_" + upper[4:])

    for candidate in candidates:
        order = get_order_by_number_with_relations(candidate)
        if order:
            return order
    return None


def cancel_order(order_number=None, phone_number=None, branch_id=None, context=None):
    """Cancel a customer's own order placed from chat.

    Ownership is verified by matching the phone number stored on the order with
    the number the customer provides. Only orders in a cancellable state and
    within the configured time window can be cancelled.
    """
    from datetime import timedelta

    from django.utils import timezone

    from message.services.ai_order_settings import get_order_feature_flags
    from order.models import Order

    flags = get_order_feature_flags(branch_id)

    if not flags.cancellation_enabled:
        return {"error": "Order cancellation is currently unavailable."}

    order_number = str(order_number or "").strip()
    if not order_number:
        return {"error": "An order number is required to cancel an order."}

    phone = "".join(ch for ch in str(phone_number or "") if ch.isdigit())
    if len(phone) < 7:
        return {
            "error": (
                "A phone number is required to verify the order before "
                "cancelling. Ask the customer for the phone number used for the "
                "order."
            )
        }

    order = _find_order_by_number(order_number)
    if not order:
        return {
            "error": "Order not found. Ask the customer to check the order number."
        }

    # Ownership: the stored phone must match the number the customer provided.
    stored_phone = "".join(ch for ch in str(order.phone_number or "") if ch.isdigit())
    if not stored_phone or phone[-7:] != stored_phone[-7:]:
        return {
            "error": (
                "The order number and phone number do not match. Do not cancel "
                "anything; ask the customer to re-check both."
            )
        }

    if branch_id is not None and order.branch_id != branch_id:
        return {
            "error": (
                "The order number and phone number do not match. Do not cancel "
                "anything; ask the customer to re-check both."
            )
        }

    if order.status == Order.OrderStatus.CANCELLED:
        return {
            "error": "This order has already been cancelled.",
            "order_number": order.order_number,
        }

    cancellable_statuses = {
        Order.OrderStatus.PENDING,
        Order.OrderStatus.CONFIRMED,
        Order.OrderStatus.PREPARING,
    }
    if order.status not in cancellable_statuses:
        return {
            "error": (
                f"This order can no longer be cancelled because it is already "
                f"{order.get_status_display()}. Tell the customer to contact the "
                "restaurant."
            ),
            "order_number": order.order_number,
            "status": order.status,
        }

    window = flags.cancellation_window_minutes
    if order.created_at < timezone.now() - timedelta(minutes=window):
        return {
            "error": (
                f"Orders can only be cancelled within {window} minutes of being "
                "placed. Tell the customer the cancellation time limit has passed "
                "and to contact the restaurant."
            ),
            "order_number": order.order_number,
            "window_minutes": window,
        }

    from order.services.order_service import OrderService

    OrderService.update_order_status(
        order,
        Order.OrderStatus.CANCELLED,
        comment="Cancelled by customer via chat",
    )
    return {
        "order_number": order.order_number,
        "status": order.status,
        "total_amount": order.total_amount,
        "message": "The order has been cancelled.",
    }


def get_enabled_tool_schemas(branch_id=None):
    """Return the tool schemas currently available to the model.

    ``create_order`` and ``cancel_order`` are withheld unless their respective
    AI order features are explicitly enabled (respecting per-branch overrides).
    """
    from message.services.ai_order_settings import get_order_feature_flags

    flags = get_order_feature_flags(branch_id)
    schemas = list(TOOL_SCHEMAS)
    if not flags.creation_enabled:
        schemas = [
            schema
            for schema in schemas
            if schema["function"]["name"] != "create_order"
        ]
    if not flags.cancellation_enabled:
        schemas = [
            schema
            for schema in schemas
            if schema["function"]["name"] != "cancel_order"
        ]
    return schemas


_EXECUTORS = {
    "search_faq": search_faq,
    "search_menu": search_menu,
    "get_order_status": get_order_status,
    "find_recent_orders": find_recent_orders,
    "get_branch_info": get_branch_info,
    "get_active_offers": get_active_offers,
    "create_order": create_order,
    "cancel_order": cancel_order,
}


def execute_tool(
    name: str, arguments: Dict[str, Any], branch_id=None, context: Optional[dict] = None
) -> str:
    """Run a tool by name and return its result as a JSON string.

    Unknown tools and exceptions produce an ``{"error": ...}`` payload so the
    model can recover instead of the whole reply failing.
    """
    function = _EXECUTORS.get(name)
    if function is None:
        return json.dumps({"error": f"Unknown tool: {name}"})

    if not isinstance(arguments, dict):
        arguments = {}

    accepted = inspect.signature(function).parameters
    if branch_id is not None and "branch_id" in accepted:
        arguments = {**arguments, "branch_id": branch_id}
    if context is not None and "context" in accepted:
        arguments = {**arguments, "context": context}
    filtered = {key: value for key, value in arguments.items() if key in accepted}

    try:
        result = function(**filtered)
    except Exception as exc:  # noqa: BLE001 - surface failures to the model
        logger.warning("Tool %s failed: %s", name, exc, exc_info=True)
        return json.dumps({"error": str(exc)})

    return json.dumps(result, default=str)
