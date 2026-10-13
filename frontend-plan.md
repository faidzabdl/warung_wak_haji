# Frontend Plan — UMKM Ordering Web App

## Top-Level Overview

Build a functional Vue 3 + Vite + TypeScript + Tailwind CSS + shadcn-vue web application
that consumes the existing FastAPI backend at `http://localhost:8000`.

**Two distinct user surfaces:**
- **Buyer** — unauthenticated; browses menu, creates orders, uploads payment proof, tracks order status
- **Seller** — authenticated via Supabase Auth (email/password login using supabase-js); manages menus, verifies payments, processes and completes orders, views history

**Auth mechanism (confirmed):**  
Seller logs in with `supabase.auth.signInWithPassword()`. The resulting `session.access_token`
is a Supabase JWT with `aud: "authenticated"` and `sub` equal to `ALLOWED_SELLER_UID`.
This token is sent as `Authorization: Bearer <token>` on all seller API calls.
No service-role key or JWT secret ever touches the frontend.

**Scope:** Frontend only. Backend and database are not modified.

**Non-goals:** Final visual design, animations, multi-seller support, real-time subscription (documented but not wired in this phase).

---

## Key API Contract Facts (grounded in backend code)

- Error envelope: `{ "error": { "code": "...", "message": "..." } }` — always
- Validation errors (422) add `"details": [{ "field", "message" }]`
- Seller auth header (exact): `Authorization: Bearer <supabase_access_token>`
- Buyer proof upload header (exact): `X-Tracking-Token: <plain_token>`
- Buyer order idempotency header (optional): `Idempotency-Key: <client_uuid>`
- Tracking token shown once (201 response only); 200 duplicate response has no token
- File uploads: JPEG/PNG/WebP only, max 5 MB, validated by backend via content-type + magic bytes
- Rate limits (per IP): POST /orders 20/min, proof upload 10/min, track 30/min

---

## Sub-Task 1 — Project Scaffold

**Status:** `[ ] pending`

**Intent:**  
Bootstrap the Vue 3 + Vite + TypeScript project inside a `frontend/` subdirectory.
Install and configure Tailwind CSS and shadcn-vue. Set up environment variables and
the base project structure that all other sub-tasks build on.

**Expected Outcomes:**
- `frontend/` directory exists with a working Vite project
- `npm run dev` starts without errors at `http://localhost:5173`
- `npm run build` completes without TypeScript or build errors
- Tailwind CSS is working (can use utility classes)
- shadcn-vue is initialized with Button, Badge, Card, Input, Label, Textarea, Select, Skeleton, Sonner components added
- `.env` has `VITE_API_URL=http://localhost:8000` and `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`
- `.env.example` documents all three vars without real values
- `frontend/` is gitignored from `node_modules` perspective (.gitignore updated)

**Todo List:**
- [ ] Run `npm create vite@latest frontend -- --template vue-ts` from workspace root
- [ ] `cd frontend && npm install`
- [ ] Install Tailwind: `npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`
- [ ] Configure `tailwind.config.js` content paths to include `./src/**/*.{vue,ts,tsx}`
- [ ] Add Tailwind directives to `src/style.css` (or `src/index.css`)
- [ ] Install shadcn-vue: follow `npx shadcn-vue@latest init` (choose default style, slate color, CSS variables)
- [ ] Add components: `npx shadcn-vue@latest add button badge card input label textarea select skeleton sonner`
- [ ] Create `frontend/.env` with `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [ ] Create `frontend/.env.example` with placeholder values (no real secrets)
- [ ] Install Vue Router: `npm install vue-router@4`
- [ ] Install Supabase JS: `npm install @supabase/supabase-js`
- [ ] Clean up default Vite boilerplate (remove HelloWorld, Counter components)
- [ ] Verify `npm run dev` and `npm run build` pass

**Relevant Context:**
- Project root is `d:\projek\umkm`; frontend lives at `d:\projek\umkm\frontend\`
- `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` come from Supabase Dashboard → Settings → API
- `VITE_SUPABASE_ANON_KEY` is the public anon key — safe for frontend
- Never add `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_JWT_SECRET` to frontend env vars

---

## Sub-Task 2 — API Client, Auth Store, and Router

**Status:** `[ ] pending`

**Intent:**  
Create the typed API client layer and auth store before building any UI pages.
This ensures every page uses consistent request/response types and auth headers,
and avoids having to refactor scattered `fetch()` calls later.

**Expected Outcomes:**
- `src/lib/api.ts` — typed API client for all endpoints; auto-injects `Authorization` header for seller calls
- `src/lib/supabase.ts` — Supabase client initialized with `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`
- `src/stores/auth.ts` — Pinia store managing seller session; `login()`, `logout()`, `session` ref
- `src/router/index.ts` — Vue Router with buyer routes and seller routes; seller routes guarded by auth
- `src/types/api.ts` — TypeScript interfaces matching exact backend schema field names

**Todo List:**
- [ ] Install Pinia: `npm install pinia`
- [ ] Create `src/types/api.ts` with interfaces: `MenuResponse`, `OrderCreateRequest`, `OrderCreateResponse`, `OrderTrackResponse`, `OrderItemSnapshot`, `ProofUploadResponse`, `OrderListItem`, `OrderDetailResponse`, `HistoryResponse`, `HistoryItem`, `ApiError`
- [ ] Create `src/lib/supabase.ts` — `createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)`
- [ ] Create `src/stores/auth.ts` — Pinia store with `session` (Supabase Session | null), `login(email, password)` calling `supabase.auth.signInWithPassword()`, `logout()` calling `supabase.auth.signOut()`, `accessToken` computed from session; restore session on app init via `supabase.auth.getSession()`
- [ ] Create `src/lib/api.ts`:
  - Base URL from `import.meta.env.VITE_API_URL`
  - `request(method, path, options)` — generic fetch wrapper; throws structured error on non-2xx
  - Error parsing: extract `error.code` and `error.message` from response body
  - Buyer functions: `getMenus()`, `getMenuDetail(id)`, `createOrder(body, idempotencyKey?)`, `uploadProof(orderNumber, file, trackingToken)`, `trackOrder(token)`
  - Seller functions: `getSellerMenus(token)`, `uploadMenuImage(file, token)`, `createMenu(body, token)`, `updateMenu(id, body, token)`, `setMenuAvailability(id, isAvailable, token)`, `getSellerOrders(token)`, `getOrderDetail(orderNumber, token)`, `verifyPayment(orderNumber, token)`, `rejectPayment(orderNumber, reason, token)`, `startProcessing(orderNumber, token)`, `completeOrder(orderNumber, token)`, `cancelOrder(orderNumber, reason, token)`, `getHistory(params, token)`
  - `uploadProof` must set header `X-Tracking-Token: <token>` (exact case) and send multipart form
  - `uploadMenuImage` must send multipart form with field name `file`
  - POST /orders must set header `Idempotency-Key` when provided
- [ ] Create `src/router/index.ts` with routes:
  - Buyer: `/` (menu list), `/menu/:id` (menu detail), `/checkout` (cart/checkout), `/order/:orderNumber/proof` (upload proof), `/track` (tracking input), `/track/:token` (tracking result)
  - Seller: `/seller/login`, `/seller/dashboard` (redirect to orders), `/seller/menus`, `/seller/orders`, `/seller/history`
  - Navigation guard: redirect `/seller/*` to `/seller/login` if no auth session
- [ ] Register Pinia and Router in `src/main.ts`

**Relevant Context:**
- `Authorization` header format: `Bearer ${accessToken}` — sent on all seller API calls
- `X-Tracking-Token` header: plain token string, NOT hashed (backend hashes it)
- `Idempotency-Key` header: client-generated UUID v4 (use `crypto.randomUUID()`)
- File upload field name is `file` for both buyer proof and seller image uploads
- Supabase `session.access_token` expires; use `supabase.auth.onAuthStateChange` to refresh
- Never store session in localStorage manually — supabase-js handles persistence

---

## Sub-Task 3 — Buyer Pages: Menu and Checkout

**Status:** `[ ] pending`

**Intent:**  
Build all buyer-facing pages for browsing menus, adding to cart, and creating an order.
The cart is client-side state only (no backend persistence for cart). Order creation
calls `POST /orders` with the exact schema the backend expects.

**Expected Outcomes:**
- `/` — `MenuListPage.vue`: fetches `GET /menus`, shows name, price, description, image (if any), availability badge. "Tambah" button adds to cart.
- `/menu/:id` — `MenuDetailPage.vue`: fetches `GET /menus/{id}`, shows full detail, quantity selector, "Tambah ke Keranjang" button.
- `/checkout` — `CheckoutPage.vue`: shows cart items (quantity editable, removable), `buyer_name` text input, optional `notes` textarea, total calculated client-side for display only (backend recalculates authoritatively). "Pesan Sekarang" calls `POST /orders`. On 201 success: show `order_number` and `tracking_token` prominently with copy button and warning "Simpan token ini — tidak dapat ditampilkan ulang." Navigate to `/order/:orderNumber/proof`. On 400 (MENU_NOT_AVAILABLE): show which item is unavailable.
- Cart state managed via Pinia store `src/stores/cart.ts`
- Loading states on all API calls; error messages shown inline

**Todo List:**
- [ ] Add shadcn-vue components: `npm run shadcn-vue add badge card`  (if not already added)
- [ ] Create `src/stores/cart.ts` — Pinia store: `items: CartItem[]`, `addItem(menu)`, `removeItem(menuId)`, `updateQuantity(menuId, qty)`, `clear()`, `total` computed
- [ ] Create `src/pages/buyer/MenuListPage.vue` — calls `getMenus()`, renders card grid with name, price (formatted as Rupiah), description, availability badge (shadcn Badge), "Tambah" button per menu item
- [ ] Create `src/pages/buyer/MenuDetailPage.vue` — calls `getMenuDetail(id)`, quantity stepper (min 1), "Tambah ke Keranjang" button
- [ ] Create `src/pages/buyer/CheckoutPage.vue`:
  - Show cart items table: name, price per item, quantity input, subtotal, remove button
  - Show estimated total (client-side sum for display)
  - `buyer_name` required input, `notes` optional textarea
  - "Pesan Sekarang" button — calls `createOrder()` with `Idempotency-Key: crypto.randomUUID()`
  - On 201: display `order_number` and `tracking_token` in a prominent alert box with copy buttons; warning text about one-time token; "Lanjut Upload Bukti" button navigates to `/order/${order_number}/proof` and passes token via router state
  - On 200 (duplicate): show "Pesanan sudah ada" message with `order_number`
  - On error: show `error.message` from API response
- [ ] Create `src/components/buyer/CartItem.vue` — reusable cart row component
- [ ] Create `src/components/NavBar.vue` — simple top nav: logo/name, "Keranjang (N)" link, "Lacak Pesanan" link, "Penjual" link
- [ ] Wire router-view in `App.vue`

**Relevant Context:**
- `OrderCreateRequest` fields: `buyer_name` (required, non-empty), `items` (array of `{menu_id, quantity}`), `notes` (optional)
- `extra='forbid'` on backend — do NOT send any extra fields like `price` or `total`
- On 201: response has `order_number`, `tracking_token`, `total_amount`, `message`
- On 200 (duplicate idempotency): response has `order_number`, `message`, `total_amount` — NO `tracking_token`
- Price display: use `Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' })`
- Inactive/unavailable menus are filtered out by backend RLS on `GET /menus` — no need to filter client-side

---

## Sub-Task 4 — Buyer Pages: Proof Upload and Order Tracking

**Status:** `[ ] pending`

**Intent:**  
Build the payment proof upload page and order tracking page.
These two pages complete the buyer's post-order flow.

**Expected Outcomes:**
- `/order/:orderNumber/proof` — `ProofUploadPage.vue`: accepts `orderNumber` from route param; reads `tracking_token` from router location state (set by checkout page). If no token in state, shows a form to manually enter token. File input (JPEG/PNG/WebP, max 5MB validated client-side first). "Upload Bukti" button calls `POST /orders/{orderNumber}/proof` with `X-Tracking-Token` header. On success: shows payment status `pending_verification` and link to tracking page.
- `/track` — `TrackInputPage.vue`: simple form with one input for tracking token; on submit navigates to `/track/:token`
- `/track/:token` — `TrackOrderPage.vue`: calls `GET /orders/track/{token}` on mount; displays order number, buyer name, order status (with human-readable Indonesian labels), payment status, items list with name/quantity/price/subtotal, total amount, notes (if any). Status badges with color coding. "Refresh" button to re-fetch. On 404: "Token tidak ditemukan atau tidak valid."

**Todo List:**
- [ ] Create `src/pages/buyer/ProofUploadPage.vue`:
  - `orderNumber` from `useRoute().params.orderNumber`
  - `trackingToken` from `useRoute().state?.trackingToken` OR manual input field if not present
  - File picker restricted to `image/jpeg,image/png,image/webp`; client-side size check ≤ 5MB before submit
  - Show file preview (using `URL.createObjectURL`)
  - Call `uploadProof(orderNumber, file, trackingToken)` — sets multipart form + `X-Tracking-Token` header
  - Handle 409 `PROOF_UPLOAD_NOT_ALLOWED` with specific message
  - Handle 403 `FORBIDDEN` (wrong token) with message
  - On success: show `payment_status` returned, link to `/track/${token}`
- [ ] Create `src/pages/buyer/TrackInputPage.vue`:
  - Single text input for tracking token
  - On submit: navigate to `/track/${token}`
- [ ] Create `src/pages/buyer/TrackOrderPage.vue`:
  - Calls `trackOrder(token)` on mount and on "Refresh"
  - Display: `OrderTrackResponse` fields — order_number, buyer_name, created_at, notes
  - Order status badge (color: awaiting_payment=yellow, waiting_processing=blue, processing=orange, completed=green, cancelled=red)
  - Payment status badge (pending_payment=gray, pending_verification=yellow, paid=green, rejected=red)
  - Items table: menu_name, menu_price, quantity, subtotal (all from `items` array using field names: `menu_name`, `menu_price`, `quantity`, `subtotal`)
  - Total amount
  - 404 error: clear message "Token tidak valid atau pesanan tidak ditemukan"
- [ ] Create `src/components/buyer/StatusBadge.vue` — reusable badge with status → label + color mapping
- [ ] Add `src/utils/format.ts` — `formatRupiah(amount: number | string)`, `formatDate(dateStr: string)`, `orderStatusLabel(status: string)`, `paymentStatusLabel(status: string)` — all labels in Indonesian

**Relevant Context:**
- `OrderTrackResponse` item fields (exact): `menu_name`, `menu_price`, `quantity`, `subtotal`
- `OrderTrackResponse` fields (exact): `order_number`, `buyer_name`, `order_status`, `payment_status`, `total_amount`, `items`, `notes`, `created_at`, `updated_at`
- Router state for passing token: use `router.push({ name: 'proof', params: { orderNumber }, state: { trackingToken } })`
- Client-side file validation before API call prevents wasting rate limit quota on obviously invalid files
- Rate limit on track endpoint: 30/minute — show a message if 429 received

---

## Sub-Task 5 — Seller Auth and Menu Management

**Status:** `[ ] pending`

**Intent:**  
Build the seller login page and complete menu management (list, create, edit, availability toggle).
This is the first seller surface and establishes the authenticated seller shell.

**Expected Outcomes:**
- `/seller/login` — `SellerLoginPage.vue`: email/password form; calls `supabase.auth.signInWithPassword()`; on success navigates to `/seller/orders`; shows auth errors inline.
- `/seller/menus` — `SellerMenuPage.vue`: fetches `GET /seller/menus` (all menus including inactive); table with name, price, availability toggle, active/inactive badge, edit button.
- Availability toggle calls `PATCH /seller/menus/{id}/availability` immediately on click with `{ is_available: boolean }`.
- Edit menu opens an inline form or modal (not a separate page) pre-filled with current values; calls `PATCH /seller/menus/{id}`.
- "Tambah Menu" button opens create form; first step uploads image via `POST /seller/menus/upload-image`; second step creates menu via `POST /seller/menus`.
- Seller layout: persistent sidebar or top nav showing: Pesanan, Menu, Riwayat, Logout.
- Route guard redirects to `/seller/login` if no session.

**Todo List:**
- [ ] Add shadcn-vue: `npx shadcn-vue@latest add dialog switch table` (for modal, toggle, table)
- [ ] Create `src/layouts/SellerLayout.vue` — wrapper with nav links (Pesanan, Menu, Riwayat) and Logout button; uses `<router-view>` inside
- [ ] Create `src/pages/seller/SellerLoginPage.vue`:
  - Email + password inputs; "Masuk" button
  - Calls `authStore.login(email, password)`
  - On success: navigate to `/seller/orders`
  - On error: show error message (wrong credentials, network error)
  - If already logged in: redirect to `/seller/orders`
- [ ] Create `src/pages/seller/SellerMenuPage.vue`:
  - On mount: call `getSellerMenus(token)` and render table
  - Table columns: Nama, Harga, Tersedia (toggle), Status (Aktif/Nonaktif badge), Aksi (Edit button)
  - Availability toggle: calls `setMenuAvailability(id, newValue, token)` immediately; optimistic update + revert on error
  - Edit button: opens `MenuEditDialog.vue` with current values pre-filled
  - "Tambah Menu" button: opens `MenuCreateDialog.vue`
- [ ] Create `src/components/seller/MenuEditDialog.vue`:
  - shadcn Dialog containing a form with all `MenuUpdate` fields (name, description, price, image_url, is_available, is_active)
  - Image upload sub-section: file picker + "Upload Gambar" button calls `uploadMenuImage`; on success fills `image_url` field automatically
  - "Simpan" calls `updateMenu(id, changedFieldsOnly, token)` — only send non-null/changed fields
  - Shows validation errors from API
- [ ] Create `src/components/seller/MenuCreateDialog.vue`:
  - Step 1: optional image upload (calls `uploadMenuImage`) → `image_url` auto-filled
  - Step 2: full `MenuCreate` form (name required, price required > 0, description optional, is_available, is_active)
  - "Buat Menu" calls `createMenu(body, token)` → on success close dialog + refresh list
- [ ] Update router: apply `SellerLayout` as parent layout for all `/seller/*` routes except login

**Relevant Context:**
- `MenuCreate` fields: `name` (required), `price` (required, > 0), `description` (optional), `image_url` (optional), `is_available` (default true), `is_active` (default true) — `extra='forbid'`
- `MenuUpdate`: all optional, only send fields that changed — `extra='forbid'` means unknown fields cause 422
- `AvailabilityUpdate`: `{ is_available: boolean }` only — no other fields
- Image upload returns `{ image_url: string }` — use this as the value for `image_url` in menu create/update
- Access token from `authStore.accessToken` computed property
- `GET /seller/menus` returns ALL menus including inactive (unlike public `GET /menus`)

---

## Sub-Task 6 — Seller Order Management and History

**Status:** `[ ] pending`

**Intent:**  
Build the active orders management page and history page.
Every action button must call the correct backend endpoint with the correct body.
Status transitions must follow backend rules — buttons should only appear for valid transitions.

**Expected Outcomes:**
- `/seller/orders` — `SellerOrdersPage.vue`: fetches `GET /seller/orders`; shows table of active orders. Each row has action buttons based on current status (see transition rules below). Clicking an action calls the correct endpoint. After each action: re-fetch order list.
- `/seller/history` — `SellerHistoryPage.vue`: fetches `GET /seller/history` with pagination and filters; shows completed/cancelled orders with items detail expandable or inline.
- Order detail modal: clicking on order opens `OrderDetailModal.vue` showing all `OrderDetailResponse` fields including payment proof image (signed URL from `payment_proof_url`).
- All action buttons show loading state; errors shown inline with API error message.

**Todo List:**
- [ ] Add shadcn-vue: `npx shadcn-vue@latest add alert-dialog` (for confirm dialogs before destructive actions)
- [ ] Create `src/pages/seller/SellerOrdersPage.vue`:
  - On mount + on "Refresh": call `getSellerOrders(token)`, render table
  - Table columns: No. Pesanan, Nama Pembeli, Status Pesanan, Status Pembayaran, Total, Jumlah Item, Waktu, Aksi
  - Action buttons per status (only show valid actions, not all):
    - `awaiting_payment` + `pending_verification`: show "Verifikasi Pembayaran" and "Tolak Pembayaran"
    - `awaiting_payment` + `pending_payment` or `awaiting_payment` + `paid`: allow "Batalkan"
    - `waiting_processing`: show "Mulai Proses" and "Batalkan"
    - `processing`: show "Selesaikan" and "Batalkan"
  - "Tolak Pembayaran" and "Batalkan" open a reason input dialog before calling API
  - Click row → open `OrderDetailModal.vue`
- [ ] Create `src/components/seller/OrderDetailModal.vue`:
  - Shows all `OrderDetailResponse` fields
  - Items table: `menu_name`, `menu_price`, `quantity`, `subtotal` (exact field names from `OrderItemDetail`)
  - If `payment_proof_url` is not null: show `<img>` with the signed URL
  - `cancel_reason` and `reject_reason` shown if present
- [ ] Create `src/components/seller/ReasonDialog.vue`:
  - shadcn AlertDialog asking for reason text
  - Used for both reject-payment and cancel
  - Validates reason is non-empty before calling API
- [ ] Create `src/pages/seller/SellerHistoryPage.vue`:
  - On mount: call `getHistory({ page: 1, page_size: 20 }, token)`
  - Filter bar: date_from (date input), date_to (date input), status (select: Semua/completed/cancelled)
  - Pagination: prev/next buttons using `total`, `page`, `page_size` from `HistoryResponse`
  - Table: No. Pesanan, Nama Pembeli, Status, Total, Waktu, Alasan (jika ada)
  - Expand row to see items (or show inline)
- [ ] Add auto-refresh to `SellerOrdersPage.vue` — poll `GET /seller/orders` every 30 seconds (simple setInterval; document that Realtime subscription is the better long-term solution per `docs/realtime.md`)

**Relevant Context:**
- Active order statuses: `awaiting_payment`, `waiting_processing`, `processing` (from backend `_ACTIVE_STATUSES`)
- `OrderListItem` fields (exact): `order_number`, `buyer_name`, `order_status`, `payment_status`, `total_amount`, `item_count`, `created_at`
- `OrderDetailResponse` fields (exact): `order_number`, `buyer_name`, `notes`, `order_status`, `payment_status`, `total_amount`, `items`, `payment_proof_url`, `cancel_reason`, `reject_reason`, `created_at`, `updated_at`
- `OrderItemDetail` fields (exact): `menu_name`, `menu_price`, `quantity`, `subtotal`, `menu_id`
- `HistoryItem` fields (exact): `order_number`, `buyer_name`, `order_status`, `payment_status`, `total_amount`, `items`, `cancel_reason`, `reject_reason`, `created_at`
- `HistoryResponse` fields (exact): `data`, `total`, `page`, `page_size`
- History query params: `page`, `page_size`, `status`, `date_from`, `date_to`
- `verify-payment` and `start-processing` and `complete` require NO request body
- `reject-payment` requires `{ reason: string }` (non-empty)
- `cancel` requires `{ reason: string }` (non-empty)
- 409 `INVALID_STATUS_TRANSITION` means button was clicked in wrong state — show API message to user

---

## Sub-Task 7 — Build Verification and Integration Check

**Status:** `[ ] pending`

**Intent:**  
Verify the complete build passes, check that all API calls use correct field names and headers,
and document what works vs what requires a running backend to test.

**Expected Outcomes:**
- `npm run build` completes with zero TypeScript errors and zero build warnings
- `npm run dev` starts cleanly
- All API function signatures in `src/lib/api.ts` match backend contract (field names, headers, paths)
- `src/types/api.ts` interfaces match backend response schemas exactly
- Known integration assumptions documented
- `frontend/README.md` created with: setup instructions, env vars needed, how to run, known limitations

**Todo List:**
- [ ] Run `npm run build` from `frontend/` — fix any TypeScript errors
- [ ] Run `npm run dev` — confirm app starts
- [ ] Cross-check `src/types/api.ts` against backend schemas — verify field names match exactly
- [ ] Cross-check `src/lib/api.ts` endpoint paths against `routers/` files — verify all paths correct
- [ ] Verify `X-Tracking-Token` header is set on proof upload (not `x-tracking-token` — fetch normalizes but be explicit)
- [ ] Verify `Authorization: Bearer ${token}` format on all seller calls
- [ ] Verify `Idempotency-Key` header on order creation
- [ ] Create `frontend/README.md` with setup and known limitations
- [ ] Document that seller login requires a real Supabase project with seller account registered and UID matching `ALLOWED_SELLER_UID` in backend `.env`
- [ ] Document that payment proof image display requires `payment_proof_url` (signed URL with 1-hour expiry from backend)

**Relevant Context:**
- Backend is at `http://localhost:8000` — must be running for integration to work
- Supabase project URL and anon key must be filled in `frontend/.env` for seller login to work
- The frontend `VITE_SUPABASE_ANON_KEY` is the PUBLIC anon key only — never the service role key
- All buyer features work without a Supabase connection (they call FastAPI directly)
- Seller login requires Supabase Auth to be configured and seller account to exist

---

## Architecture Diagram (reference)

```
frontend/src/
├── main.ts                  ← registers Pinia + Router + App
├── App.vue                  ← router-view root
├── router/index.ts          ← all routes + navigation guard
├── stores/
│   ├── auth.ts              ← Supabase session management
│   └── cart.ts              ← buyer cart state
├── lib/
│   ├── supabase.ts          ← Supabase client init
│   └── api.ts               ← all API calls typed
├── types/api.ts             ← TS interfaces matching backend schemas
├── utils/format.ts          ← formatRupiah, formatDate, status labels
├── layouts/
│   └── SellerLayout.vue     ← sidebar nav for seller pages
├── components/
│   ├── NavBar.vue           ← buyer top navigation
│   ├── buyer/
│   │   ├── CartItem.vue
│   │   └── StatusBadge.vue
│   └── seller/
│       ├── MenuEditDialog.vue
│       ├── MenuCreateDialog.vue
│       ├── OrderDetailModal.vue
│       └── ReasonDialog.vue
└── pages/
    ├── buyer/
    │   ├── MenuListPage.vue
    │   ├── MenuDetailPage.vue
    │   ├── CheckoutPage.vue
    │   ├── ProofUploadPage.vue
    │   ├── TrackInputPage.vue
    │   └── TrackOrderPage.vue
    └── seller/
        ├── SellerLoginPage.vue
        ├── SellerMenuPage.vue
        ├── SellerOrdersPage.vue
        └── SellerHistoryPage.vue
```
