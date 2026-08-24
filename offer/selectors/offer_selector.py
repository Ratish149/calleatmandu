from django.utils import timezone

from offer.models import Offer


def get_active_offers(now=None):
    """
    Fetch all currently active offers with prefetched products to avoid N+1 queries.
    Validates active flag, date range, and happy hour time slot.
    """
    if now is None:
        now = timezone.now()

    queryset = Offer.objects.filter(is_active=True).prefetch_related("products")

    active_offers = []
    for offer in queryset:
        if offer.start_datetime and now < offer.start_datetime:
            continue
        if offer.end_datetime and now > offer.end_datetime:
            continue
        if offer.start_time and offer.end_time:
            current_time = now.time()
            if not (offer.start_time <= current_time <= offer.end_time):
                continue
        active_offers.append(offer)

    return active_offers


def calculate_product_offer_price(product, active_offers):
    """
    Calculates the best offer price for a product based on applicable active offers
    (scoped to product, subcategory, category, or cart/any).

    Returns:
        float: The discounted price rounded to 2 decimal places if an offer applies
               and reduces the price, otherwise None.
    """
    if not product or not product.price:
        return None

    original_price = float(product.price)
    best_price = original_price

    for offer in active_offers:
        applies = False

        if offer.scope == Offer.ScopeType.PRODUCT:
            product_ids = {p.id for p in offer.products.all()}
            if product.id in product_ids:
                applies = True

        elif offer.scope == Offer.ScopeType.CATEGORY:
            if (
                offer.category_id
                and product.category_id
                and offer.category_id == product.category_id
            ):
                applies = True

        elif offer.scope == Offer.ScopeType.SUBCATEGORY:
            if (
                offer.subcategory_id
                and product.sub_category_id
                and offer.subcategory_id == product.sub_category_id
            ):
                applies = True

        elif offer.scope == Offer.ScopeType.CART:
            applies = True

        if applies:
            if offer.offer_type == Offer.OfferType.PERCENTAGE:
                discount = (original_price * offer.discount_percentage) / 100.0
                if offer.max_discount_amount and discount > offer.max_discount_amount:
                    discount = offer.max_discount_amount
                discounted_price = max(0.0, original_price - discount)
                if discounted_price < best_price:
                    best_price = discounted_price

            elif offer.offer_type == Offer.OfferType.FLAT:
                discount = offer.discount_amount
                discounted_price = max(0.0, original_price - discount)
                if discounted_price < best_price:
                    best_price = discounted_price

    if best_price < original_price:
        return round(best_price, 2)

    return None
