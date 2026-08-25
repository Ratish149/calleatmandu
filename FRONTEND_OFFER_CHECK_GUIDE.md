# Frontend Offer & Promo Code Check Integration Guide

This guide explains how to integrate the **Offer & Promo Code Validation APIs** (`POST /api/promo-codes/check/` and `POST /api/offers/check/`) into your frontend cart / checkout component (React, Next.js, Vue, or React Native).

---

## 1. Available Validation Endpoints

| Endpoint | Method | Purpose | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST /api/promo-codes/check/` | `POST` | Check and validate a standalone promo code, returning its details and calculated discount. | **Yes** (`Bearer <token>`) |
| `POST /api/offers/check/` | `POST` | Check cart total & items against active offers or promo codes. | **Yes** (`Bearer <token>`) |

---

## 2. Standalone Promo Code Check (`POST /api/promo-codes/check/`)

Use this endpoint when a user enters a coupon/promo code at checkout to quickly validate the code and fetch its details.

### Request Body Schema (`PromoCodeCheckSerializer`)

```json
{
  "code": "WELCOME50",
  "cart_total": 1000.0
}
```

| Field Name | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `code` | String | **Yes** | Promo code entered by the user (case-insensitive) |
| `cart_total` | Float | No | Current subtotal of the cart (default: `0.0`). If provided, calculates exact discount. |

---

### Response Schemas

#### A. Success — Code Valid (`HTTP 200 OK`)

```json
{
  "is_valid": true,
  "message": "Promo code is valid.",
  "promo_code": {
    "id": 1,
    "code": "WELCOME50",
    "description": "Flat Rs. 150 discount for new users",
    "promo_type": "AMOUNT",
    "amount": 150.0,
    "max_total_usage": 500,
    "max_usage_per_user": 1,
    "current_usage_count": 42,
    "start_datetime": "2026-08-01T00:00:00Z",
    "end_datetime": "2026-08-31T23:59:59Z",
    "calculated_discount": 150.0,
    "final_amount": 850.0
  }
}
```

*For **PERCENTAGE** discount type (`promo_type: "PERCENTAGE"`):*

```json
{
  "is_valid": true,
  "message": "Promo code is valid.",
  "promo_code": {
    "id": 2,
    "code": "SUPER15",
    "description": "15% discount on cart total",
    "promo_type": "PERCENTAGE",
    "amount": 15.0,
    "max_total_usage": null,
    "max_usage_per_user": 2,
    "current_usage_count": 5,
    "start_datetime": null,
    "end_datetime": null,
    "calculated_discount": 150.0,
    "final_amount": 850.0
  }
}
```

---

#### B. Failure — Code Invalid or Limit Reached (`HTTP 400 Bad Request`)

```json
{
  "is_valid": false,
  "message": "You have already reached the max usage limit (1) for this promo code.",
  "promo_code": {
    "id": 1,
    "code": "WELCOME50",
    "description": "Flat Rs. 150 discount",
    "promo_type": "AMOUNT",
    "amount": 150.0,
    "is_active": true
  }
}
```

---

## 3. Cart Offer Check (`POST /api/offers/check/`)

Use this endpoint when checking full cart offers (including BOGO, Free Delivery, and auto-applied deals).

### Request Body Schema (`OfferCheckSerializer`)

```json
{
  "promo_code": "WELCOME50", 
  "cart_total": 1200.0,
  "cart_items": [
    {
      "product_id": 10,
      "category_id": 2,
      "subcategory_id": 5,
      "price": 300.0,
      "quantity": 2
    }
  ]
}
```

### Success Response (`HTTP 200 OK`)

```json
{
  "is_valid": true,
  "message": "Promo code applied successfully.",
  "offer_id": null,
  "offer_title": "Promo Code: WELCOME50",
  "promo_code": "WELCOME50",
  "discount_amount": 150.0,
  "final_amount": 1050.0,
  "reward_details": {
    "promo_type": "AMOUNT",
    "amount": 150.0
  }
}
```

---

## 4. TypeScript Interfaces

Add these interfaces to your frontend codebase (`types/offer.ts`):

```typescript
export type PromoType = "AMOUNT" | "PERCENTAGE";

export interface PromoCodeDetail {
  id: number;
  code: string;
  description?: string | null;
  promo_type: PromoType;
  amount: number;
  max_total_usage?: number | null;
  max_usage_per_user?: number;
  current_usage_count?: number;
  start_datetime?: string | null;
  end_datetime?: string | null;
  calculated_discount?: number;
  final_amount?: number;
  is_active?: boolean;
}

export interface PromoCodeCheckPayload {
  code: string;
  cart_total?: number;
}

export interface PromoCodeCheckResponse {
  is_valid: boolean;
  message: string;
  promo_code?: PromoCodeDetail | null;
}

export interface CartItemInput {
  product_id: number;
  category_id?: number | null;
  subcategory_id?: number | null;
  price: number;
  quantity: number;
}

export interface OfferCheckPayload {
  promo_code?: string | null;
  cart_total: number;
  cart_items?: CartItemInput[];
}

export interface OfferCheckResponse {
  is_valid: boolean;
  message: string;
  offer_id?: number | null;
  offer_title?: string;
  promo_code?: string | null;
  discount_amount: number;
  final_amount: number;
  reward_details?: Record<string, any>;
}
```

---

## 5. API Functions & React Hooks

### API Fetcher (`api/offer.ts`)

```typescript
import {
  PromoCodeCheckPayload,
  PromoCodeCheckResponse,
  OfferCheckPayload,
  OfferCheckResponse,
} from "../types/offer";

// Validate standalone promo code
export async function checkPromoCode(
  token: string,
  payload: PromoCodeCheckPayload
): Promise<PromoCodeCheckResponse> {
  const response = await fetch("/api/promo-codes/check/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok && response.status !== 400) {
    throw new Error(data.detail || "Failed to validate promo code");
  }
  return data;
}

// Evaluate full cart offers
export async function checkCartOffer(
  token: string,
  payload: OfferCheckPayload
): Promise<OfferCheckResponse> {
  const response = await fetch("/api/offers/check/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok && response.status !== 400) {
    throw new Error(data.detail || "Failed to validate offer");
  }
  return data;
}
```

### TanStack Query Mutation Hooks (`hooks/useCheckPromoCode.ts`)

```typescript
import { useMutation } from "@tanstack/react-query";
import { checkPromoCode } from "../api/offer";
import { PromoCodeCheckPayload, PromoCodeCheckResponse } from "../types/offer";

export function useCheckPromoCode(token: string) {
  return useMutation<PromoCodeCheckResponse, Error, PromoCodeCheckPayload>({
    mutationFn: (payload) => checkPromoCode(token, payload),
  });
}
```

---

## 6. React Cart Component Integration Example

Below is a clean React / Next.js implementation for a Cart page using `POST /api/promo-codes/check/`:

```tsx
import React, { useState } from "react";
import { useCheckPromoCode } from "../hooks/useCheckPromoCode";

interface CartItem {
  id: number;
  name: string;
  price: number;
  quantity: number;
}

interface CartProps {
  items: CartItem[];
  authToken: string;
}

export function CartComponent({ items, authToken }: CartProps) {
  const [promoCodeInput, setPromoCodeInput] = useState("");
  const [appliedPromo, setAppliedPromo] = useState<{
    code: string;
    discountAmount: number;
  } | null>(null);

  const checkPromoMutation = useCheckPromoCode(authToken);

  const cartTotal = items.reduce(
    (sum, item) => sum + item.price * item.quantity,
    0
  );

  const handleApplyPromoCode = () => {
    if (!promoCodeInput.trim()) return;

    checkPromoMutation.mutate(
      {
        code: promoCodeInput.trim(),
        cart_total: cartTotal,
      },
      {
        onSuccess: (data) => {
          if (data.is_valid && data.promo_code) {
            setAppliedPromo({
              code: data.promo_code.code,
              discountAmount: data.promo_code.calculated_discount ?? 0,
            });
          } else {
            setAppliedPromo(null);
          }
        },
      }
    );
  };

  const discountAmount = appliedPromo?.discountAmount ?? 0;
  const finalTotal = Math.max(0, cartTotal - discountAmount);

  return (
    <div className="cart-container p-4 max-w-lg mx-auto bg-white rounded shadow">
      <h2 className="text-xl font-bold mb-4">Your Cart</h2>

      {/* Items List */}
      <div className="divide-y mb-4">
        {items.map((item) => (
          <div key={item.id} className="py-2 flex justify-between">
            <span>
              {item.name} x {item.quantity}
            </span>
            <span>Rs. {item.price * item.quantity}</span>
          </div>
        ))}
      </div>

      {/* Promo Code Input */}
      <div className="my-4">
        <label className="block text-sm font-medium mb-1">Have a Promo Code?</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={promoCodeInput}
            onChange={(e) => setPromoCodeInput(e.target.value)}
            placeholder="Enter promo code (e.g. WELCOME50)"
            className="border px-3 py-2 rounded w-full uppercase"
          />
          <button
            onClick={handleApplyPromoCode}
            disabled={checkPromoMutation.isPending}
            className="bg-red-600 text-white px-4 py-2 rounded font-semibold disabled:opacity-50"
          >
            {checkPromoMutation.isPending ? "Applying..." : "Apply"}
          </button>
        </div>

        {/* Status Message */}
        {checkPromoMutation.data && (
          <p
            className={`mt-2 text-sm ${
              checkPromoMutation.data.is_valid
                ? "text-green-600 font-medium"
                : "text-red-600 font-medium"
            }`}
          >
            {checkPromoMutation.data.message}
          </p>
        )}
      </div>

      {/* Order Financial Summary */}
      <div className="border-t pt-4 space-y-2">
        <div className="flex justify-between text-gray-700">
          <span>Subtotal</span>
          <span>Rs. {cartTotal.toFixed(2)}</span>
        </div>

        {discountAmount > 0 && (
          <div className="flex justify-between text-green-600 font-medium">
            <span>Discount ({appliedPromo?.code})</span>
            <span>- Rs. {discountAmount.toFixed(2)}</span>
          </div>
        )}

        <div className="flex justify-between text-lg font-bold text-gray-900 border-t pt-2">
          <span>Total Amount</span>
          <span>Rs. {finalTotal.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}
```

---

## 7. Summary of API Endpoints

- **List / Create Promo Codes**: `GET` / `POST` `/api/promo-codes/`
- **Retrieve / Update / Delete Promo Code**: `GET` / `PUT` / `DELETE` `/api/promo-codes/<id>/`
- **Check / Validate Promo Code**: `POST /api/promo-codes/check/`
- **Check / Evaluate Cart Offers**: `POST /api/offers/check/`
