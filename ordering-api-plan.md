# Ordering API Plan — UMKM Backend

## Top-Level Overview

Build a secure, production-ready ordering API for a single UMKM (micro-business) using FastAPI and Supabase.
The backend serves three dashboard features for the seller: **Orders** (active orders management),
**Order History** (completed/cancelled with pagination/filters), and **Menu Management** (CRUD + availability).
Buyers are unauthenticated — they create orders and track them using a high-entropy secret token (hashed in DB).
Sellers authenticate via Supabase Auth JWT.

**Scope:** Backend only. No frontend code. Deployment targets Railway (backend) + Vercel (future frontend) + Supabase.

**Non-goals:** Payment gateway integration, multi-UMKM/multi-seller, frontend code, Redis, real-time frontend push beyond Supabase Realtime channel.

**Key decisions locked in:**
- Rate limiting: `slowapi` in-memory (acceptable for small UMKM scale)
- Tracking token: plain token returned once at order creation, only SHA-256 hash stored in DB
- Deployment: Railway (FastAPI) + Vercel (Vue 3 frontend, future) + Supabase free tier
- Seller identity: validated against `ALLOWED_SELLER_UID` env var in `require_seller` dependency — not just "any authenticated user"
- Idempotency: `Idempotency-Key` header on `POST /orders`; unique constraint on `idempotency_key` in `orders` table; duplicate key returns existing order (200, not 201)
- Proof upload re-upload: blocked if `payment_status` is already `paid`, `rejected`, or order is `cancelled` — prevents overwrite after decision made
- Menu image upload: dedicated `POST /seller/menus/upload-image` endpoint (multipart); backend validates type+size, uploads to Supabase Storage, returns `image_url`; service-role key never exposed to frontend
- Tests: written incrementally alongside each feature sub-task (4, 5, 6), not deferred to Sub-Task 8; Sub-Task 8 becomes final integration test run + coverage review

---

## Sub-Task 1 — Project Scaffold & Configuration

**Status:** `[ ] pending`

**Intent:**
Create the project skeleton, directory structure, dependency manifest, and environment configuration so every subsequent sub-task has a consistent foundation to build on.

**Expected Outcomes:**
- Repository has the agreed modular directory structure.
- `requirements.txt` lists all dependencies with pinned major versions.
- `.env.example` documents every required env var without real secrets.
- `config.py` loads and validates env vars using Pydantic Settings; the app refuses to start with missing required vars.
- `main.py` boots a FastAPI app with CORS configured from env var, global error handlers that never leak stack traces, and health-check endpoint.
- `.gitignore` excludes `.env`, `__pycache__`, `.pytest_cache`, and similar.

**Todo List:**
- [ ] Create directory structure: `routers/`, `schemas/`, `services/`, `dependencies/`, `tests/`
- [ ] Create `requirements.txt` with: `fastapi`, `uvicorn[standard]`, `supabase` (Python SDK), `pydantic-settings`, `python-dotenv`, `slowapi`, `pytest`, `pytest-asyncio`, `httpx`, `python-multipart`, `PyJWT`
- [ ] Create `.env.example` with keys: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `ALLOWED_ORIGINS`, `ALLOWED_SELLER_UID`, `ENVIRONMENT` (`development`/`production`)
- [ ] Create `config.py` — Pydantic `BaseSettings` class loading all env vars, with validators
- [ ] Create `db.py` — initialize Supabase client (anon client for public ops, service-role client only for server-side privileged ops, never exposed to frontend)
- [ ] Create `main.py` — FastAPI app, CORS middleware from config, global 500 handler (no stack trace in response), 422 handler, `/health` endpoint
- [ ] Create `.gitignore`
- [ ] Create `README.md` skeleton with sections: Setup, Environment, Database, Running, Tests, API Contract

**Relevant Context:**
- `config.py`: Use `pydantic-settings` `BaseSettings` with `model_config = SettingsConfigDict(env_file=".env")`
- `db.py`: Two clients — `get_anon_client()` for public/buyer ops, `get_service_client()` for server-side seller-privileged ops
- CORS: `ALLOWED_ORIGINS` env var as comma-separated list, parsed into list at startup
- Never import `SUPABASE_SERVICE_ROLE_KEY` in any router — only in `db.py`
- `ALLOWED_SELLER_UID`: single UUID string of the one permitted seller account; loaded in `config.py`

---

## Sub-Task 2 — Database Schema, RLS, and Storage Policy

**Status:** `[ ] pending`

**Intent:**
Design and document the complete PostgreSQL schema in `schema.sql` including tables, constraints, indexes, Row Level Security policies, and Supabase Storage bucket configuration. This is the source of truth for the data layer.

**Expected Outcomes:**
- `schema.sql` is complete and executable on a fresh Supabase project.
- All tables have appropriate PKs, FKs, CHECK constraints, and NOT NULL constraints.
- Indexes exist for all query-critical columns (status, created_at, order_number, token_hash).
- RLS is enabled on all tables; policies enforce least privilege.
- Storage bucket `payment-proofs` is private; policies allow buyer upload (by order token logic via service role) and seller read only.
- Snapshot fields on `order_items` ensure price history immutability.

**Todo List:**
- [ ] Design `menus` table: `id` (uuid PK), `name`, `description`, `price` (numeric, positive CHECK), `image_url`, `is_available` (bool), `is_active` (bool), `created_at`, `updated_at`
- [ ] Design `orders` table: `id` (uuid PK), `order_number` (unique, generated), `idempotency_key` (text, unique index, nullable), `buyer_name`, `notes`, `payment_status` (enum), `order_status` (enum), `tracking_token_hash` (text, unique index), `payment_proof_path` (nullable), `cancel_reason` (nullable), `reject_reason` (nullable), `created_at`, `updated_at`
- [ ] Design `order_items` table: `id` (uuid PK), `order_id` (FK orders), `menu_id` (FK menus nullable — menu may be deleted), `menu_name_snapshot` (text), `menu_price_snapshot` (numeric), `quantity` (int, positive CHECK), `subtotal` (numeric, computed = price_snapshot * quantity)
- [ ] Design `order_total` — stored as computed column or trigger on `orders` derived from `order_items` sum
- [ ] Design `audit_logs` table: `id`, `order_id`, `action`, `actor` (seller uid or system), `metadata` (jsonb), `created_at`
- [ ] Add CHECK constraints for valid enum transitions (document the allowed transitions)
- [ ] Add indexes: `orders(order_status)`, `orders(payment_status)`, `orders(created_at)`, `orders(tracking_token_hash)`, `orders(order_number)`, `order_items(order_id)`
- [ ] Write RLS policies:
  - `menus`: public SELECT for `is_active=true AND is_available=true`; INSERT/UPDATE/DELETE only for authenticated seller (via `auth.uid()` check against a single-row `seller_config` or via `auth.role() = 'authenticated'` since single-seller)
  - `orders`: no direct public SELECT/INSERT (all buyer ops go through service-role in backend); seller SELECT/UPDATE via authenticated
  - `order_items`: same as orders
  - `audit_logs`: INSERT via service role only; SELECT for authenticated seller
- [ ] Define Storage bucket `payment-proofs` as private
- [ ] Write Storage policies: service-role can upload and read; authenticated seller can read; no public access
- [ ] Add `idempotency_key` unique index on `orders` table; define behavior: if backend receives `Idempotency-Key` header and key already exists in DB, return the existing order (HTTP 200) without creating a new one
- [ ] Define Storage bucket `menu-images` as public (read) for menu image serving

**Relevant Context:**
- `payment_status` enum values: `pending_payment`, `pending_verification`, `paid`, `rejected`
- `order_status` enum values: `awaiting_payment`, `waiting_processing`, `processing`, `completed`, `cancelled`
- Valid status transitions (enforced in service layer, documented here for reference):
  - `awaiting_payment` → `waiting_processing` (on payment confirmed) or `cancelled`
  - `waiting_processing` → `processing` or `cancelled`
  - `processing` → `completed` or `cancelled`
  - `payment: pending_payment` → `pending_verification` (on proof upload)
  - `payment: pending_verification` → `paid` or `rejected`
- Single-seller system: RLS "seller check" uses `auth.uid() = '<ALLOWED_SELLER_UID>'` — hardened against any other authenticated Supabase user accidentally having access; UID is set via DB migration or env var reference in policy
- `order_number` format: `ORD-YYYYMMDD-XXXX` (date + 4-char random alphanumeric), unique index guarantees no collision

---

## Sub-Task 3 — Auth, Dependencies, and Error Handling

**Status:** `[ ] pending`

**Intent:**
Implement reusable FastAPI dependencies for seller authentication (JWT validation via Supabase), a standardized error response model, and the rate limiter setup. These are used by all subsequent routers.

**Expected Outcomes:**
- `dependencies/auth.py` exports `require_seller` dependency that validates Supabase JWT and returns seller uid; returns 401 on invalid/missing token.
- `dependencies/rate_limit.py` configures `slowapi` limiter instance for reuse across routers.
- `schemas/common.py` defines `ErrorResponse` Pydantic model used consistently across all error returns.
- All 401/403/404/422/429/500 errors return `{"error": {"code": "...", "message": "..."}}` — never raw FastAPI defaults on public endpoints.

**Todo List:**
- [ ] Create `dependencies/auth.py`: extract Bearer token from `Authorization` header, verify with `SUPABASE_JWT_SECRET` using `PyJWT`, raise `HTTPException(401)` on failure; verify `sub` (uid) matches `settings.ALLOWED_SELLER_UID`, raise `HTTPException(403)` if not; return verified seller uid
- [ ] Create `dependencies/rate_limit.py`: initialize `slowapi.Limiter` with `key_func=get_remote_address`; attach to app in `main.py`
- [ ] Create `schemas/common.py`: `ErrorDetail` and `ErrorResponse` models; helper `error_response(code, message)` factory
- [ ] Update `main.py`: register `slowapi` exception handler for 429; override FastAPI's default 422 handler to use `ErrorResponse` format

**Relevant Context:**
- Supabase JWTs are signed with `SUPABASE_JWT_SECRET` (found in Supabase project settings → API → JWT Secret)
- `require_seller` is injected via `Depends(require_seller)` in all seller routers
- Do NOT use Supabase Python SDK's auth verification — verify JWT directly with PyJWT for reliability and no network call
- Rate limit for public endpoints: 20/minute for order creation, 10/minute for proof upload, 30/minute for tracking
- `require_seller` enforces two checks: (1) valid JWT signature + not expired, (2) `sub` == `ALLOWED_SELLER_UID` — 401 for invalid JWT, 403 for valid JWT but wrong UID

---

## Sub-Task 4 — Menu API

**Status:** `[ ] pending`

**Intent:**
Implement all menu endpoints: public read APIs (listing active menus, viewing menu detail) and seller-authenticated write APIs (create, edit, toggle availability/active status, image upload). Image upload is a dedicated endpoint that validates file and returns a hosted URL.

**Expected Outcomes:**
- `GET /menus` — public, returns list of active+available menus.
- `GET /menus/{id}` — public, returns single active+available menu detail.
- `POST /seller/menus` — seller only, creates menu (references `image_url` returned by upload endpoint).
- `PATCH /seller/menus/{id}` — seller only, partial update (name, description, price, image_url, is_available, is_active).
- `PATCH /seller/menus/{id}/availability` — seller only, quick toggle available/unavailable.
- `POST /seller/menus/upload-image` — seller only, multipart upload; validates jpeg/png/webp, max 5MB; uploads to `menu-images` bucket in Supabase Storage; returns `{"image_url": "..."}`.
- Price changes do NOT retroactively affect existing order snapshots (enforced by snapshot design in Sub-Task 2).
- All seller endpoints return 401 if unauthenticated, 403 if wrong seller UID.

**Todo List:**
- [ ] Create `schemas/menu.py`: `MenuCreate`, `MenuUpdate` (all optional fields for PATCH), `MenuResponse`, `MenuListResponse`, `ImageUploadResponse`
- [ ] Create `services/menu_service.py`: `get_active_menus()`, `get_menu_detail(id)`, `create_menu(data)`, `update_menu(id, data)`, `toggle_availability(id, is_available)`, `upload_menu_image(file)`
- [ ] Create `routers/menu.py`: public GET endpoints; seller write endpoints in `routers/seller.py` under `/seller/menus`
- [ ] Register routers in `main.py`
- [ ] Validate: price must be > 0; name must not be empty; inactive menus are excluded from public listing
- [ ] Image upload: file type check via `content_type` AND magic bytes (first few bytes of file); max 5MB; sanitize filename; store at `menu-images/{uuid4}.{ext}`; bucket is public-read so `image_url` is a direct public URL
- [ ] Write tests alongside implementation: public listing filter, seller CRUD, image upload (valid/invalid type/size), auth enforcement
- [ ] `MenuUpdate` uses `Optional` fields with `model_config = ConfigDict(extra='forbid')` to reject unknown fields

**Relevant Context:**
- Public GET endpoints use anon Supabase client (RLS filters `is_active=true AND is_available=true`)
- All seller write endpoints use service-role client after `require_seller` validates JWT + UID
- `menu-images` Storage bucket: public read (so `image_url` can be embedded directly in menu response); write restricted to service-role only
- Image upload endpoint is at `POST /seller/menus/upload-image` — before creating a menu, seller uploads image first, gets back URL, then includes URL in `POST /seller/menus` body
- No service-role key touches the frontend — all uploads go through the FastAPI backend

---

## Sub-Task 5 — Order Creation, Tracking, and Proof Upload

**Status:** `[ ] pending`

**Intent:**
Implement the buyer-facing order flow: create order (with server-side price calculation, snapshot, and idempotency), upload payment proof (with re-upload guard), and track order status using the secret token. All buyer operations are unauthenticated at the HTTP level but protected via token and service-role backend logic.

**Expected Outcomes:**
- `POST /orders` — creates order; accepts optional `Idempotency-Key` header; returns `order_number` and `tracking_token` (plain, shown once only); rate-limited (20/min).
- `POST /orders/{order_number}/proof` — uploads payment proof image; requires `X-Tracking-Token` header (hashed to verify ownership); validates file type (jpeg/png/webp) via content-type + magic bytes, size ≤ 5MB; **blocked** if `payment_status` is already `paid`, `rejected`, or `order_status` is `cancelled`; moves order to `pending_verification`; rate-limited (10/min).
- `GET /orders/track/{tracking_token}` — returns order status, items, total, payment status; 404 if token invalid; rate-limited (30/min).
- Backend fetches prices from DB; buyer-provided prices are ignored.
- Unavailable or inactive menu items reject the whole order with a clear error listing which items are unavailable.
- `tracking_token` is `secrets.token_urlsafe(32)` (43 chars), SHA-256 hashed before DB storage.
- `order_number` is unique (`ORD-YYYYMMDD-XXXX` format).
- Idempotency: if `Idempotency-Key` header matches existing row, return existing order (HTTP 200) without creating duplicate.

**Todo List:**
- [ ] Create `schemas/order.py`: `OrderItemInput`, `OrderCreateRequest` (with optional `idempotency_key` field mapped from header), `OrderCreateResponse` (includes `tracking_token`), `OrderTrackResponse`, `ProofUploadResponse`
- [ ] Create `services/order_service.py`:
  - `create_order(data, idempotency_key)`: check idempotency_key collision first → validate menu availability → fetch prices → compute totals → generate order_number + tracking token → hash token → insert order + order_items atomically via Supabase RPC → return plain token
  - `upload_proof(order_number, file, plain_token)`: hash token → verify ownership → **check upload is allowed** (payment_status must be `pending_payment` or `pending_verification` only, order not cancelled) → validate file type+size → upload to Storage → update to `pending_verification`
  - `track_order(plain_token)`: hash input token → lookup by hash → return order + items snapshot
- [ ] Create `routers/order.py`: wire endpoints, apply rate limits, extract `Idempotency-Key` and `X-Tracking-Token` headers
- [ ] Register router in `main.py` with prefix `/orders`
- [ ] File validation: `content_type` AND first-bytes magic number check for jpeg/png/webp; size ≤ 5MB; filename sanitized with `uuid4` rename
- [ ] Write tests alongside implementation: full happy-path, idempotency key deduplication, re-upload after payment verified (expect 409), wrong tracking token, unavailable menu, price manipulation, file type/size rejection

**Relevant Context:**
- All order writes use service-role client (buyer has no Supabase JWT)
- Atomicity strategy: Supabase RPC (`create_order_with_items`) — PostgreSQL function that inserts `orders` + `order_items` in one transaction; compensating delete is fragile, avoid it
- `secrets.token_urlsafe(32)` → 43-char token; `hashlib.sha256(token.encode()).hexdigest()` for storage
- `order_number` collision: retry up to 3 times with new random suffix before raising 500
- Upload re-upload guard: allowed states = `{pending_payment, pending_verification}` AND order_status != `cancelled`; all other states return 409 `PROOF_UPLOAD_NOT_ALLOWED`
- Do NOT store plain tracking token anywhere — buyer must save their link; document in README
- Storage path: `payment-proofs/{order_id}/{uuid4}.{ext}`

---

## Sub-Task 6 — Seller Order Management, Payment Verification, and History

**Status:** `[ ] pending`

**Intent:**
Implement seller-authenticated endpoints for managing the order lifecycle: viewing active orders, viewing detail with proof, verifying/rejecting payment, advancing order through processing states, cancelling orders, and querying history with pagination and date/status filters.

**Expected Outcomes:**
- `GET /seller/orders` — list active orders (status not in completed/cancelled); seller only.
- `GET /seller/orders/{order_number}` — order detail + signed URL for payment proof if present; seller only.
- `POST /seller/orders/{order_number}/verify-payment` — marks payment as `paid`, order as `waiting_processing`; logs action.
- `POST /seller/orders/{order_number}/reject-payment` — body: `{reason}`, marks payment `rejected`, order `cancelled`; logs action.
- `POST /seller/orders/{order_number}/start-processing` — moves order to `processing`; validates current status is `waiting_processing`.
- `POST /seller/orders/{order_number}/complete` — moves to `completed`.
- `POST /seller/orders/{order_number}/cancel` — body: `{reason}`, moves to `cancelled` from any non-terminal state; logs action.
- `GET /seller/history` — paginated list of completed/cancelled orders; supports `?page`, `?page_size`, `?status`, `?date_from`, `?date_to`.
- All status transitions validated; illegal transitions return 409 with clear message.
- All mutating seller actions write to `audit_logs`.

**Todo List:**
- [ ] Create `schemas/seller_order.py`: `OrderListItem`, `OrderDetail`, `OrderDetailResponse` (includes signed proof URL), `PaymentRejectRequest`, `CancelRequest`, `HistoryQueryParams`, `HistoryResponse`
- [ ] Create `services/seller_order_service.py`:
  - `list_active_orders()` — query orders where status NOT IN terminal states, ordered by `created_at` asc
  - `get_order_detail(order_number)` — fetch order + items + generate signed URL for proof path (Supabase Storage signed URL, 1-hour expiry)
  - `verify_payment(order_number, seller_uid)` — validate transition → update → audit log
  - `reject_payment(order_number, reason, seller_uid)` — validate → update → audit log
  - `start_processing(order_number, seller_uid)` — validate → update → audit log
  - `complete_order(order_number, seller_uid)` — validate → update → audit log
  - `cancel_order(order_number, reason, seller_uid)` — validate → update → audit log
  - `get_history(params)` — paginated query with filters
- [ ] Create `routers/seller.py`: all routes under `/seller`, all protected by `require_seller`
- [ ] Register router in `main.py` with prefix `/seller`
- [ ] Transition guard: `_assert_valid_transition(current_status, target_status)` helper raises 409 on invalid
- [ ] History: `page_size` max 100, default 20; return `{data: [...], total: int, page: int, page_size: int}`
- [ ] Signed URL for proof: use Supabase Storage `create_signed_url(bucket, path, expires_in=3600)` via service-role client

**Relevant Context:**
- "Active orders" = `order_status` IN `awaiting_payment`, `waiting_processing`, `processing`
- "History" = `order_status` IN `completed`, `cancelled`
- Audit log entry: `{order_id, action: "payment_verified"|"payment_rejected"|"order_cancelled"|..., actor: seller_uid, metadata: {reason?, previous_status}}`
- Rejection message to include in README: "Jika pembayaran sudah dilakukan namun bukti ditolak, hubungi UMKM langsung untuk proses refund. Refund tidak otomatis."
- Signed URL approach hides actual Storage path from buyers/public; only seller sees it via this endpoint

---

## Sub-Task 7 — Supabase Realtime Integration

**Status:** `[ ] pending`

**Intent:**
Document and configure secure Supabase Realtime access for the seller dashboard so it can subscribe to live order updates. Backend configures the channel permissions; frontend will subscribe directly to Supabase Realtime using the seller's JWT. No backend WebSocket proxying needed.

**Expected Outcomes:**
- `schema.sql` includes Realtime publication setup for `orders` and `order_items` tables.
- `README.md` documents the Realtime channel name, which events to subscribe to (`INSERT`, `UPDATE`), and the filter pattern for the seller dashboard.
- RLS policies on `orders` already cover Realtime (Supabase Realtime respects RLS for authenticated users).
- A section in README explains that the frontend must pass the seller's Supabase JWT when initializing the Realtime client to get authorized channel access.
- No sensitive server-side keys are used or needed on the frontend for Realtime.

**Todo List:**
- [ ] Add `ALTER PUBLICATION supabase_realtime ADD TABLE orders, order_items;` to `schema.sql`
- [ ] Verify RLS policies from Sub-Task 2 cover Realtime SELECT access for authenticated seller
- [ ] Document in `README.md`: Realtime setup, channel subscription pattern, filter by `order_status`, event types, JWT usage
- [ ] Add note in README: buyers do NOT get Realtime access — they poll `GET /orders/track/{token}` instead

**Relevant Context:**
- Supabase Realtime automatically enforces RLS for Postgres Changes subscriptions when using anon/user JWT
- Frontend Realtime client uses `supabase-js` with the seller's session JWT — no extra backend endpoint needed
- Channel filter example: `{event: '*', schema: 'public', table: 'orders'}` with RLS doing the access control

---

## Sub-Task 8 — Tests

**Status:** `[ ] pending`

**Intent:**
Final integration test run and coverage review. Unit and feature tests are written incrementally in Sub-Tasks 4, 5, and 6. This sub-task runs the full suite end-to-end, identifies any remaining gaps, fills them, and documents failures.

**Expected Outcomes:**
- All tests written in Sub-Tasks 4–6 run without errors or failures are documented.
- Integration tests covering cross-feature flows pass (e.g., create order → upload proof → seller history shows completed order).
- `tests/test_security.py` covers auth bypass and input manipulation scenarios.
- Any failures documented in `README.md` under "Known Test Limitations" with root cause.
- No production data touched.

**Todo List:**
- [ ] Run full test suite: `pytest tests/ -v --tb=short`; fix any failures not already documented
- [ ] Add `tests/test_security.py` if not created during earlier sub-tasks:
  - Valid JWT but wrong UID (expect 403)
  - Expired JWT (expect 401)
  - Malformed JWT (expect 401)
  - Status field in order creation request body ignored
  - Role field in request body ignored
  - Proof re-upload after payment verified (expect 409 `PROOF_UPLOAD_NOT_ALLOWED`)
  - Idempotency-Key deduplication (second request returns 200 with same order)
- [ ] Add integration test: full order lifecycle from creation to completion, assert history entry exists with correct snapshot
- [ ] Review test coverage; add missing tests for any documented endpoint not yet covered
- [ ] Document in README: which tests require a real Supabase project vs fully mocked; how to run each group

**Relevant Context:**
- Tests written incrementally in Sub-Tasks 4, 5, 6: feature tests live in `tests/test_menu.py`, `tests/test_orders.py`, `tests/test_seller.py`
- `tests/conftest.py` created in Sub-Task 1 scaffold; updated with fixtures as needed during each sub-task
- Use `pytest-asyncio` with `asyncio_mode = "auto"` in `pytest.ini`
- `ENVIRONMENT=test` env var enables mock Supabase client in `db.py`; real Supabase tests tagged with `@pytest.mark.integration`
- Never hardcode real credentials; use `pytest-dotenv` or separate `.env.test` with dummy values

---

## Sub-Task 9 — README and API Contract Documentation

**Status:** `[ ] pending`

**Intent:**
Complete the README with full setup instructions, environment variable guide, database setup steps, server run commands, test run commands, and the API contract reference (all endpoints, methods, auth, request/response schemas, status codes, error format, example curl commands). This is the primary integration guide for the frontend team.

**Expected Outcomes:**
- `README.md` is complete and self-sufficient for a new developer to set up the project.
- API contract section documents every endpoint with: HTTP method, path, auth requirement, request body schema, response schema, status codes, and one curl example.
- Error format is documented with all defined error codes.
- Deployment section covers Railway setup, environment variable injection, and Vercel (future frontend) setup.
- Known limitations and residual risks are documented.

**Todo List:**
- [ ] Setup section: Python version, venv creation, `pip install -r requirements.txt`, copy `.env.example` to `.env`
- [ ] Supabase setup: create project, run `schema.sql` in SQL editor, configure Storage bucket, note JWT secret location
- [ ] Running server: `uvicorn main:app --reload`
- [ ] Running tests: `pytest tests/ -v`
- [ ] Full API contract table for all endpoints
- [ ] Error response format documentation: `{"error": {"code": "string", "message": "string"}}`
- [ ] All defined error codes (e.g. `MENU_NOT_AVAILABLE`, `INVALID_TRACKING_TOKEN`, `INVALID_STATUS_TRANSITION`, `UNAUTHORIZED`, `FORBIDDEN`, `VALIDATION_ERROR`, `FILE_TOO_LARGE`, `INVALID_FILE_TYPE`, `PROOF_UPLOAD_NOT_ALLOWED`, `DUPLICATE_IDEMPOTENCY_KEY`)
- [ ] Curl examples for: create order, upload proof, track order, verify payment, get history
- [ ] Realtime subscription guide for frontend
- [ ] Tracking token warning: "Token hanya ditampilkan sekali. Simpan link tracking Anda."
- [ ] Refund disclaimer for rejected payments
- [ ] Known limitations: in-memory rate limit resets on restart, token non-recoverable, single-seller assumption, no automatic payment verification
- [ ] Deployment: Railway env var setup, Vercel (future), Supabase free tier limits

---

## Deployment Architecture (for reference)

```
Buyer Browser          Seller Browser (Vue 3, future)
     |                        |
     | HTTP                   | HTTP + Supabase Realtime WS
     v                        v
[Railway — FastAPI]    [Vercel — Vue 3 + Vite]
     |                        |
     |    service-role        |   anon key + seller JWT
     +--------+  +------------+
              |  |
         [Supabase]
    PostgreSQL + Auth + Storage + Realtime
```

## Security Residual Risks (to document in README)

- Rate limits reset on Railway restart (slowapi in-memory)
- Tracking token non-recoverable if lost (by design)
- Manual payment verification — seller must check QRIS transaction manually
- Single-seller access controlled by `ALLOWED_SELLER_UID` env var — if var is misconfigured, wrong account gets access; verify on deploy
- File content validation is type/size + magic bytes only (no deep malware scan)
- No automatic refund mechanism — buyer directed to contact UMKM manually
- Idempotency key is optional; clients that omit it and retry may create duplicate orders (acceptable trade-off for simplicity)
- `menu-images` bucket is public-read — image URLs are guessable if path is known; acceptable for menu images (not sensitive)
