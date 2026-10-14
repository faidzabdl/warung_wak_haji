-- =============================================================================
-- Migration v2 — Warung Wak Haji
-- =============================================================================
-- Jalankan di Supabase SQL Editor.
-- Aman untuk database yang sudah berisi data (backfill sebelum constraint baru,
-- kolom lama dihapus setelah data dipindahkan).
-- Idempoten: dapat dijalankan ulang tanpa error.
-- Semua perubahan dalam satu transaksi.
--
-- PENTING — Setelah COMMIT, jalankan bagian STORAGE CLEANUP secara manual
-- (tidak masuk transaksi karena memerlukan izin superuser/service role):
--   - Hapus policy storage lewat Dashboard → Storage → Policies, ATAU
--     jalankan blok DO $$ ... $$ di bagian STORAGE CLEANUP di bawah.
--   - Kosongkan dan hapus bucket 'payment-proofs' lewat Supabase Dashboard.
--     JANGAN hapus baris storage.objects lewat SQL (bisa rusak metadata bucket).
-- =============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Tambah kolom baru ke menus (IF NOT EXISTS → idempoten)
-- ============================================================================

ALTER TABLE menus
    ADD COLUMN IF NOT EXISTS menu_type text NOT NULL DEFAULT 'Makanan',
    ADD COLUMN IF NOT EXISTS category  text NOT NULL DEFAULT 'Umum';

-- Tambah CHECK constraint untuk menu_type hanya jika belum ada
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE  conrelid = 'menus'::regclass
          AND  contype  = 'c'
          AND  pg_get_constraintdef(oid) LIKE '%menu_type%'
    ) THEN
        ALTER TABLE menus
            ADD CONSTRAINT menus_menu_type_check
                CHECK (menu_type IN ('Makanan', 'Minuman'));
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Tambah kolom baru ke orders (default untuk backfill data lama)
-- ============================================================================

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS table_number   text NOT NULL DEFAULT '-',
    ADD COLUMN IF NOT EXISTS payment_method text NOT NULL DEFAULT 'qris';

-- ============================================================================
-- STEP 3: Tambah kolom menu_type ke order_items (default untuk backfill)
-- ============================================================================

ALTER TABLE order_items
    ADD COLUMN IF NOT EXISTS menu_type text NOT NULL DEFAULT 'Makanan';

-- ============================================================================
-- STEP 4: Backfill order_items.menu_type dari menus via JOIN
-- Jika menu sudah dihapus (menu_id NULL atau tidak ada di menus), pakai 'Makanan'.
-- ============================================================================

UPDATE order_items oi
SET    menu_type = COALESCE(
           (SELECT m.menu_type FROM menus m WHERE m.id = oi.menu_id),
           'Makanan'
       );

-- ============================================================================
-- STEP 5: Backfill payment_status — petakan pending_verification → pending_payment
-- ============================================================================

UPDATE orders
SET    payment_status = 'pending_payment'
WHERE  payment_status = 'pending_verification';

-- ============================================================================
-- STEP 6: Preserve reject_reason ke cancel_reason sebelum kolom dihapus
-- ============================================================================

UPDATE orders
SET    cancel_reason = COALESCE(cancel_reason, reject_reason)
WHERE  reject_reason IS NOT NULL;

-- ============================================================================
-- STEP 7: Drop semua check constraint orders yang menyebut order_status,
-- payment_status, atau payment_method — via pg_constraint (idempoten, FOR loop)
-- ============================================================================

DO $$
DECLARE
    v_name text;
BEGIN
    FOR v_name IN
        SELECT conname
        FROM   pg_constraint
        WHERE  conrelid = 'orders'::regclass
          AND  contype  = 'c'
          AND  (
              pg_get_constraintdef(oid) LIKE '%order_status%'
           OR pg_get_constraintdef(oid) LIKE '%payment_status%'
           OR pg_get_constraintdef(oid) LIKE '%payment_method%'
          )
    LOOP
        EXECUTE format('ALTER TABLE orders DROP CONSTRAINT IF EXISTS %I', v_name);
    END LOOP;
END $$;

-- ============================================================================
-- STEP 8: Tambah constraint baru — idempoten (cek pg_constraint dulu)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'orders'::regclass AND conname = 'orders_order_status_check'
    ) THEN
        ALTER TABLE orders ADD CONSTRAINT orders_order_status_check
            CHECK (order_status IN (
                'awaiting_payment', 'waiting_processing', 'processing',
                'ready', 'completed', 'cancelled'
            ));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'orders'::regclass AND conname = 'orders_payment_status_check'
    ) THEN
        ALTER TABLE orders ADD CONSTRAINT orders_payment_status_check
            CHECK (payment_status IN ('pending_payment', 'paid', 'rejected'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'orders'::regclass AND conname = 'orders_payment_method_check'
    ) THEN
        ALTER TABLE orders ADD CONSTRAINT orders_payment_method_check
            CHECK (payment_method IN ('qris', 'cash'));
    END IF;
END $$;

-- ============================================================================
-- STEP 9: Drop kolom lama setelah data sudah diamankan
-- ============================================================================

ALTER TABLE orders
    DROP COLUMN IF EXISTS payment_proof_path,
    DROP COLUMN IF EXISTS reject_reason;

-- ============================================================================
-- STEP 10: Lepas DEFAULT setelah backfill agar insert yang lupa field gagal
-- ============================================================================

ALTER TABLE orders
    ALTER COLUMN table_number   DROP DEFAULT,
    ALTER COLUMN payment_method DROP DEFAULT;

ALTER TABLE order_items
    ALTER COLUMN menu_type DROP DEFAULT;

-- ============================================================================
-- STEP 11: Drop SEMUA overload lama create_order_with_items secara dinamis
-- ============================================================================

DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT p.oid::regprocedure AS sig
        FROM   pg_proc p
        JOIN   pg_namespace n ON n.oid = p.pronamespace
        WHERE  n.nspname = 'public'
          AND  p.proname = 'create_order_with_items'
    LOOP
        EXECUTE 'DROP FUNCTION ' || r.sig;
    END LOOP;
END $$;

-- ============================================================================
-- STEP 12: Buat RPC create_order_with_items v2
-- - Menerima table_number dan payment_method
-- - Status awal: qris → awaiting_payment/pending_payment,
--                cash → waiting_processing/pending_payment
-- - Validasi menu (is_active, is_available)
-- - Snapshot menu_type per item
-- - Total dihitung dari DB (harga client diabaikan)
-- ============================================================================

CREATE FUNCTION create_order_with_items(
    order_data  jsonb,
    items_data  jsonb[]
)
RETURNS orders
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_order          orders;
    v_item           jsonb;
    v_total          numeric(12,2) := 0;
    v_subtotal       numeric(12,2);
    v_menu           menus%ROWTYPE;
    v_payment_method text;
    v_order_status   text;
    v_payment_status text;
BEGIN
    v_payment_method := order_data->>'payment_method';

    IF v_payment_method = 'qris' THEN
        v_order_status   := 'awaiting_payment';
        v_payment_status := 'pending_payment';
    ELSIF v_payment_method = 'cash' THEN
        v_order_status   := 'waiting_processing';
        v_payment_status := 'pending_payment';
    ELSE
        RAISE EXCEPTION 'Invalid payment_method: %', v_payment_method;
    END IF;

    INSERT INTO orders (
        order_number, idempotency_key, buyer_name,
        table_number, payment_method, notes,
        payment_status, order_status, tracking_token_hash
    )
    VALUES (
        order_data->>'order_number',
        NULLIF(order_data->>'idempotency_key', ''),
        order_data->>'buyer_name',
        order_data->>'table_number',
        v_payment_method,
        NULLIF(order_data->>'notes', ''),
        v_payment_status,
        v_order_status,
        order_data->>'tracking_token_hash'
    )
    RETURNING * INTO v_order;

    FOREACH v_item IN ARRAY items_data LOOP
        SELECT * INTO v_menu FROM menus WHERE id = (v_item->>'menu_id')::uuid;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Menu not found: %', v_item->>'menu_id';
        END IF;
        IF v_menu.is_active = false THEN
            RAISE EXCEPTION 'Menu not active: %', v_menu.name;
        END IF;
        IF v_menu.is_available = false THEN
            RAISE EXCEPTION 'Menu not available: %', v_menu.name;
        END IF;

        v_subtotal := v_menu.price * (v_item->>'quantity')::integer;
        v_total    := v_total + v_subtotal;

        INSERT INTO order_items (
            order_id, menu_id, menu_name_snapshot,
            menu_price_snapshot, menu_type, quantity, subtotal
        )
        VALUES (
            v_order.id, v_menu.id, v_menu.name,
            v_menu.price, v_menu.menu_type,
            (v_item->>'quantity')::integer, v_subtotal
        );
    END LOOP;

    UPDATE orders SET total_amount = v_total
    WHERE id = v_order.id RETURNING * INTO v_order;

    RETURN v_order;

EXCEPTION
    WHEN OTHERS THEN RAISE;
END;
$$;

COMMENT ON FUNCTION create_order_with_items(jsonb, jsonb[]) IS
    'v2: Atomic order + items insert. Status from payment_method. '
    'Validates menu availability. Snapshots menu_type. Total from DB prices. '
    'SECURITY DEFINER.';

COMMIT;

-- =============================================================================
-- STORAGE CLEANUP — jalankan TERPISAH (di luar transaksi, perlu service role)
-- =============================================================================
-- Hapus policy yang terkait bucket payment-proofs secara dinamis.
-- Jika error izin, hapus manual lewat Dashboard → Storage → Policies.
--
-- DO $$
-- DECLARE r record;
-- BEGIN
--   FOR r IN
--     SELECT policyname FROM pg_policies
--     WHERE  schemaname = 'storage' AND tablename = 'objects'
--       AND  (
--           coalesce(qual,       '') ILIKE '%payment-proofs%'
--        OR coalesce(with_check, '') ILIKE '%payment-proofs%'
--       )
--   LOOP
--     EXECUTE format('DROP POLICY %I ON storage.objects', r.policyname);
--   END LOOP;
-- END $$;
--
-- Setelah policy dihapus:
--   1. Buka Supabase Dashboard → Storage → payment-proofs
--   2. Hapus semua file di dalam bucket (Select All → Delete)
--   3. Klik "Delete Bucket"
-- JANGAN gunakan DELETE FROM storage.objects lewat SQL.
-- =============================================================================
