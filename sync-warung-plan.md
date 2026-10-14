# Sync Plan — Warung Wak Haji (Backend + Frontend)

## Top-Level Overview

Sinkronisasi aplikasi Warung Wak Haji (FastAPI + Supabase backend, Vue 3 + Tailwind + shadcn frontend)
agar alur bisnis, model status, dan desain UI sesuai dengan prototype `tampilan_pembelian_3.html`.

Perubahan terbesar:
- Model status baru: QRIS dan Cash punya alur berbeda sejak order dibuat
- Status `ready` ditambah (processing → ready → completed)
- Upload bukti bayar dihapus seluruhnya
- `table_number` dan `payment_method` wajib di setiap order
- Menu punya `menu_type` (Makanan/Minuman) dan `category`
- Desain frontend dimigrasi mengikuti prototype (CSS variable, layout seller berubah)

**Sumber Kebenaran:** `tampilan_pembelian_3.html`
**Prinsip:** Backend mengikuti frontend. Jika ada konflik, ikuti spesifikasi ini.

---

## Model Status (WAJIB)

| Tahap | order_status | payment_status | Label UI |
|---|---|---|---|
| QRIS baru dibuat | `awaiting_payment` | `pending_payment` | Menunggu Pembayaran |
| Cash baru dibuat | `waiting_processing` | `pending_payment` | Pesanan Dibuat |
| Sedang dimasak | `processing` | `paid` (QRIS) / `pending_payment` (Cash) | Sedang Diproses |
| Siap disajikan | `ready` | sama | Siap Disajikan |
| Selesai | `completed` | `paid` | Selesai |
| Dibatalkan | `cancelled` | `pending_payment` atau `rejected` | Dibatalkan |

**Alur transisi yang diizinkan:**
```
QRIS: awaiting_payment --verify-payment--> processing (payment_status=paid)
QRIS: awaiting_payment --reject-payment--> cancelled (payment_status=rejected)
QRIS: awaiting_payment --cancel--> cancelled (payment_status=pending_payment)
Cash: waiting_processing --start-processing--> processing
Cash: waiting_processing --cancel--> cancelled
Both: processing --mark-ready--> ready
Both: ready --complete--> completed (Cash: payment_status=paid dalam transaksi)
```

Semua transisi atomik via `UPDATE ... WHERE order_status = <status_asal>` — jika 0 rows updated → 409.
`verify-payment` dan `reject-payment` hanya untuk `payment_method='qris'` — selain itu → 409.
`cancel` hanya dari `awaiting_payment` atau `waiting_processing` — dari `processing`, `ready`, `completed` → 409.

---

## Keputusan yang Dikonfirmasi

| Topik | Keputusan |
|---|---|
| `order_status` / `payment_status` | `text + CHECK`, bukan PostgreSQL ENUM |
| `table_number` | `text`, regex `^\d{1,4}$` di request schema saja (bukan response, data lama berisi '-') |
| `payment_method` | `qris` atau `cash`, wajib |
| Upload bukti bayar | DIHAPUS seluruhnya |
| `reason` reject/cancel | OPSIONAL (`str \| None = None`) |
| Menu publik endpoint | Return SEMUA menu termasuk `is_available=false` |
| `order_items` snapshot | Tambah kolom `menu_type` |
| Backfill lama | `payment_method='qris'`, `table_number='-'`, `order_items.menu_type` dari join menus (fallback 'Makanan') |
| Backfill payment_status | `pending_verification` → `pending_payment` |
| Backfill reject_reason | `UPDATE orders SET cancel_reason = COALESCE(cancel_reason, reject_reason) WHERE reject_reason IS NOT NULL` sebelum drop kolom |
| History summary | Dihitung backend: `total_revenue`, `completed_count`, `cancelled_count` |
| `OrderListItem` | `item_count` saja, tanpa `items[]` |
| Polling buyer track | ~5 detik, stop saat `completed`/`cancelled` atau tab tidak aktif |
| Polling seller orders | ~5-10 detik, stop saat tab tidak aktif |
| Submit checkout | Buka popup dulu; POST saat confirm di popup; disable selama request; Batal tidak clear keranjang/form |
| shadcn | Pertahankan, restyle dengan CSS variable dari prototype |
| Seller layout | Hapus sidebar, pakai `.snav` tab (bottom bar mobile, tab desktop) |
| Role switch | Di seller area saja; tombol masuk mode pembeli redirect ke `/` |
| History | Tanpa tombol hapus riwayat |
| `start-processing` | Tetap nama sama, TANPA batasan payment_method |

---

## Sub-Task 1 — Migration SQL + update schema.sql

**Status:** `[ ] pending`

**Intent:**
Ubah struktur DB agar sesuai model status baru dengan migration yang aman untuk data yang sudah ada.

**Expected Outcomes:**
- `menus` punya `menu_type` dan `category`
- `orders` punya `table_number`, `payment_method`; tidak punya `payment_proof_path`, `reject_reason`
- `order_items` punya `menu_type` snapshot
- CHECK constraints `order_status` dan `payment_status` diupdate (termasuk nilai `ready`)
- RPC `create_order_with_items` diupdate: menerima `table_number`, `payment_method`; menentukan status awal berdasarkan metode; mengisi snapshot `menu_type` per item; menolak `is_available=false`
- `schema.sql` konsisten dengan migration
- File `migration_v2.sql` tersedia untuk dijalankan di Supabase SQL Editor

**Todo List:**
1. Buat file `migration_v2.sql`
2. Bungkus seluruh migration dalam `BEGIN; ... COMMIT;`
3. Tambah kolom baru ke `menus`: `menu_type` (dengan CHECK), `category`
4. Tambah kolom baru ke `orders`: `table_number` (default '-' untuk backfill), `payment_method` (default 'qris' untuk backfill)
5. Tambah kolom baru ke `order_items`: `menu_type` (default 'Makanan' untuk backfill)
6. Backfill `order_items.menu_type` dari join ke `menus` (fallback 'Makanan' jika menu sudah dihapus)
7. Backfill `orders.payment_status`: `pending_verification` → `pending_payment`
8. Preserve `reject_reason` ke `cancel_reason`: `UPDATE orders SET cancel_reason = COALESCE(cancel_reason, reject_reason) WHERE reject_reason IS NOT NULL`
9. Cek nama constraint asli lewat `pg_constraint` dan DROP constraint `order_status` dan `payment_status`
10. ADD constraint baru `order_status` (tambah `ready`), `payment_status` (hapus `pending_verification`)
11. Lepas DEFAULT dari `table_number`, `payment_method`, `order_items.menu_type`
12. DROP kolom `payment_proof_path` dan `reject_reason` dari `orders`
13. Update/replace RPC `create_order_with_items`: terima `table_number`, `payment_method`; status awal QRIS=`awaiting_payment`, Cash=`waiting_processing`; snapshot `menu_type` dari `menus`; tolak `is_available=false`
14. Update `schema.sql` agar konsisten dengan state akhir

**Relevant Context:**
- `schema.sql` untuk referensi struktur awal dan RPC
- Nama constraint yang perlu di-drop: cek dengan `SELECT conname FROM pg_constraint WHERE conrelid = 'orders'::regclass AND contype = 'c'`
- RPC `create_order_with_items` ada di `schema.sql` SECTION 4
- Catatan: DROP DEFAULT setelah backfill agar insert baru yang lupa field gagal eksplisit

---

## Sub-Task 2 — Backend Schemas

**Status:** `[ ] pending`

**Intent:**
Sinkronkan semua Pydantic models dengan model data baru.

**Expected Outcomes:**
- `MenuCreate`, `MenuUpdate`, `MenuResponse` punya `menu_type`, `category`, `is_available`
- `OrderCreateRequest` punya `table_number` (regex `^\d{1,4}$`, wajib) dan `payment_method` (`qris|cash`, wajib)
- `OrderTrackResponse` punya `table_number`, `payment_method` (response — tanpa validasi regex)
- `OrderDetailResponse.items[]` punya `menu_type`, `name` (alias dari `menu_name`), `qty` (alias dari `quantity`), `subtotal`
- `OrderListItem` punya `table_number`, `payment_method`, `item_count`
- `HistoryItem` punya `table_number`, `payment_method`; tidak punya `reject_reason`
- `HistoryResponse` punya `total_revenue`, `completed_count`, `cancelled_count` sebagai field summary
- `OrderDetailResponse` tidak punya `payment_proof_url`, tidak punya `reject_reason`
- `CancelRequest.reason` dan `RejectRequest.reason` adalah `str | None = None`
- `PaymentRejectRequest` dihapus, diganti `RejectRequest` dengan `reason` opsional
- `ProofUploadResponse` dihapus

**Todo List:**
1. Update `schemas/menu.py`: tambah `menu_type`, `category` ke `MenuCreate`, `MenuUpdate`, `MenuResponse`
2. Update `schemas/order.py`: tambah `table_number`, `payment_method` ke `OrderCreateRequest`; tambah ke `OrderTrackResponse`; hapus `ProofUploadResponse`; tambah `payment_method` validator (`qris|cash`)
3. Update `schemas/seller_order.py`: update `OrderListItem`, `OrderDetailResponse`, `HistoryItem`; hapus `payment_proof_url`, `reject_reason`; ganti `PaymentRejectRequest` dengan `RejectRequest`; `reason` opsional; tambah summary fields ke `HistoryResponse`; `OrderItemDetail` punya `menu_type`, `name`, `qty`, `subtotal`

**Relevant Context:**
- `schemas/order.py`, `schemas/menu.py`, `schemas/seller_order.py`
- Validasi regex `table_number` HANYA di `OrderCreateRequest`, tidak di response schema

---

## Sub-Task 3 — Backend Services

**Status:** `[ ] pending`

**Intent:**
Implementasikan logika transisi status baru, hapus semua logika proof upload, update semua return values.

**Expected Outcomes:**
- `order_service.create_order()` meneruskan `table_number`, `payment_method` ke RPC
- `order_service.upload_proof()` dan semua konstanta terkait dihapus
- `order_service.track_order()` mengembalikan `table_number`, `payment_method`
- `menu_service.get_active_menus()` return SEMUA menu (hapus filter `is_available=True`)
- `seller_order_service._assert_transition()` mengimplementasikan aturan transisi baru
- `seller_order_service.verify_payment()`: cek `payment_method='qris'` + `awaiting_payment` → `processing`, `paid`
- `seller_order_service.reject_payment()`: cek `payment_method='qris'` + `awaiting_payment` → `cancelled`, `rejected`
- `seller_order_service.start_processing()`: `waiting_processing` → `processing` (tanpa cek payment_method)
- `seller_order_service.mark_ready()`: `processing` → `ready` (fungsi baru)
- `seller_order_service.complete_order()`: `ready` → `completed`; jika Cash set `paid`
- `seller_order_service.cancel_order()`: hanya dari `awaiting_payment` atau `waiting_processing`
- Semua fungsi yang list/detail return `table_number`, `payment_method`
- `get_order_detail()` hapus logika signed URL, hapus `payment_proof_url`, `reject_reason`
- `get_history()` return summary `total_revenue`, `completed_count`, `cancelled_count`

**Todo List:**
1. Update `services/order_service.py`:
   - Hapus `upload_proof()`, `_ALLOWED_CONTENT_TYPES`, `_MAX_FILE_SIZE`, `_MAGIC_BYTES`, `_check_magic()`, `_CONTENT_TYPE_TO_EXT`
   - Update `create_order()`: pass `table_number`, `payment_method` ke RPC
   - Update `track_order()`: return `table_number`, `payment_method`
2. Update `services/menu_service.py`:
   - `get_active_menus()`: hapus filter `is_available=True` (return semua aktif)
   - `get_all_menus_for_seller()`: sudah return semua, tidak perlu ubah
3. Rewrite `services/seller_order_service.py`:
   - Update `_assert_transition()` dengan aturan baru
   - Update `verify_payment()`, `reject_payment()`, `start_processing()`, `complete_order()`, `cancel_order()`
   - Tambah `mark_ready()`
   - Hapus signed URL logic dari `get_order_detail()`
   - Update `list_active_orders()`, `get_order_detail()`, `get_history()` dengan field baru

**Relevant Context:**
- `services/order_service.py`, `services/menu_service.py`, `services/seller_order_service.py`
- Pattern atomik: `UPDATE ... WHERE order_status = <status_asal>` dan cek apakah update berhasil (0 rows = 409)
- `_ACTIVE_STATUSES` perlu tambah `ready` sebagai status aktif

---

## Sub-Task 4 — Backend Routers

**Status:** `[ ] pending`

**Intent:**
Hapus endpoint proof upload, tambah `mark-ready`, update body reject/cancel.

**Expected Outcomes:**
- `POST /orders/{order_number}/proof` dihapus
- Import `File`, `UploadFile` yang tidak terpakai dihapus dari `routers/order.py`
- `POST /seller/orders/{order_number}/mark-ready` ditambah
- Body reject dan cancel menggunakan schema baru dengan `reason` opsional
- Semua endpoint seller tetap diproteksi `require_seller`

**Todo List:**
1. Update `routers/order.py`: hapus endpoint proof, hapus import tidak terpakai
2. Update `routers/seller.py`: tambah `mark-ready` endpoint; update import untuk `RejectRequest`; pastikan body reject/cancel pakai schema dengan `reason` opsional

**Relevant Context:**
- `routers/order.py`, `routers/seller.py`
- Import `mark_ready` dari `services/seller_order_service`

**⚠️ LAPORAN SETELAH SUB-TASK INI SEBELUM LANJUT KE FRONTEND**

---

## Sub-Task 5 — Frontend Types & Utils

**Status:** `[ ] pending`

**Intent:**
Sinkronkan TypeScript types, API client, dan format utilities dengan model baru.

**Expected Outcomes:**
- `types/api.ts`: semua interface diupdate dengan field baru; `ProofUploadResponse` dihapus
- `lib/api.ts`: `uploadProof()` dihapus; `markReady()` ditambah; `reason` opsional di reject/cancel
- `utils/format.ts`: hapus `pending_verification`; tambah `ready` dengan label "Siap Disajikan" dan warna

**Todo List:**
1. Update `frontend/src/types/api.ts`
2. Update `frontend/src/lib/api.ts`
3. Update `frontend/src/utils/format.ts`

---

## Sub-Task 6 — Hapus ProofUpload + Update Router

**Status:** `[ ] pending`

**Intent:**
Bersihkan semua referensi proof upload dari frontend.

**Todo List:**
1. Hapus `frontend/src/pages/buyer/ProofUploadPage.vue`
2. Update `frontend/src/router/index.ts`: hapus route `/order/:orderNumber/proof`

---

## Sub-Task 7 — Frontend Buyer Pages (logika + desain)

**Status:** `[ ] pending`

**Intent:**
Update halaman buyer agar sesuai alur dan desain baru.

**Expected Outcomes:**
- `MenuListPage`: filter jenis + kategori dinamis; kartu bergaya prototype (PESAN/stepper/HABIS)
- `CheckoutPage`: form `table_number` + `payment_method` (card QRIS/Cash); Submit buka popup modal; POST di confirm; disable selama request; Batal tidak clear form/keranjang; setelah order dibuat tampil token + link track
- `TrackOrderPage`: polling 5 detik (stop saat terminal/tab tidak aktif); hapus upload proof section; tampil meja, metode, catatan
- Popup QRIS: QR contoh berlabel prototype, nominal, merchant, langkah scan, "Saya Sudah Bayar" / "Batal"
- Popup Cash: ringkasan meja, daftar item, total, keterangan kasir, "Konfirmasi Pesanan" / "Kembali"

**Relevant Context:**
- `tampilan_pembelian_3.html` sebagai referensi desain dan alur popup
- QR diberi label "Prototype: QR ini hanya contoh dan bukan kode pembayaran sungguhan"

---

## Sub-Task 8 — Frontend Seller Pages (logika + desain)

**Status:** `[ ] pending`

**Intent:**
Update halaman seller: tombol aksi sesuai status baru, desain kartu grid, polling, role switch.

**Expected Outcomes:**
- `SellerOrdersPage`: grid kartu (1/2/3 kolom); info meja+nama+waktu+ID+lencana+ringkasan+tombol per status; polling 5-10 dtk; tombol per status: awaiting_payment→Konfirmasi Bayar+Tolak, waiting_processing→Proses Pesanan+Batalkan, processing→Buka Pesanan+Siap Disajikan, ready→Buka Pesanan+Selesai(atau "Terima Tunai & Selesai" jika cash belum lunas)
- `SellerHistoryPage`: 3 kartu summary (total_revenue, completed_count, cancelled_count dari backend) + daftar kartu riwayat; tanpa tombol hapus
- `SellerMenuPage`: grid kartu menu; dropdown jenis+kategori dinamis; saklar Tersedia/Habis; Edit; Hapus dua langkah; form modal dengan chip jenis + saran kategori
- `OrderDetailModal`: dibangun ulang sesuai desain prototype — header Nama+Meja, group MAKANAN/MINUMAN (tersembunyi jika kosong), label QTY/HARGA hanya di group pertama, bar cokelat nama, kotak qty, total diapit dua garis, tombol TUTUP pil cokelat tua di tengah; bottom sheet di mobile
- `ReasonDialog`: reason opsional (hapus validasi wajib)
- `SellerLayout`: hapus sidebar; `.snav` tab (bottom bar mobile, tab garis bawah desktop); lencana jumlah aktif di Pemesanan
- Role switch di seller: tombol "Pembeli | Penjual"; klik Pembeli → redirect `/`

**Relevant Context:**
- `tampilan_pembelian_3.html` — komponen `SellerOrders`, `SellerHistory`, `MenuEditor`, `OrderDetailModal`, `SellerApp`, `.snav`
- Label tombol: `awaiting_payment` → Konfirmasi Bayar + Tolak; `waiting_processing` → Proses Pesanan + Batalkan; `processing` → Buka Pesanan + Siap Disajikan; `ready` → Buka Pesanan + Selesai/"Terima Tunai & Selesai"

---

## Sub-Task 9 — Frontend Desain (CSS + Layout global)

**Status:** `[ ] pending`

**Intent:**
Pindahkan CSS variable dan tema dari prototype ke `frontend/`, muat font Inter.

**Expected Outcomes:**
- CSS variable (`--bg`, `--ink`, `--brand`, `--brand-dark`, `--line`, `--field`, `--muted`, `--on-brand`) dan dark mode ada di `style.css`
- Font Inter dimuat di `frontend/index.html`
- shadcn components menggunakan CSS variable (tidak ada warna hardcode yang bertabrakan)
- `NavBar.vue` restyle dengan tema warung
- `frontend/index.html` title diupdate ke "Warung Wak Haji"
- Tidak ada horizontal scroll di 360px, 768px, 1280px

**Todo List:**
1. Update `frontend/src/style.css`: tambah `:root` CSS variable + dark mode variants
2. Update `frontend/index.html`: tambah Google Fonts Inter; ubah title
3. Update `frontend/src/components/NavBar.vue`: restyle dengan tema

**Relevant Context:**
- CSS variable dari `tampilan_pembelian_3.html` baris 10-18
- Dark mode: `@media (prefers-color-scheme:dark)` + `[data-theme="dark"]`

---

## Sub-Task 10 — Tests & Verifikasi

**Status:** `[ ] pending`

**Intent:**
Pastikan semua logika baru tercover test dan 5 skenario uji manual dari kriteria selesai lulus.

**Expected Outcomes:**
- Pytest tests untuk:
  - Status awal QRIS: `awaiting_payment` / `pending_payment`
  - Status awal Cash: `waiting_processing` / `pending_payment`
  - Setiap transisi valid (verify, reject, start-processing, mark-ready, complete, cancel)
  - Setiap transisi invalid → 409
  - Cancel saat `processing` → 409
  - `verify-payment` untuk Cash → 409
  - `reject-payment` untuk Cash → 409
  - Order dengan `is_available=false` → 4xx
  - Total dihitung server (bukan dari client)
  - Migration pada data lama (backfill)
- 5 skenario uji manual lulus:
  1. QRIS: pesan → konfirmasi → status berubah tanpa refresh
  2. Cash: pesan → proses → siap → selesai → masuk history lunas
  3. Cancel saat processing: ditolak 409, tombol tidak muncul di UI
  4. Menu habis: tombol HABIS di UI, POST order ditolak server
  5. Menu dihapus: tetap tampil benar di popup detail pesanan lama
- Lint dan type-check lulus
- Tidak ada referensi tersisa ke `payment_proof`, `reject_reason`, `pending_verification`, `uploadProof`, `ProofUploadPage`

**Todo List:**
1. Tulis/update `tests/test_orders.py`: QRIS vs Cash status awal, semua transisi
2. Tulis/update `tests/test_seller.py`: verify/reject/process/ready/complete/cancel + invalid cases
3. Tulis/update `tests/test_menu.py`: is_available filter, create order dengan menu habis
4. Jalankan `pytest tests/ -v`
5. Jalankan lint dan type-check frontend (`cd frontend && npx tsc --noEmit`)
6. Grep untuk referensi lama yang harus sudah dihapus
7. Jalankan 5 skenario manual

---

## Urutan Eksekusi

```
1 (SQL) → 2 (schemas) → 3 (services) → 4 (routers)
⬇ LAPORAN — tunggu konfirmasi sebelum lanjut
5 (FE types) → 6 (hapus proof) → 7 (buyer pages) → 8 (seller pages) → 9 (desain) → 10 (tests)
```
