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


_EXECUTORS = {
    "search_faq": search_faq,
    "search_menu": search_menu,
    "get_order_status": get_order_status,
    "find_recent_orders": find_recent_orders,
    "get_branch_info": get_branch_info,
    "get_active_offers": get_active_offers,
}


def execute_tool(
    name: str, arguments: Dict[str, Any], branch_id=None
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
    filtered = {key: value for key, value in arguments.items() if key in accepted}

    try:
        result = function(**filtered)
    except Exception as exc:  # noqa: BLE001 - surface failures to the model
        logger.warning("Tool %s failed: %s", name, exc, exc_info=True)
        return json.dumps({"error": str(exc)})

    return json.dumps(result, default=str)
