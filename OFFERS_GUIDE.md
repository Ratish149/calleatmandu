# Food Delivery Offer & Promotion Guide (CallEatMandu)

This guide documents all possible types of offers and promo codes supported by the **CallEatMandu** system, including step-by-step instructions and sample JSON payloads for creating and checking them via the API.

---

## Table of Contents
1. [Overview of Offer Capabilities](#1-overview-of-offer-capabilities)
2. [Supported Offer Types](#2-supported-offer-types)
3. [Supported Scope & Targets](#3-supported-scope--targets)
4. [Promo Codes vs. Auto-Applied Offers](#4-promo-codes-vs-auto-applied-offers)
5. [Happy Hours & Validity Constraints](#5-happy-hours--validity-constraints)
6. [How to Create Offers (API Payload Examples)](#6-how-to-create-offers-api-payload-examples)
7. [How to Check/Validate Offers during Checkout](#7-how-to-checkvalidate-offers-during-checkout)

---

## 1. Overview of Offer Capabilities

The `offer` app supports a highly flexible promotion engine suitable for online food delivery platforms. You can create:
- **Order/Cart-level discounts** (e.g. 15% off orders above Rs. 1,000).
- **Category & Subcategory discounts** (e.g. Flat Rs. 100 off on all Bakery items).
- **Product-specific deals** (e.g. 20% off on Large Chicken Pizza).
- **Buy X Get Y (BOGO) Deals** (e.g. Buy 1 Burger get 1 Coke free, or Buy 2 Pizzas get Garlic Bread at 50% off).
- **Free Delivery Promotions** (e.g. Free delivery on orders over Rs. 500).
- **Happy Hours & Time Slot Deals** (e.g. Lunch hour discount valid only between 12:00 PM – 3:00 PM).
- **Promo Codes & Vouchers** (e.g. Coupon codes like `WELCOME50` or `SUMMER2026`).

---

## 2. Supported Offer Types

| `offer_type` | Description | Relevant Fields Required |
| :--- | :--- | :--- |
| `PERCENTAGE` | Discount calculated as a percentage of total price. Can cap max discount. | `discount_percentage`, `max_discount_amount` (optional) |
| `FLAT` | Fixed amount subtracted from total order. | `discount_amount` |
| `BUY_X_GET_Y` | Buy a specific item and get another item for free or at a discount. | `buy_product`, `buy_quantity`, `get_product`, `get_quantity`, `get_discount_percentage` |
| `FREE_DELIVERY` | Waives delivery charge when cart conditions are met. | `min_order_amount` |
| `COMBO` | Special price or deal for ordering bundle/combo items. | `products`, `discount_amount` / `discount_percentage` |

---

## 3. Supported Scope & Targets

| `scope` | Applies To | Relevant Foreign Key Fields |
| :--- | :--- | :--- |
| `CART` | Entire order / cart total. | None (applies to whole cart) |
| `CATEGORY` | All food items within a specific category. | `category` (e.g. Category ID for Bakery) |
| `SUBCATEGORY` | All items within a specific subcategory. | `subcategory` (e.g. Subcategory ID for Cakes) |
| `PRODUCT` | One or more specific products. | `products` (List of Product IDs) |

---

## 4. Promo Codes vs. Auto-Applied Offers

- **Auto-Applied Offers**: If an offer has **no** `PromoCode` attached, the system automatically checks and applies the best active offer to eligible carts during checkout.
- **Promo Code Offers**: If a `PromoCode` (e.g. `MOMO50`) is linked to an offer, the customer must manually enter the coupon code to receive the discount.

Multiple promo codes can point to a single offer (e.g., `INFLUENCER1`, `INFLUENCER2` both granting 15% discount).

---

## 5. Happy Hours & Validity Constraints

Offers and Promo Codes can be restricted using:
- **`start_datetime` & `end_datetime`**: Valid date range (e.g. 2026-08-01 to 2026-08-31).
- **`start_time` & `end_time`**: Daily time window for Happy Hours (e.g. `12:00:00` to `15:00:00`).
- **`min_order_amount`**: Minimum cart subtotal required (e.g. Rs. 500).
- **`max_total_usage`**: Total number of times this offer/promo code can be redeemed overall.
- **`max_usage_per_user`**: Max times an individual logged-in user can redeem it.

---

## 6. How to Create Offers (API Payload Examples)

### Scenario A: Flat 15% Off Cart Above Rs. 1000 (Max Discount Rs. 300)
`POST /api/offers/`
```json
{
  "title": "Monsoon Mega Sale",
  "description": "Get 15% off on orders above Rs. 1000 up to Rs. 300.",
  "banner_image": "offers/banners/monsoon_sale_banner.jpg",
  "offer_type": "PERCENTAGE",

  "scope": "CART",
  "discount_percentage": 15.0,
  "max_discount_amount": 300.0,
  "min_order_amount": 1000.0,
  "is_active": true
}
```


---

### Scenario B: Buy 1 Momo Get 1 Coke Free (BOGO)
`POST /api/offers/`
```json
{
  "title": "Buy 1 Steam Momo Get 1 Coke Free",
  "description": "Buy 1 Steam Momo and get a 250ml Coke absolutely free!",
  "offer_type": "BUY_X_GET_Y",
  "scope": "PRODUCT",
  "buy_product": 5,
  "buy_quantity": 1,
  "get_product": 12,
  "get_quantity": 1,
  "get_discount_percentage": 100.0,
  "is_active": true
}
```

---

### Scenario C: Lunch Happy Hour (Flat Rs. 100 Off from 12 PM to 3 PM)
`POST /api/offers/`
```json
{
  "title": "Lunch Happy Hour Special",
  "description": "Flat Rs. 100 off on all lunch orders between 12 PM and 3 PM.",
  "offer_type": "FLAT",
  "scope": "CART",
  "discount_amount": 100.0,
  "min_order_amount": 400.0,
  "start_time": "12:00:00",
  "end_time": "15:00:00",
  "is_active": true
}
```

---

### Scenario D: Create a Coupon Code linked to an Offer
1. Create the Offer (or use an existing offer ID):
   `POST /api/offers/` (Returns `id: 3`)

2. Create the Promo Code linking to Offer ID 3:
   `POST /api/promo-codes/`
```json
{
  "code": "WELCOME50",
  "description": "Welcome coupon for new users",
  "offer": 3,
  "max_usage_per_user": 1,
  "max_total_usage": 500,
  "is_active": true
}
```

---

## 7. How to Check/Validate Offers during Checkout

Frontend apps send cart contents and optional promo code to the check endpoint:

`POST /api/offers/check/`

### Request Payload:
```json
{
  "promo_code": "WELCOME50",
  "cart_total": 850.0,
  "cart_items": [
    {
      "product_id": 5,
      "category_id": 2,
      "price": 250.0,
      "quantity": 2
    },
    {
      "product_id": 10,
      "category_id": 4,
      "price": 350.0,
      "quantity": 1
    }
  ]
}
```

### Successful Response:
```json
{
  "is_valid": true,
  "message": "Offer applied successfully.",
  "offer_id": 3,
  "offer_title": "Welcome Special Offer",
  "promo_code": "WELCOME50",
  "discount_amount": 150.0,
  "final_amount": 700.0,
  "reward_details": {}
}
```

---

## API Summary Quick Reference

- **List / Create Offers**: `GET` / `POST` `/api/offers/`
- **Update / Delete Offer**: `GET` / `PUT` / `DELETE` `/api/offers/<id>/`
- **List / Create Promo Codes**: `GET` / `POST` `/api/promo-codes/`
- **Update / Delete Promo Code**: `GET` / `PUT` / `DELETE` `/api/promo-codes/<id>/`
- **Verify & Calculate Discount**: `POST` `/api/offers/check/`
