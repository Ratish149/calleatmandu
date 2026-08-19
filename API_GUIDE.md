# CallEatMandu — API Guide

Base URL: `http://localhost:8000/api`

---

## 1. Product

### 1.1 Create a Category

```http
POST /api/categories/
Content-Type: application/json
```

**Body**
```json
{
  "name": "Fast Food"
}
```

**Response `201`**
```json
{
  "id": 1,
  "name": "Fast Food",
  "slug": "fast-food"
}
```

---

### 1.2 Create a Subcategory

```http
POST /api/subcategories/
Content-Type: application/json
```

**Body**
```json
{
  "name": "Burgers",
  "category": 1
}
```

**Response `201`**
```json
{
  "id": 1,
  "name": "Burgers",
  "slug": "burgers",
  "category": 1
}
```

---

### 1.3 Create a Product (with Extras & Images)

Products, extras, and additional images are created in **one single request** using `multipart/form-data`.

```http
POST /api/products/
Content-Type: multipart/form-data
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | text | ✅ | Auto-generates `slug` |
| `description` | text | ✅ | |
| `price` | number | ✅ | Base price in NPR |
| `thumbnail_image` | file | ✅ | Main product thumbnail |
| `category` | number (id) | ❌ | |
| `sub_category` | number (id) | ❌ | |
| `extras` | text (JSON string) | ❌ | Array of extras — see format below |
| `images` | file (multiple) | ❌ | Send multiple `images` fields for extra gallery images |

**`extras` format** — send as a JSON string:
```
[{"name": "Extra Cheese", "additional_price": 50}, {"name": "Crispy Fries", "additional_price": 80}]
```

**cURL example**
```bash
curl -X POST http://localhost:8000/api/products/ \
  -F "name=Chicken Burger" \
  -F "description=Juicy chicken patty with fresh veggies." \
  -F "price=350" \
  -F "category=1" \
  -F "sub_category=1" \
  -F "thumbnail_image=@/path/to/thumb.jpg" \
  -F 'extras=[{"name":"Extra Cheese","additional_price":50},{"name":"Crispy Fries","additional_price":80}]' \
  -F "images=@/path/to/img1.jpg" \
  -F "images=@/path/to/img2.jpg"
```

**Response `201`** — full product detail returned immediately:
```json
{
  "id": 3,
  "name": "Chicken Burger",
  "slug": "chicken-burger",
  "description": "Juicy chicken patty with fresh veggies.",
  "price": 350.0,
  "thumbnail_image": "/media/product/thumbnail/chicken-burger.jpg",
  "category": 1,
  "category_name": "Fast Food",
  "sub_category": 1,
  "sub_category_name": "Burgers",
  "extras": [
    { "id": 1, "name": "Extra Cheese", "additional_price": 50.0 },
    { "id": 2, "name": "Crispy Fries",  "additional_price": 80.0 }
  ],
  "images": [
    { "id": 1, "image": "/media/product/images/img1.jpg" },
    { "id": 2, "image": "/media/product/images/img2.jpg" }
  ],
  "created_at": "2026-08-19T10:00:00Z",
  "updated_at": "2026-08-19T10:00:00Z"
}
```

---

### 1.4 Get Product Detail (with Extras & Images)

```http
GET /api/products/<slug>/
```

**Example**
```http
GET /api/products/chicken-burger/
```

**Response `200`**
```json
{
  "id": 3,
  "name": "Chicken Burger",
  "slug": "chicken-burger",
  "description": "Juicy chicken patty with fresh veggies.",
  "price": 350.0,
  "thumbnail_image": "/media/product/thumbnail/chicken-burger.jpg",
  "category": 1,
  "category_name": "Fast Food",
  "sub_category": 1,
  "sub_category_name": "Burgers",
  "extras": [
    { "id": 1, "name": "Extra Cheese", "additional_price": 50.0 },
    { "id": 2, "name": "Crispy Fries", "additional_price": 80.0 }
  ],
  "images": [
    { "id": 1, "image": "/media/product/images/burger-side.jpg" }
  ],
  "created_at": "2026-08-19T10:00:00Z",
  "updated_at": "2026-08-19T10:00:00Z"
}
```

---

### 1.5 Add an Extra to a Product

```http
POST /api/products/<slug>/extras/
Content-Type: application/json
```

**Body**
```json
{
  "name": "Extra Cheese",
  "additional_price": 50.0
}
```

**Response `201`**
```json
{
  "id": 1,
  "product": 3,
  "name": "Extra Cheese",
  "additional_price": 50.0
}
```

---

### 1.6 Update / Delete an Extra

```http
PATCH  /api/products/<slug>/extras/<pk>/
DELETE /api/products/<slug>/extras/<pk>/
```

**PATCH body (partial update)**
```json
{
  "additional_price": 60.0
}
```

---

## 2. Order

### 2.1 Create an Order

The server automatically:
- Finds the **nearest active branch** from the provided coordinates
- Applies any active **offer or promo code**
- Generates a unique **`order_number`** like `EAT_482931`

> ⚠️ Never send calculated prices — the server computes everything.

```http
POST /api/orders/
Content-Type: application/json
```

**Minimal body (no extras, no promo)**
```json
{
  "customer_name": "Ram Thapa",
  "phone_number": "9841000000",
  "delivery_location": "Thamel, Kathmandu",
  "latitude": 27.7152,
  "longitude": 85.3123,
  "items": [
    {
      "product_id": 3,
      "quantity": 2
    }
  ]
}
```

**Full body (with extras + promo code)**
```json
{
  "customer_name": "Ram Thapa",
  "phone_number": "9841000000",
  "delivery_location": "Thamel, Kathmandu",
  "latitude": 27.7152,
  "longitude": 85.3123,
  "special_note": "Less spicy please",
  "promo_code": "SAVE20",
  "items": [
    {
      "product_id": 3,
      "quantity": 2,
      "extras": [
        { "extra_id": 1 },
        { "extra_id": 2 }
      ]
    },
    {
      "product_id": 5,
      "quantity": 1
    }
  ]
}
```

> **Extra validation**: each `extra_id` must belong to its `product_id` — otherwise the API returns `400`.

**Response `201`**
```json
{
  "id": 10,
  "order_number": "EAT_482931",
  "user": null,
  "branch": 2,
  "branch_name": "Thamel Branch",
  "customer_name": "Ram Thapa",
  "phone_number": "9841000000",
  "delivery_location": "Thamel, Kathmandu",
  "latitude": 27.7152,
  "longitude": 85.3123,
  "special_note": "Less spicy please",
  "subtotal": 960.0,
  "discount_amount": 192.0,
  "delivery_fee": 0.0,
  "total_amount": 768.0,
  "promo_code": 3,
  "offer": null,
  "status": "PENDING",
  "items": [
    {
      "id": 21,
      "product": 3,
      "product_name": "Chicken Burger",
      "quantity": 2,
      "unit_price": 350.0,
      "extras_price": 130.0,
      "subtotal": 960.0,
      "selected_extras": [
        { "id": 1, "extra": 1, "extra_name": "Extra Cheese", "additional_price": 50.0 },
        { "id": 2, "extra": 2, "extra_name": "Crispy Fries",  "additional_price": 80.0 }
      ]
    }
  ],
  "created_at": "2026-08-19T10:00:00Z",
  "updated_at": "2026-08-19T10:00:00Z"
}
```

---

### 2.2 Get Order Detail

```http
GET /api/orders/<order_number>/
```

**Example**
```http
GET /api/orders/EAT_482931/
```

Returns the same structure as the create response above.

---

### 2.3 Update Order Status

```http
PATCH /api/orders/<order_number>/
Content-Type: application/json
Authorization: Bearer <token>
```

**Body**
```json
{
  "status": "CONFIRMED"
}
```

**Available statuses**

| Value | Meaning |
|---|---|
| `PENDING` | Order placed, awaiting confirmation |
| `CONFIRMED` | Branch confirmed the order |
| `PREPARING` | Kitchen is preparing |
| `OUT_FOR_DELIVERY` | Rider on the way |
| `DELIVERED` | Order delivered |
| `CANCELLED` | Order cancelled |

---

### 2.4 List & Filter Orders

```http
GET /api/orders/
GET /api/orders/?status=PENDING
GET /api/orders/?branch=2
GET /api/orders/?phone_number=9841000000
GET /api/orders/?customer_name=Ram
```

---

## 3. Price Calculation

All calculations happen server-side:

```
item_subtotal  = (unit_price + extras_price_per_unit) × quantity
order_subtotal = Σ item_subtotals
total_amount   = order_subtotal − discount_amount + delivery_fee
```

**Example walkthrough**

```
Chicken Burger    350 base
  + Extra Cheese   50
  + Crispy Fries   80
  = 480 per unit × 2 qty = 960

Promo SAVE20 → 20% off → discount = 192
Total = 960 − 192 + 0 delivery = 768
```

---

## 4. Quick Reference

| Action | Method | URL |
|---|---|---|
| List categories | `GET` | `/api/categories/` |
| Create category | `POST` | `/api/categories/` |
| Category detail | `GET/PUT/PATCH/DELETE` | `/api/categories/<pk>/` |
| List subcategories | `GET` | `/api/subcategories/` |
| Create subcategory | `POST` | `/api/subcategories/` |
| Subcategory detail | `GET/PUT/PATCH/DELETE` | `/api/subcategories/<pk>/` |
| List products | `GET` | `/api/products/` |
| Create product | `POST` | `/api/products/` |
| Product detail | `GET/PUT/PATCH/DELETE` | `/api/products/<slug>/` |
| List product extras | `GET` | `/api/products/<slug>/extras/` |
| Add extra to product | `POST` | `/api/products/<slug>/extras/` |
| Extra detail | `GET/PUT/PATCH/DELETE` | `/api/products/<slug>/extras/<pk>/` |
| List orders | `GET` | `/api/orders/` |
| Create order | `POST` | `/api/orders/` |
| Order detail | `GET/PUT/PATCH/DELETE` | `/api/orders/<order_number>/` |
