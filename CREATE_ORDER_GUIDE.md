# Order Creation Guide

This document details how to create an order with order items and product extras using the **CallEatMandu** REST API.

---

## 1. Endpoint Overview

* **Endpoint URL:** `/api/orders/`
* **HTTP Method:** `POST`
* **Content-Type:** `application/json`
* **Authentication:** **Required** (`IsAuthenticated`). An `Authorization: Bearer <token>` header must be provided to place an order.

---

## 2. Request Payload Schema

### Top-Level Fields

| Field Name | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `customer_name` | String | **Yes** | Full name of the customer |
| `phone_number` | String | **Yes** | Contact phone number |
| `delivery_location` | String | **Yes** | Street address or landmark for delivery |
| `latitude` | Float | **Yes** | Delivery location latitude (used for nearest branch assignment) |
| `longitude` | Float | **Yes** | Delivery location longitude (used for nearest branch assignment) |
| `special_note` | String | No | Cooking or delivery instructions |
| `promo_code` | String | No | Case-insensitive promo code string (e.g. `WELCOME10`) |
| `items` | Array | **Yes** | List of order items (minimum 1 item) |

---

### `items` Object Schema

| Field Name | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `product_id` | Integer | **Yes** | ID of the product to order |
| `quantity` | Integer | **Yes** | Quantity to order (minimum `1`) |
| `extras` | Array | No | List of selected extra options for this product |

---

### `extras` Object Schema

| Field Name | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `extra_id` | Integer | **Yes** | ID of the `ProductExtra` associated with the product |

---

## 3. Business & Calculation Logic

When an order request is posted to `POST /api/orders/`, `OrderService.create_order` performs the following automated steps:

1. **Branch Assignment:** Automatically identifies and assigns the nearest active branch based on `latitude` and `longitude`.
2. **Product & Extra Validation:**
   * Validates that `product_id` exists.
   * Validates that each `extra_id` exists and belongs directly to the specified `product_id`.
3. **Price Calculation:**
   * **`extras_price`**: Sum of `additional_price` of all selected extras per item unit.
   * **`item_subtotal`**: `(unit_price + extras_price) * quantity`.
   * **`subtotal`**: Sum of all `item_subtotal` values.
4. **Offer & Promo Code Evaluation:** Automatically evaluates active cart offers or promo codes and calculates `discount_amount`.
5. **Final Total:** `total_amount = max(0, subtotal - discount_amount + delivery_fee)`.
6. **Price Snapshot:** Prices for products and extras are snapshotted inside `OrderItem` and `OrderItemExtra` to preserve historical order accuracy even if menu prices change later.

---

## 4. Example Request Payloads

### Example 1: Full Order with Extras and Promo Code

```json
{
  "customer_name": "Ram Bahadur",
  "phone_number": "9841234567",
  "delivery_location": "New Road, Kathmandu",
  "latitude": 27.700769,
  "longitude": 85.311658,
  "special_note": "Please make it extra spicy and call upon arrival.",
  "promo_code": "SAVE50",
  "items": [
    {
      "product_id": 12,
      "quantity": 2,
      "extras": [
        {
          "extra_id": 3
        },
        {
          "extra_id": 5
        }
      ]
    },
    {
      "product_id": 8,
      "quantity": 1,
      "extras": []
    }
  ]
}
```

---

### Example 2: Simple Order without Extras

```json
{
  "customer_name": "Sita Sharma",
  "phone_number": "9801122334",
  "delivery_location": "Jhamsikhel, Lalitpur",
  "latitude": 27.6766,
  "longitude": 85.3135,
  "items": [
    {
      "product_id": 4,
      "quantity": 1
    }
  ]
}
```

---

## 5. Example Response Payloads

### HTTP 201 Created (Success)

```json
{
  "id": 45,
  "order_number": "EAT_482931",
  "user": 3,
  "branch": 1,
  "branch_name": "Kathmandu Main Branch",
  "customer_name": "Ram Bahadur",
  "phone_number": "9841234567",
  "delivery_location": "New Road, Kathmandu",
  "latitude": 27.700769,
  "longitude": 85.311658,
  "special_note": "Please make it extra spicy and call upon arrival.",
  "subtotal": 650.0,
  "discount_amount": 50.0,
  "delivery_fee": 0.0,
  "total_amount": 600.0,
  "promo_code": 2,
  "offer": 1,
  "status": "PENDING",
  "items": [
    {
      "id": 101,
      "product": 12,
      "product_name": "Chicken MoMo",
      "quantity": 2,
      "unit_price": 250.0,
      "extras_price": 50.0,
      "subtotal": 600.0,
      "selected_extras": [
        {
          "id": 201,
          "extra": 3,
          "extra_name": "Extra Cheese",
          "additional_price": 30.0
        },
        {
          "id": 202,
          "extra": 5,
          "extra_name": "Extra Spicy Chutney",
          "additional_price": 20.0
        }
      ]
    },
    {
      "id": 102,
      "product": 8,
      "product_name": "Coca-Cola 500ml",
      "quantity": 1,
      "unit_price": 50.0,
      "extras_price": 0.0,
      "subtotal": 50.0,
      "selected_extras": []
    }
  ],
  "created_at": "2026-08-25T13:20:00Z",
  "updated_at": "2026-08-25T13:20:00Z"
}
```

---

### HTTP 400 Bad Request (Validation Errors)

#### 1. Extra Does Not Belong to Product

```json
{
  "error": "Extra 'Extra Cheese' does not belong to product 'Coca-Cola 500ml'."
}
```

#### 2. Invalid Product ID

```json
{
  "error": "Product with ID 999 does not exist."
}
```

#### 3. Empty Items Array

```json
{
  "items": [
    "This list may not be empty."
  ]
}
```
