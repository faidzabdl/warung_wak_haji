# UMKM Ordering API

> Production-ready ordering backend for a single UMKM — FastAPI + Supabase.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Setup](#3-setup)
4. [Environment Variables](#4-environment-variables)
5. [Database Setup](#5-database-setup)
6. [Running the Server](#6-running-the-server)
7. [Running Tests](#7-running-tests)
8. [API Contract](#8-api-contract)
9. [Deployment](#9-deployment)
10. [Known Limitations](#10-known-limitations)
11. [Realtime Integration](#11-realtime-integration)

---

## 1. Project Overview

This is the backend API for a single UMKM (micro/small business) ordering system. Buyers browse the menu, place orders, upload QRIS payment proof, and track their order status using a one-time secret token. The seller authenticates via Supabase Auth JWT and manages the full order lifecycle through a dashboard.

**Three dashboard features:**

| Feature | Description |
|---|---|
| **Orders** | Active orders management — verify/reject payment, process, complete, cancel |
| **Order History** | Paginated history of completed and cancelled orders with date/status filters |
| **Menu Management** | Full CRUD for menu items including image upload and availability toggle |

**Single-seller model:** Access is controlled by `ALLOWED_SELLER_UID` — only one Supabase Auth user has seller privileges. Buyers are unauthenticated at the HTTP level.

**Scope:** Backend only. No frontend code. Deployment targets Railway (backend) + Vercel (future Vue 3 frontend) + Supabase.

---

## 2. Tech Stack

| Component | Technology |
|---|---|
| Language / Framework | Python 3.11+ / FastAPI 0.111+ |
| Database / Auth / Storage | Supabase (PostgreSQL + Auth + Storage + Realtime) |
| Schema Validation | Pydantic v2 + pydantic-settings |
| JWT Validation | PyJWT (direct, no network call) |
| Rate Limiting | slowapi (in-memory) |
| Testing | pytest + httpx |
| Server | Uvicorn |
| Deployment | Railway (backend) + Vercel (future frontend) |

---

## 3. Setup

```bash
# 1. Clone the repository and create a virtual environment
git clone <repo-url>
cd <repo-directory>
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env with your Supabase credentials (see Section 4 below)
```

---

## 4. Environment Variables

Copy `.env.example` to `.env` and fill in all seven values before starting the server.

| Variable | Description | Where to find |
|---|---|---|
| `SUPABASE_URL` | Project URL (e.g. `https://xxxx.supabase.co`) | Supabase Dashboard → Settings → API |
| `SUPABASE_ANON_KEY` | Public anon key — safe for frontend use | Supabase Dashboard → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side privileged key — **NEVER expose to frontend** | Supabase Dashboard → Settings → API |
| `SUPABASE_JWT_SECRET` | JWT signing secret for token validation | Supabase Dashboard → Settings → API → JWT Secret |
| `ALLOWED_SELLER_UID` | UUID of the single authorized seller account | Supabase Dashboard → Authentication → Users → copy the seller's UID |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | e.g. `http://localhost:5173,https://yourfrontend.vercel.app` |
| `ENVIRONMENT` | `development` or `production` | Set manually |

> ⚠️ **`SUPABASE_SERVICE_ROLE_KEY` must NEVER be committed to Git or sent to the frontend.** It bypasses all Row Level Security policies. The `.gitignore` already excludes `.env` — verify this before your first commit.

**Example `.env`:**

```env
SUPABASE_URL=https://abcdefghijkl.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard
ALLOWED_SELLER_UID=a1b2c3d4-e5f6-7890-abcd-ef1234567890
ALLOWED_ORIGINS=http://localhost:5173
ENVIRONMENT=development
```

The app **refuses to start** if any required variable is missing or empty (enforced by Pydantic Settings validation).

---

## 5. Database Setup

1. Create a new project at [supabase.com](https://supabase.com).

2. Go to **SQL Editor → New Query**.

3. Open `schema.sql` from this repository.

4. **Important:** Before running, find and replace the placeholder seller UID:
   - Search for `'00000000-0000-0000-0000-000000000000'`
   - Replace with your actual seller's Supabase Auth UID
   - Find the UID at: **Supabase Dashboard → Authentication → Users → copy the seller's UID**

5. Paste the full contents of `schema.sql` into the SQL Editor and click **Run**.

6. Create **Storage buckets** in **Supabase Dashboard → Storage**:
   - `payment-proofs` — **private** bucket (no public access)
   - `menu-images` — **public** bucket (enable public access for direct image URLs)

7. Run the Storage policy SQL from the comments at the bottom of `schema.sql` to grant the seller signed-URL read access to `payment-proofs`.

8. Copy the **JWT Secret** from **Supabase Dashboard → Settings → API → JWT Secret** into your `.env` as `SUPABASE_JWT_SECRET`.

---

## 6. Running the Server

```bash
# Development — auto-reload on file changes
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

Interactive API docs are available while the server is running:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

**Health check:**

```bash
curl http://localhost:8000/health
# {"status": "ok", "environment": "development"}
```

---

## 7. Running Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_orders.py -v

# With coverage report (requires pytest-cov)
pytest tests/ --cov=. --cov-report=term-missing
```

> All tests use **mocked Supabase services** and do **not** require a real Supabase connection or live credentials. Tests tagged `@pytest.mark.integration` are the exception — those require a real Supabase project and a populated `.env`.

---

## 8. API Contract

### Endpoint Summary

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/menus` | Public | List active + available menus |
| `GET` | `/menus/{menu_id}` | Public | Get single menu detail |
| `POST` | `/orders` | Public | Create a new order |
| `POST` | `/orders/{order_number}/proof` | `X-Tracking-Token` header | Upload payment proof |
| `GET` | `/orders/track/{tracking_token}` | Public (token in path) | Track order status |
| `GET` | `/seller/menus` | Bearer JWT | List all menus (incl. inactive) |
| `POST` | `/seller/menus` | Bearer JWT | Create a menu item |
| `PATCH` | `/seller/menus/{menu_id}` | Bearer JWT | Partially update a menu item |
| `PATCH` | `/seller/menus/{menu_id}/availability` | Bearer JWT | Toggle menu availability |
| `POST` | `/seller/menus/upload-image` | Bearer JWT | Upload menu image |
| `GET` | `/seller/orders` | Bearer JWT | List active orders |
| `GET` | `/seller/orders/{order_number}` | Bearer JWT | Order detail + proof URL |
| `POST` | `/seller/orders/{order_number}/verify-payment` | Bearer JWT | Verify payment |
| `POST` | `/seller/orders/{order_number}/reject-payment` | Bearer JWT | Reject payment |
| `POST` | `/seller/orders/{order_number}/start-processing` | Bearer JWT | Start processing order |
| `POST` | `/seller/orders/{order_number}/complete` | Bearer JWT | Complete order |
| `POST` | `/seller/orders/{order_number}/cancel` | Bearer JWT | Cancel order |
| `GET` | `/seller/history` | Bearer JWT | Paginated order history |
| `GET` | `/health` | Public | Health check |

---

### Public — Menus

#### `GET /menus`

Returns all menus where `is_active = true` AND `is_available = true`.

**Response `200`:**
```json
[
  {
    "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
    "name": "Nasi Goreng Spesial",
    "description": "Nasi goreng dengan telur dan ayam",
    "price": "25000.00",
    "image_url": "https://xxxx.supabase.co/storage/v1/object/public/menu-images/abc123.jpg",
    "is_available": true,
    "is_active": true,
    "created_at": "2024-01-15T08:00:00Z",
    "updated_at": "2024-01-15T08:00:00Z"
  }
]
```

```bash
curl http://localhost:8000/menus
```

---

#### `GET /menus/{menu_id}`

Returns a single menu by UUID. Returns `404` if not found or if the menu is inactive/unavailable.

**Path params:** `menu_id` — UUID of the menu item.

**Response `200`:** Same shape as a single element from `GET /menus`.

**Response `404`:**
```json
{"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}}
```

```bash
curl http://localhost:8000/menus/d290f1ee-6c54-4b01-90e6-d701748f0851
```

---

### Public — Orders (Buyer)

#### `POST /orders`

Creates a new order. Prices are **always fetched from the database** — any prices sent by the client are ignored. All items must be active and available; if any are not, the entire order is rejected.

**Rate limit:** 20 requests/minute per IP.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `Content-Type` | Yes | `application/json` |
| `Idempotency-Key` | No | Arbitrary unique string. If the same key is received again, returns the existing order (`200`) instead of creating a duplicate. |

**Request body:**
```json
{
  "buyer_name": "Budi Santoso",
  "items": [
    {"menu_id": "d290f1ee-6c54-4b01-90e6-d701748f0851", "quantity": 2},
    {"menu_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "quantity": 1}
  ],
  "notes": "Tidak pakai cabai"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `buyer_name` | string | Yes | Non-empty after strip |
| `items` | array | Yes | At least one item; quantity ≥ 1 |
| `notes` | string | No | Optional order note |

**Response `201` — new order created:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "tracking_token": "tK9mXzR2pL8vQwYnJdFc0uHsEiAo3bGe7NkCVMT_DZ4",
  "total_amount": "75000.00",
  "message": "Simpan token ini. Tidak dapat ditampilkan ulang."
}
```

> ⚠️ **`tracking_token` is shown ONCE only.** Store the tracking link immediately. Lost tokens cannot be recovered — there is no lookup-by-name or account recovery mechanism.

**Response `200` — duplicate idempotency key:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "message": "Pesanan sudah ada (idempotency key dikenali).",
  "total_amount": "75000.00"
}
```

**Response `400` — unavailable items:**
```json
{"error": {"code": "MENU_NOT_AVAILABLE", "message": "Menu item 'Nasi Goreng Spesial' is not available"}}
```

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: frontend-cart-uuid-abc123" \
  -d '{
    "buyer_name": "Budi Santoso",
    "items": [
      {"menu_id": "d290f1ee-6c54-4b01-90e6-d701748f0851", "quantity": 2}
    ],
    "notes": "Tidak pakai cabai"
  }'
```

---

#### `POST /orders/{order_number}/proof`

Uploads a QRIS payment proof image. Ownership is verified via `X-Tracking-Token` — the header value is hashed and compared against the stored hash.

**Rate limit:** 10 requests/minute per IP.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Tracking-Token` | Yes | Plain tracking token from order creation |
| `Content-Type` | Yes | `multipart/form-data` |

**Form field:** `file` — image file (JPEG, PNG, or WebP; max 5 MB).

Validation: `Content-Type` header AND magic bytes (first bytes of file content) are both checked.

**Blocked states (returns `409`):** Upload is not allowed if `payment_status` is already `paid` or `rejected`, or if `order_status` is `cancelled`.

**Response `200`:**
```json
{
  "message": "Bukti pembayaran berhasil diunggah.",
  "payment_status": "pending_verification"
}
```

**Response `409`:**
```json
{"error": {"code": "PROOF_UPLOAD_NOT_ALLOWED", "message": "Cannot upload proof in the current order state"}}
```

> ⚠️ **Uploading proof does NOT confirm payment.** The seller manually checks the QRIS transaction and verifies or rejects it. If your payment was completed but the proof is rejected, contact the UMKM directly for a refund. **Refunds are NOT automatic.**

```bash
curl -X POST http://localhost:8000/orders/ORD-20240115-AB12/proof \
  -H "X-Tracking-Token: tK9mXzR2pL8vQwYnJdFc0uHsEiAo3bGe7NkCVMT_DZ4" \
  -F "file=@/path/to/payment_proof.jpg"
```

---

#### `GET /orders/track/{tracking_token}`

Returns full order status and item snapshot for the given tracking token.

**Rate limit:** 30 requests/minute per IP.

**Path param:** `tracking_token` — the 43-character plain token from order creation.

**Response `200`:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "buyer_name": "Budi Santoso",
  "order_status": "waiting_processing",
  "payment_status": "paid",
  "total_amount": "75000.00",
  "items": [
    {
      "menu_name": "Nasi Goreng Spesial",
      "menu_price": "25000.00",
      "quantity": 2,
      "subtotal": "50000.00"
    }
  ],
  "notes": "Tidak pakai cabai",
  "created_at": "2024-01-15T08:30:00Z",
  "updated_at": "2024-01-15T08:45:00Z"
}
```

**Response `404`:**
```json
{"error": {"code": "INVALID_TRACKING_TOKEN", "message": "Tracking token not found"}}
```

```bash
curl "http://localhost:8000/orders/track/tK9mXzR2pL8vQwYnJdFc0uHsEiAo3bGe7NkCVMT_DZ4"
```

---

### Seller — Menus (Bearer JWT required)

All seller endpoints require a valid Supabase Auth JWT for the seller account. Include it as:

```
Authorization: Bearer <supabase_access_token>
```

Returns `401` on missing/expired/invalid token; `403` if the token belongs to a different user than `ALLOWED_SELLER_UID`.

---

#### `GET /seller/menus`

Lists all menu items including inactive and unavailable ones.

**Response `200`:** Array of full `MenuResponse` objects (same shape as public menu response, but unfiltered).

```bash
curl http://localhost:8000/seller/menus \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNC1lNWY2LTc4OTAtYWJjZC1lZjEyMzQ1Njc4OTAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIn0.SIGNATURE"
```

---

#### `POST /seller/menus`

Creates a new menu item. To include an image, upload it first via `POST /seller/menus/upload-image` and pass the returned URL here.

**Request body:**
```json
{
  "name": "Mie Goreng Seafood",
  "description": "Mie goreng dengan udang dan cumi",
  "price": "30000.00",
  "image_url": "https://xxxx.supabase.co/storage/v1/object/public/menu-images/uuid.jpg",
  "is_available": true,
  "is_active": true
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | Non-empty after strip |
| `description` | string | No | |
| `price` | number | Yes | Must be > 0 |
| `image_url` | string | No | URL returned by upload-image endpoint |
| `is_available` | boolean | No | Default `true` |
| `is_active` | boolean | No | Default `true` |

**Response `201`:** Full `MenuResponse` object.

```bash
curl -X POST http://localhost:8000/seller/menus \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Mie Goreng Seafood", "price": 30000, "is_available": true, "is_active": true}'
```

---

#### `PATCH /seller/menus/{menu_id}`

Partially updates a menu item. Only send the fields you want to change — all fields are optional.

**Request body (all fields optional):**
```json
{
  "name": "Mie Goreng Spesial",
  "price": "32000.00",
  "is_available": false
}
```

Unknown fields are rejected with `422 VALIDATION_ERROR`.

**Response `200`:** Updated `MenuResponse` object.

```bash
curl -X PATCH "http://localhost:8000/seller/menus/d290f1ee-6c54-4b01-90e6-d701748f0851" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"price": 32000}'
```

---

#### `PATCH /seller/menus/{menu_id}/availability`

Quick toggle for `is_available` without sending a full update body.

**Request body:**
```json
{"is_available": false}
```

**Response `200`:** Updated `MenuResponse` object.

```bash
curl -X PATCH "http://localhost:8000/seller/menus/d290f1ee-6c54-4b01-90e6-d701748f0851/availability" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"is_available": false}'
```

---

#### `POST /seller/menus/upload-image`

Uploads a menu image to Supabase Storage (`menu-images` bucket) and returns the public URL. Call this **before** `POST /seller/menus` to get the `image_url`.

**Form field:** `file` — image file (JPEG, PNG, or WebP; max 5 MB).

Validation: both `Content-Type` and magic bytes are checked.

**Response `200`:**
```json
{"image_url": "https://xxxx.supabase.co/storage/v1/object/public/menu-images/3f7a8b2e-1234-5678-90ab-cdef01234567.jpg"}
```

**Response `400`:**
```json
{"error": {"code": "FILE_TOO_LARGE", "message": "File exceeds the 5MB limit"}}
```
```json
{"error": {"code": "INVALID_FILE_TYPE", "message": "Only jpeg, png, and webp files are allowed"}}
```

> ⚠️ **`SUPABASE_SERVICE_ROLE_KEY` is used server-side to upload to Storage.** It is never sent to or accessible from the frontend. The frontend calls this FastAPI endpoint, which performs the upload internally.

```bash
curl -X POST http://localhost:8000/seller/menus/upload-image \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/menu_image.jpg"
```

---

### Seller — Orders (Bearer JWT required)

#### `GET /seller/orders`

Lists all active orders — those with `order_status` in `awaiting_payment`, `waiting_processing`, or `processing` — ordered by `created_at` ascending (oldest first).

**Response `200`:**
```json
[
  {
    "order_number": "ORD-20240115-AB12",
    "buyer_name": "Budi Santoso",
    "order_status": "waiting_processing",
    "payment_status": "paid",
    "total_amount": "75000.00",
    "item_count": 2,
    "created_at": "2024-01-15T08:30:00Z"
  }
]
```

```bash
curl http://localhost:8000/seller/orders \
  -H "Authorization: Bearer <token>"
```

---

#### `GET /seller/orders/{order_number}`

Returns full order detail including items snapshot and a signed URL for the payment proof image (valid for 1 hour). `payment_proof_url` is `null` if no proof has been uploaded yet.

**Response `200`:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "buyer_name": "Budi Santoso",
  "notes": "Tidak pakai cabai",
  "order_status": "waiting_processing",
  "payment_status": "paid",
  "total_amount": "75000.00",
  "items": [
    {
      "menu_name": "Nasi Goreng Spesial",
      "menu_price": "25000.00",
      "quantity": 2,
      "subtotal": "50000.00",
      "menu_id": "d290f1ee-6c54-4b01-90e6-d701748f0851"
    }
  ],
  "payment_proof_url": "https://xxxx.supabase.co/storage/v1/object/sign/payment-proofs/...?token=...&expiresIn=3600",
  "cancel_reason": null,
  "reject_reason": null,
  "created_at": "2024-01-15T08:30:00Z",
  "updated_at": "2024-01-15T08:45:00Z"
}
```

**Response `404`:**
```json
{"error": {"code": "ORDER_NOT_FOUND", "message": "Order not found"}}
```

```bash
curl "http://localhost:8000/seller/orders/ORD-20240115-AB12" \
  -H "Authorization: Bearer <token>"
```

---

#### `POST /seller/orders/{order_number}/verify-payment`

Marks the payment as `paid` and advances the order to `waiting_processing`.

**Valid prior states:** `order_status = awaiting_payment` AND `payment_status = pending_verification`.

**Response `200`:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "order_status": "waiting_processing",
  "payment_status": "paid"
}
```

**Response `409`:**
```json
{"error": {"code": "INVALID_STATUS_TRANSITION", "message": "Cannot verify payment in current order state"}}
```

```bash
curl -X POST "http://localhost:8000/seller/orders/ORD-20240115-AB12/verify-payment" \
  -H "Authorization: Bearer <token>"
```

---

#### `POST /seller/orders/{order_number}/reject-payment`

Rejects the payment and cancels the order. A reason is required.

**Request body:**
```json
{"reason": "Bukti transfer tidak sesuai nominal"}
```

**Response `200`:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "order_status": "cancelled",
  "payment_status": "rejected"
}
```

> ⚠️ Rejecting payment moves the order to `cancelled`. If the buyer already made the payment, they must contact the UMKM directly for a refund. **Refunds are NOT automatic.**

```bash
curl -X POST "http://localhost:8000/seller/orders/ORD-20240115-AB12/reject-payment" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Bukti transfer tidak sesuai nominal"}'
```

---

#### `POST /seller/orders/{order_number}/start-processing`

Advances the order from `waiting_processing` to `processing`.

**Valid prior state:** `order_status = waiting_processing`.

**Response `200`:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "order_status": "processing"
}
```

```bash
curl -X POST "http://localhost:8000/seller/orders/ORD-20240115-AB12/start-processing" \
  -H "Authorization: Bearer <token>"
```

---

#### `POST /seller/orders/{order_number}/complete`

Marks the order as `completed`.

**Valid prior state:** `order_status = processing`.

**Response `200`:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "order_status": "completed"
}
```

```bash
curl -X POST "http://localhost:8000/seller/orders/ORD-20240115-AB12/complete" \
  -H "Authorization: Bearer <token>"
```

---

#### `POST /seller/orders/{order_number}/cancel`

Cancels the order from any non-terminal state. A reason is required.

**Valid prior states:** `awaiting_payment`, `waiting_processing`, `processing`.

**Request body:**
```json
{"reason": "Stok habis"}
```

**Response `200`:**
```json
{
  "order_number": "ORD-20240115-AB12",
  "order_status": "cancelled"
}
```

```bash
curl -X POST "http://localhost:8000/seller/orders/ORD-20240115-AB12/cancel" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Stok habis"}'
```

---

#### `GET /seller/history`

Returns a paginated list of completed and cancelled orders.

**Query parameters:**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `page` | int | `1` | Page number (≥ 1) |
| `page_size` | int | `20` | Items per page (1–100) |
| `status` | string | — | Filter by `completed` or `cancelled` |
| `date_from` | string | — | ISO 8601 date filter start (inclusive) |
| `date_to` | string | — | ISO 8601 date filter end (inclusive) |

**Response `200`:**
```json
{
  "data": [
    {
      "order_number": "ORD-20240114-CD34",
      "buyer_name": "Siti Rahayu",
      "order_status": "completed",
      "payment_status": "paid",
      "total_amount": "45000.00",
      "items": [
        {
          "menu_name": "Es Teh Manis",
          "menu_price": "5000.00",
          "quantity": 3,
          "subtotal": "15000.00",
          "menu_id": null
        }
      ],
      "cancel_reason": null,
      "reject_reason": null,
      "created_at": "2024-01-14T12:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

```bash
curl "http://localhost:8000/seller/history?page=1&page_size=20&status=completed&date_from=2024-01-01" \
  -H "Authorization: Bearer <token>"
```

---

### System

#### `GET /health`

Returns server status and current environment. No auth required.

**Response `200`:**
```json
{"status": "ok", "environment": "development"}
```

---

### Error Response Format

All errors — including auth failures, validation errors, not-found errors, and server errors — use the same envelope:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message"
  }
}
```

`422 VALIDATION_ERROR` responses include an additional `details` array:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {"field": "body.items", "message": "items cannot be empty"}
    ]
  }
}
```

### Error Code Reference

| Code | HTTP Status | Description |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or malformed `Authorization` header |
| `TOKEN_EXPIRED` | 401 | JWT token has expired |
| `INVALID_TOKEN` | 401 | JWT signature invalid or token malformed |
| `FORBIDDEN` | 403 | Valid JWT but `sub` does not match `ALLOWED_SELLER_UID` |
| `VALIDATION_ERROR` | 422 | Request body failed Pydantic validation |
| `MENU_NOT_FOUND` | 404 | Menu item does not exist or is not accessible |
| `MENU_NOT_AVAILABLE` | 400 | Menu item is marked as unavailable |
| `MENU_NOT_ACTIVE` | 400 | Menu item is inactive |
| `ORDER_NOT_FOUND` | 404 | Order does not exist |
| `INVALID_TRACKING_TOKEN` | 404 | Tracking token did not match any order |
| `PROOF_UPLOAD_NOT_ALLOWED` | 409 | Upload blocked — order is already paid, rejected, or cancelled |
| `INVALID_STATUS_TRANSITION` | 409 | Requested status change is not valid from current state |
| `FILE_TOO_LARGE` | 400 | Uploaded file exceeds 5 MB |
| `INVALID_FILE_TYPE` | 400 | File type not allowed (only JPEG, PNG, WebP) |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests from this IP |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

### Status Flows

```
ORDER STATUS FLOW
-----------------
awaiting_payment   → waiting_processing   (seller: verify payment)
awaiting_payment   → cancelled            (seller: reject payment OR cancel)
waiting_processing → processing           (seller: start processing)
waiting_processing → cancelled            (seller: cancel)
processing         → completed            (seller: complete)
processing         → cancelled            (seller: cancel)

Terminal states: completed, cancelled — no further transitions allowed.


PAYMENT STATUS FLOW
-------------------
pending_payment       → pending_verification   (buyer uploads proof)
pending_verification  → paid                   (seller verifies payment)
pending_verification  → rejected               (seller rejects) → order becomes cancelled
```

---

## 9. Deployment ke Render.com

Aplikasi ini di-deploy menggunakan **Render Blueprint** (`render.yaml`) — satu file yang mendefinisikan backend dan frontend sekaligus.

### Prasyarat

- Repo sudah di GitHub (public atau private)
- Akun [Render.com](https://render.com) (gratis)
- Project Supabase sudah jalan dan migration sudah dijalankan (lihat [Bagian 5](#5-database-setup))
- Kamu punya nilai untuk semua env var (lihat [Bagian 4](#4-environment-variables))

---

### Langkah Deploy

#### 1. Deploy via Blueprint

1. Buka [render.com/dashboard](https://dashboard.render.com)
2. Klik **New → Blueprint**
3. Pilih GitHub repo ini
4. Render membaca `render.yaml` dan menampilkan preview **2 service**: `warung-backend` dan `warung-frontend`
5. Klik **Apply** — kedua service mulai build

#### 2. Isi env var backend (`warung-backend`)

Buka **Dashboard → warung-backend → Environment** dan isi:

| Variable | Nilai | Cara mendapatkan |
|---|---|---|
| `SUPABASE_URL` | `https://xxxx.supabase.co` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | `eyJ...` | Supabase Dashboard → Settings → API → anon public |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | Supabase Dashboard → Settings → API → service_role ⚠️ rahasia |
| `SUPABASE_JWT_SECRET` | string panjang | Supabase Dashboard → Settings → API → JWT Secret |
| `ALLOWED_SELLER_UID` | UUID | Supabase Dashboard → Authentication → Users → copy UID seller |
| `ALLOWED_ORIGINS` | `https://warung-frontend.onrender.com` | URL frontend dari langkah 3 |

Setelah isi, klik **Save Changes** → Render otomatis redeploy backend.

#### 3. Isi env var frontend (`warung-frontend`)

Buka **Dashboard → warung-frontend → Environment** dan isi:

| Variable | Nilai | Cara mendapatkan |
|---|---|---|
| `VITE_SUPABASE_URL` | `https://xxxx.supabase.co` | Sama seperti `SUPABASE_URL` di backend |
| `VITE_SUPABASE_ANON_KEY` | `eyJ...` | Sama seperti `SUPABASE_ANON_KEY` di backend |
| `VITE_API_URL` | `https://warung-backend.onrender.com` | URL backend dari langkah 2 |

Setelah isi, klik **Save Changes** → Render otomatis rebuild frontend.

> ⚠️ **Jangan pernah** masukkan `SUPABASE_SERVICE_ROLE_KEY` ke env var frontend. Key ini hanya untuk backend.

#### 4. Cari tahu URL masing-masing service

Setelah deploy pertama selesai, Render menampilkan URL di halaman service:
- Backend: `https://warung-backend.onrender.com` (atau nama yang kamu pilih)
- Frontend: `https://warung-frontend.onrender.com`

Gunakan kedua URL ini untuk mengisi `ALLOWED_ORIGINS` (backend) dan `VITE_API_URL` (frontend) di langkah 2–3.

---

### Catatan Free Tier Render

| Service | Free Tier |
|---|---|
| Web Service (backend) | 750 jam/bulan, **spin down setelah 15 menit idle** — request pertama setelah idle ~30 detik |
| Static Site (frontend) | Gratis selamanya, tidak ada spin down |

> Jika spin down backend mengganggu, pertimbangkan upgrade ke **Render Starter ($7/bulan)** untuk always-on.

### Supabase Free Tier Limits

| Resource | Limit |
|---|---|
| PostgreSQL storage | 500 MB |
| File storage | 1 GB |
| Monthly active users | 50,000 |
| Bandwidth | 2 GB / month |

Monitor usage di **Supabase Dashboard → Reports**.

---

## 10. Known Limitations

| Limitation | Impact | Mitigation / Notes |
|---|---|---|
| In-memory rate limiting (`slowapi`) resets on server restart | Rate limits can be bypassed by triggering a Railway restart | Acceptable for small UMKM scale; upgrade to Redis limiter for high traffic |
| Tracking token is non-recoverable if lost | Buyer cannot track their order | Documented clearly at order creation; frontend must prompt buyer to save the link |
| Manual payment verification | Seller must manually check the QRIS transaction in their bank app | By design — no payment gateway integration |
| `ALLOWED_SELLER_UID` is a single env var | Misconfiguration grants wrong user seller access | Verify the UID on every deploy |
| File validation uses `Content-Type` + magic bytes only | Malicious files with valid image headers could still be uploaded | No deep malware scan — acceptable risk for UMKM scale |
| No automatic refund mechanism | Rejected payments require manual handling by the seller | Documented in buyer-facing error messages; refund policy is UMKM's responsibility |
| `Idempotency-Key` header is optional | Clients that retry without the header may create duplicate orders | Frontend should always send `Idempotency-Key`; acceptable trade-off for simplicity |
| `menu-images` Storage bucket is public-read | Image URLs are guessable if the path is known | Acceptable — menu images are not sensitive data |
| Single-seller architecture | Only one seller account per deployment | By design; multi-seller would require a full re-architecture |

---

## 11. Realtime Integration

The seller dashboard subscribes directly to **Supabase Realtime (Postgres Changes)** using the seller's JWT. No backend WebSocket proxy is needed.

See **[docs/realtime.md](docs/realtime.md)** for the full setup guide including:

- Initializing the Supabase JS client
- Setting the seller session JWT
- Subscribing to `orders` table changes
- Filtering to active orders only
- Handling event payloads (`INSERT`, `UPDATE`)
- Cleanup on component unmount (Vue 3)
- Security notes (RLS enforcement, never use service-role key in frontend)

**Quick summary:**

```js
const channel = supabase
  .channel('seller-orders')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'orders' }, (payload) => {
    // handle INSERT / UPDATE
  })
  .subscribe()
```

> **Buyers do NOT use Realtime.** They poll `GET /orders/track/{tracking_token}` (rate-limited to 30 req/min per IP).

> ⚠️ **Never use `SUPABASE_SERVICE_ROLE_KEY` in frontend code.** The Realtime client uses the anon key + seller JWT, which is sufficient — RLS handles authorization automatically.
