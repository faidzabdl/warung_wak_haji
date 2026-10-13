# Supabase Realtime Integration Guide

## Overview

The seller dashboard uses **Supabase Realtime (Postgres Changes)** to receive live order
updates without polling. When a buyer creates an order or its status changes, the seller
dashboard receives the event instantly via WebSocket.

**Buyers do NOT use Realtime.** They poll [`GET /orders/track/{tracking_token}`](../README.md)
instead (rate-limited to 30 requests/minute).

---

## Prerequisites

- Seller must be logged in and have a valid **Supabase Auth JWT** (`access_token`) obtained
  from the login flow.
- Frontend uses [`@supabase/supabase-js`](https://github.com/supabase/supabase-js) **v2+**.
- `SUPABASE_URL` and `SUPABASE_ANON_KEY` are **public** and safe to embed in frontend code.
- No extra backend endpoint is needed — the frontend subscribes directly to Supabase.

---

## Setup

### 1. Install the Supabase client

```bash
npm install @supabase/supabase-js
```

### 2. Initialize the Supabase client

```js
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)
```

> Both environment variables are **public**. The anon key is intentionally designed to be
> embedded in frontend code; access is controlled by RLS policies, not by keeping the key
> secret.

### 3. Set the seller session

After the seller logs in via your backend (which returns the Supabase JWT), inject the
session into the client so Realtime can authenticate with the seller's identity:

```js
// sellerJwt is the access_token returned by your login endpoint
await supabase.auth.setSession({
  access_token: sellerJwt,
  refresh_token: '',   // omit or pass empty string for non-refresh flows
})
```

### 4. Subscribe to order changes

```js
const channel = supabase
  .channel('seller-orders')
  .on(
    'postgres_changes',
    {
      event: '*',       // listens for INSERT, UPDATE, and DELETE
      schema: 'public',
      table: 'orders',
    },
    (payload) => {
      console.log('Order event:', payload.eventType, payload)
      // Re-fetch or patch your local state based on payload
    }
  )
  .subscribe((status) => {
    console.log('Realtime subscription status:', status)
    // status: 'SUBSCRIBED' | 'TIMED_OUT' | 'CLOSED' | 'CHANNEL_ERROR'
  })
```

### 5. Filter to active orders only (optional)

To reduce noise and only receive events for orders that are not yet completed or cancelled,
add a `filter` parameter:

```js
const channel = supabase
  .channel('seller-active-orders')
  .on(
    'postgres_changes',
    {
      event: '*',
      schema: 'public',
      table: 'orders',
      filter: 'order_status=in.(awaiting_payment,waiting_processing,processing)',
    },
    (payload) => {
      // Only fires for active-status orders
    }
  )
  .subscribe()
```

> **Note:** Server-side filters are applied **in addition to** RLS. The seller will never
> receive events for rows RLS denies, regardless of filter.

### 6. Unsubscribe on component unmount (Vue 3)

Always clean up the subscription when the component is destroyed to avoid memory leaks and
stale connections:

```js
import { onUnmounted } from 'vue'

onUnmounted(async () => {
  await supabase.removeChannel(channel)
})
```

---

## Event Payload Structure

Each event delivers a `payload` object with the following shape:

| Field | Type | Description |
|-------|------|-------------|
| `payload.eventType` | `'INSERT' \| 'UPDATE' \| 'DELETE'` | The type of change that occurred |
| `payload.new` | `object` | The new row values (present for `INSERT` and `UPDATE`) |
| `payload.old` | `object` | The previous row values (present for `UPDATE` and `DELETE`) |
| `payload.schema` | `string` | Always `'public'` |
| `payload.table` | `string` | Table name, e.g. `'orders'` |
| `payload.commit_timestamp` | `string` | ISO 8601 timestamp of the DB commit |

### Example INSERT payload

```json
{
  "eventType": "INSERT",
  "schema": "public",
  "table": "orders",
  "new": {
    "id": "...",
    "order_number": "ORD-20240101-AB12",
    "buyer_name": "Budi",
    "order_status": "awaiting_payment",
    "payment_status": "pending_payment",
    "total_amount": "45000.00",
    "created_at": "2024-01-01T10:00:00Z"
  },
  "old": {}
}
```

---

## Security Notes

- **RLS enforcement:** The `orders` table has a seller SELECT policy
  (`"Seller can view all orders"`) that checks `auth.uid()` against the configured seller
  UID. Supabase Realtime automatically applies this policy — the seller JWT only receives
  events for rows the policy authorizes.
- **Never use the service-role key in frontend code.** The service-role key bypasses RLS
  entirely and must stay on the server side only.
- **The anon key is public by design.** It provides no elevated access on its own; the
  seller JWT is the actual access gate via RLS.
- **No backend WebSocket proxy is needed.** The frontend connects directly to Supabase
  Realtime infrastructure.

---

## Buyer Tracking

Buyers do **not** use Realtime. They track their order status by polling:

```
GET /orders/track/{tracking_token}
```

This endpoint is rate-limited to **30 requests/minute** per IP. The tracking token is a
43-character high-entropy secret returned once at order creation and never stored in
plaintext. Buyers must save their tracking link — it cannot be recovered if lost.
