# Food Delivery Offer & Promotion Guide (CallEatMandu)

This guide documents all possible types of offers and promo codes supported by the **CallEatMandu** system, including step-by-step instructions and sample JSON payloads for creating, checking, and validating them via the API.

---

## Table of Contents
1. [Overview of Offer & Promo Code Capabilities](#1-overview-of-offer--promo-code-capabilities)
2. [Promo Code Architecture (`PromoCode`)](#2-promo-code-architecture-promocode)
3. [Supported Offer Types (`Offer`)](#3-supported-offer-types-offer)
4. [Supported Scope & Targets](#4-supported-scope--targets)
5. [How to Create Promo Codes (API Payload Examples)](#5-how-to-create-promo-codes-api-payload-examples)
6. [How to Check & Validate Promo Codes](#6-how-to-check--validate-promo-codes)
7. [How to Evaluate Cart Deals](#7-how-to-evaluate-cart-deals)

---

## 1. Overview of Offer & Promo Code Capabilities

The system supports two complementary promotion mechanisms:
1. **Standalone Promo Codes (`PromoCode`)**: Custom coupon codes (e.g. `WELCOME50`, `FLAT100`, `SUPER15`) with direct discount configuration (`AMOUNT` or `PERCENTAGE`), validity dates, overall usage caps, and per-user usage limits.
2. **Offers Engine (`Offer`)**: Complex deals including Buy-X-Get-Y (BOGO), Free Delivery, Category/Subcategory/Product specific discounts, and Happy Hour deals.

---

## 2. Promo Code Architecture (`PromoCode`)

Each `PromoCode` is configured directly with its own discount type and amount:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `code` | String | Unique coupon code (e.g. `SUMMER50`). Auto-converted to uppercase. |
| `description` | String | Optional description of the promotion. |
| `promo_type` | String (`AMOUNT` \| `PERCENTAGE`) | Type of discount: `AMOUNT` (Fixed amount in Rs.) or `PERCENTAGE` (Rate between 0–100%). |
| `amount` | Float | Discount value (e.g. `100.0` for Rs. 100 flat, or `15.0` for 15%). |
| `max_total_usage` | Integer (optional) | Maximum times this promo code can be redeemed overall. |
| `max_usage_per_user` | Integer (default: 1) | Maximum times an individual logged-in user can redeem it. |
| `start_datetime` | DateTime (optional) | Start date & time when promo code becomes valid. |
| `end_datetime` | DateTime (optional) | Expiry date & time after which promo code is invalid. |
| `is_active` | Boolean (default: true) | Master active toggle. |

---

## 3. Supported Offer Types (`Offer`)

| `offer_type` | Description | Relevant Fields Required |
| :--- | :--- | :--- |
| `PERCENTAGE` | Discount calculated as a percentage of total price. Can cap max discount. | `discount_percentage`, `max_discount_amount` (optional) |
| `FLAT` | Fixed amount subtracted from total order. | `discount_amount` |
| `BUY_X_GET_Y` | Buy a specific item and get another item for free or at a discount. | `buy_product`, `buy_quantity`, `get_product`, `get_quantity`, `get_discount_percentage` |
| `FREE_DELIVERY` | Waives delivery charge when cart conditions are met. | `min_order_amount` |
| `COMBO` | Special price or deal for ordering bundle/combo items. | `products`, `discount_amount` / `discount_percentage` |

---

## 4. Supported Scope & Targets

| `scope` | Applies To | Relevant Foreign Key Fields |
| :--- | :--- | :--- |
| `CART` | Entire order / cart total. | None (applies to whole cart) |
| `CATEGORY` | All food items within a specific category. | `category` (Category ID) |
| `SUBCATEGORY` | All items within a specific subcategory. | `subcategory` (Subcategory ID) |
| `PRODUCT` | One or more specific products. | `products` (List of Product IDs) |

---

## 5. How to Create Promo Codes (API Payload Examples)

### Scenario A: Create a Flat Rs. 100 Off Promo Code
`POST /api/promo-codes/`
```json
{
  "code": "FLAT100",
  "description": "Flat Rs. 100 off on all orders",
  "promo_type": "AMOUNT",
  "amount": 100.0,
  "max_total_usage": 500,
  "max_usage_per_user": 1,
  "is_active": true
}
```

---

### Scenario B: Create a 20% Off Promo Code
`POST /api/promo-codes/`
```json
{
  "code": "SAVE20",
  "description": "20% percentage discount promo code",
  "promo_type": "PERCENTAGE",
  "amount": 20.0,
  "max_total_usage": 1000,
  "max_usage_per_user": 2,
  "start_datetime": "2026-08-01T00:00:00Z",
  "end_datetime": "2026-08-31T23:59:59Z",
  "is_active": true
}
```

---

## 6. How to Check & Validate Promo Codes

Frontend applications can send a promo code string (and optional cart total) to validate it and get its calculated discount:

`POST /api/promo-codes/check/`

**Headers:**
`Authorization: Bearer <access_token>`

### Request Payload:
```json
{
  "code": "FLAT100",
  "cart_total": 850.0
}
```

### Successful Response (`HTTP 200 OK`):
```json
{
  "is_valid": true,
  "message": "Promo code is valid.",
  "promo_code": {
    "id": 1,
    "code": "FLAT100",
    "description": "Flat Rs. 100 off on all orders",
    "promo_type": "AMOUNT",
    "amount": 100.0,
    "max_total_usage": 500,
    "max_usage_per_user": 1,
    "current_usage_count": 12,
    "start_datetime": null,
    "end_datetime": null,
    "calculated_discount": 100.0,
    "final_amount": 750.0
  }
}
```

---

## 7. How to Evaluate Cart Deals

`POST /api/offers/check/`

**Headers:**
`Authorization: Bearer <access_token>`

### Request Payload:
```json
{
  "promo_code": "FLAT100",
  "cart_total": 850.0,
  "cart_items": [
    {
      "product_id": 5,
      "category_id": 2,
      "price": 250.0,
      "quantity": 2
    }
  ]
}
```

### Response:
```json
{
  "is_valid": true,
  "message": "Promo code applied successfully.",
  "offer_id": null,
  "offer_title": "Promo Code: FLAT100",
  "promo_code": "FLAT100",
  "discount_amount": 100.0,
  "final_amount": 750.0,
  "reward_details": {
    "promo_type": "AMOUNT",
    "amount": 100.0
  }
}
```

---

## API Summary Quick Reference

- **List / Create Promo Codes**: `GET` / `POST` `/api/promo-codes/`
- **Update / Delete Promo Code**: `GET` / `PUT` / `DELETE` `/api/promo-codes/<id>/`
- **Check & Validate Promo Code**: `POST /api/promo-codes/check/`
- **List / Create Offers**: `GET` / `POST` `/api/offers/`
- **Update / Delete Offer**: `GET` / `PUT` / `DELETE` `/api/offers/<id>/`
- **Verify & Calculate Cart Deals**: `POST /api/offers/check/`
