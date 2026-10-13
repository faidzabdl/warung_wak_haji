-- =============================================================================
-- UMKM Ordering API — Database Schema
-- =============================================================================
--
-- HOW TO RUN:
--   1. Open your Supabase project → SQL Editor.
--   2. Search for the text "TODO: replace with actual seller UID" and substitute
--      the placeholder UUID ('00000000-0000-0000-0000-000000000000') with the
--      real Supabase Auth UID of the seller account before running.
--      You can find the UID in Supabase Dashboard → Authentication → Users.
--   3. Paste the entire file contents into the SQL Editor and click Run.
--   4. After running, follow the STORAGE SETUP section below to create the two
--      Storage buckets manually in the Supabase Dashboard.
--
-- SELLER UID NOTE:
--   This schema is for a single-seller system. Every RLS policy that restricts
--   access to the seller uses:
--       auth.uid()::text = current_setting('app.seller_uid', true)
--   There are two ways to set app.seller_uid at runtime:
--     Option A (Supabase custom config, recommended for production):
--       Set the Postgres parameter in your Supabase project config, or inject it
--       per-request from the backend via:  SET LOCAL app.seller_uid = '<uid>';
--     Option B (hardcoded UID in policy, simpler for single-tenant deploy):
--       Replace current_setting('app.seller_uid', true) with a UUID literal
--       directly in each policy, e.g.:
--           auth.uid() = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'::uuid
--   The policies below use Option A (current_setting). If you prefer Option B,
--   do a find-and-replace on the placeholder UUID after substitution.
--
-- STATUS TRANSITIONS (enforced in service layer, documented here for reference):
--   order_status:
--     awaiting_payment  → waiting_processing (payment confirmed)
--     awaiting_payment  → cancelled
--     waiting_processing → processing
--     waiting_processing → cancelled
--     processing        → completed
--     processing        → cancelled
--   payment_status:
--     pending_payment   → pending_verification (proof uploaded)
--     pending_verification → paid
--     pending_verification → rejected
-- =============================================================================


-- =============================================================================
-- SECTION 1: TABLES
-- =============================================================================

-- ---------------------------------------------------------------------------
-- menus
-- ---------------------------------------------------------------------------
CREATE TABLE menus (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text        NOT NULL CHECK (char_length(trim(name)) > 0),
    description  text,
    price        numeric(12,2) NOT NULL CHECK (price > 0),
    image_url    text,
    is_available boolean     NOT NULL DEFAULT true,
    is_active    boolean     NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  menus              IS 'Seller menu items. Public reads filtered to is_active AND is_available.';
COMMENT ON COLUMN menus.is_available IS 'Seller can quickly mark an item as temporarily unavailable (e.g. sold out today) without deactivating it.';
COMMENT ON COLUMN menus.is_active    IS 'Soft-delete flag. Inactive menus are hidden from all public endpoints.';

-- ---------------------------------------------------------------------------
-- orders
-- ---------------------------------------------------------------------------
CREATE TABLE orders (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number        text          NOT NULL UNIQUE,   -- format: ORD-YYYYMMDD-XXXX
    idempotency_key     text          UNIQUE,            -- nullable; client-supplied header for deduplication
    buyer_name          text          NOT NULL CHECK (char_length(trim(buyer_name)) > 0),
    notes               text,
    payment_status      text          NOT NULL DEFAULT 'pending_payment'
                            CHECK (payment_status IN (
                                'pending_payment',
                                'pending_verification',
                                'paid',
                                'rejected'
                            )),
    order_status        text          NOT NULL DEFAULT 'awaiting_payment'
                            CHECK (order_status IN (
                                'awaiting_payment',
                                'waiting_processing',
                                'processing',
                                'completed',
                                'cancelled'
                            )),
    tracking_token_hash text          NOT NULL UNIQUE,   -- SHA-256 hex of the plain token returned once to buyer
    total_amount        numeric(12,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    payment_proof_path  text,                            -- Storage path, e.g. payment-proofs/{order_id}/{uuid}.ext
    cancel_reason       text,
    reject_reason       text,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    updated_at          timestamptz   NOT NULL DEFAULT now()
);

COMMENT ON TABLE  orders                     IS 'Buyer orders. All buyer writes go through the FastAPI service-role client; no direct public inserts.';
COMMENT ON COLUMN orders.order_number        IS 'Human-readable unique identifier in format ORD-YYYYMMDD-XXXX.';
COMMENT ON COLUMN orders.idempotency_key     IS 'Optional client-supplied key. If present and already exists, backend returns the existing order (HTTP 200) instead of creating a duplicate.';
COMMENT ON COLUMN orders.tracking_token_hash IS 'SHA-256(token_urlsafe(32)). Plain token is shown to buyer once and never stored.';
COMMENT ON COLUMN orders.total_amount        IS 'Sum of order_items.subtotal. Set by create_order_with_items RPC after items are inserted.';

-- ---------------------------------------------------------------------------
-- order_items
-- ---------------------------------------------------------------------------
CREATE TABLE order_items (
    id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id             uuid          NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_id              uuid          REFERENCES menus(id) ON DELETE SET NULL,  -- nullable: menu may be deleted later
    menu_name_snapshot   text          NOT NULL,
    menu_price_snapshot  numeric(12,2) NOT NULL CHECK (menu_price_snapshot > 0),
    quantity             integer       NOT NULL CHECK (quantity > 0),
    subtotal             numeric(12,2) NOT NULL CHECK (subtotal > 0),  -- stored; Python computes price_snapshot * quantity
    created_at           timestamptz   NOT NULL DEFAULT now()
);

COMMENT ON TABLE  order_items                    IS 'Immutable snapshot of each line item at the time of order creation.';
COMMENT ON COLUMN order_items.menu_id            IS 'Nullable FK — set to NULL if the source menu row is deleted. Snapshot fields preserve the original values.';
COMMENT ON COLUMN order_items.menu_name_snapshot IS 'Name of the menu item at time of order; immutable even if menu is later renamed.';
COMMENT ON COLUMN order_items.menu_price_snapshot IS 'Price at time of order; immutable even if menu price changes later.';
COMMENT ON COLUMN order_items.subtotal           IS 'Stored (not computed column). Python calculates menu_price_snapshot * quantity before insert.';

-- ---------------------------------------------------------------------------
-- audit_logs
-- ---------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id   uuid        REFERENCES orders(id) ON DELETE SET NULL,
    action     text        NOT NULL,   -- e.g. 'payment_verified', 'payment_rejected', 'order_cancelled', 'order_completed', 'processing_started'
    actor      text        NOT NULL,   -- seller uid or 'system'
    metadata   jsonb,                  -- optional context, e.g. {reason, previous_status}
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  audit_logs          IS 'Immutable append-only log of seller actions on orders. Inserted only via service-role client; no UPDATE or DELETE via RLS.';
COMMENT ON COLUMN audit_logs.action   IS 'Action identifier: payment_verified | payment_rejected | order_cancelled | order_completed | processing_started';
COMMENT ON COLUMN audit_logs.actor    IS 'UID of the seller who performed the action, or the string ''system'' for automated actions.';
COMMENT ON COLUMN audit_logs.metadata IS 'Optional JSON context, e.g. {"reason": "...", "previous_status": "waiting_processing"}.';


-- =============================================================================
-- SECTION 2: INDEXES
-- =============================================================================

CREATE INDEX ON orders (order_status);
CREATE INDEX ON orders (payment_status);
CREATE INDEX ON orders (created_at DESC);
CREATE UNIQUE INDEX ON orders (tracking_token_hash);   -- belt-and-suspenders alongside UNIQUE column constraint
CREATE UNIQUE INDEX ON orders (order_number);          -- belt-and-suspenders
CREATE INDEX ON orders (idempotency_key) WHERE idempotency_key IS NOT NULL;  -- partial index; skips NULL rows
CREATE INDEX ON order_items (order_id);
CREATE INDEX ON audit_logs (order_id);


-- =============================================================================
-- SECTION 3: UPDATED_AT TRIGGER
-- =============================================================================

-- Generic trigger function — fires BEFORE UPDATE on any table that has updated_at.
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_menus_updated_at
    BEFORE UPDATE ON menus
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- =============================================================================
-- SECTION 4: RPC FUNCTION — ATOMIC ORDER CREATION
-- =============================================================================
--
-- Used by the FastAPI service layer (via service-role client) to insert an order
-- and all its items in a single transaction. Calculates total_amount from the
-- inserted items so the Python layer never has to do a separate UPDATE.
--
-- Parameters:
--   order_data  jsonb   — fields for the orders row (see keys below)
--   items_data  jsonb[] — array of order_items rows (one element per line item)
--
-- order_data keys:
--   order_number, idempotency_key (optional/null), buyer_name, notes (optional),
--   payment_status, order_status, tracking_token_hash
--
-- items_data element keys:
--   menu_id (optional/null), menu_name_snapshot, menu_price_snapshot,
--   quantity, subtotal
--
-- Returns: the fully populated orders row after total_amount is set.

CREATE OR REPLACE FUNCTION create_order_with_items(
    order_data  jsonb,
    items_data  jsonb[]
)
RETURNS orders
LANGUAGE plpgsql
SECURITY DEFINER   -- runs as the function owner (postgres); called by service-role client
AS $$
DECLARE
    v_order        orders;
    v_item         jsonb;
    v_total        numeric(12,2) := 0;
BEGIN
    -- 1. Insert the order row.
    INSERT INTO orders (
        order_number,
        idempotency_key,
        buyer_name,
        notes,
        payment_status,
        order_status,
        tracking_token_hash
    )
    VALUES (
        order_data->>'order_number',
        NULLIF(order_data->>'idempotency_key', ''),   -- store NULL if empty string or key absent
        order_data->>'buyer_name',
        NULLIF(order_data->>'notes', ''),
        COALESCE(order_data->>'payment_status', 'pending_payment'),
        COALESCE(order_data->>'order_status',   'awaiting_payment'),
        order_data->>'tracking_token_hash'
    )
    RETURNING * INTO v_order;

    -- 2. Insert all order_items rows.
    FOREACH v_item IN ARRAY items_data LOOP
        INSERT INTO order_items (
            order_id,
            menu_id,
            menu_name_snapshot,
            menu_price_snapshot,
            quantity,
            subtotal
        )
        VALUES (
            v_order.id,
            NULLIF(v_item->>'menu_id', '')::uuid,
            v_item->>'menu_name_snapshot',
            (v_item->>'menu_price_snapshot')::numeric(12,2),
            (v_item->>'quantity')::integer,
            (v_item->>'subtotal')::numeric(12,2)
        );

        v_total := v_total + (v_item->>'subtotal')::numeric(12,2);
    END LOOP;

    -- 3. Update total_amount on the order row.
    UPDATE orders
       SET total_amount = v_total
     WHERE id = v_order.id
    RETURNING * INTO v_order;

    RETURN v_order;

EXCEPTION
    WHEN OTHERS THEN
        -- Any error causes the whole transaction to roll back automatically
        -- in plpgsql; re-raise so the caller gets the original error detail.
        RAISE;
END;
$$;

COMMENT ON FUNCTION create_order_with_items(jsonb, jsonb[]) IS
    'Atomically inserts an orders row + all order_items rows and sets total_amount. '
    'Called by FastAPI backend via service-role client. SECURITY DEFINER runs as postgres.';


-- =============================================================================
-- SECTION 5: ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE menus       ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders      ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs  ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- SELLER UID PLACEHOLDER
-- TODO: replace '00000000-0000-0000-0000-000000000000' with the actual seller
--       Supabase Auth UID before running this script.
-- ---------------------------------------------------------------------------

-- ---- menus ----------------------------------------------------------------

-- Public SELECT: only active and available items visible to anonymous users.
CREATE POLICY "Public can view active menus"
    ON menus FOR SELECT
    TO anon
    USING (is_active = true AND is_available = true);

-- Seller SELECT: full table access, including inactive/unavailable items.
CREATE POLICY "Seller can view all menus"
    ON menus FOR SELECT
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

-- Seller INSERT.
CREATE POLICY "Seller can insert menus"
    ON menus FOR INSERT
    TO authenticated
    WITH CHECK (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

-- Seller UPDATE.
CREATE POLICY "Seller can update menus"
    ON menus FOR UPDATE
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    )
    WITH CHECK (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

-- Seller DELETE.
CREATE POLICY "Seller can delete menus"
    ON menus FOR DELETE
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

-- ---- orders ---------------------------------------------------------------
-- No public access. All buyer writes go via service-role (bypasses RLS).
-- Seller can SELECT and UPDATE; INSERT/DELETE remain service-role only.

CREATE POLICY "Seller can view all orders"
    ON orders FOR SELECT
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

CREATE POLICY "Seller can update orders"
    ON orders FOR UPDATE
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    )
    WITH CHECK (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

-- ---- order_items ----------------------------------------------------------

CREATE POLICY "Seller can view order items"
    ON order_items FOR SELECT
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

CREATE POLICY "Seller can update order items"
    ON order_items FOR UPDATE
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    )
    WITH CHECK (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );

-- ---- audit_logs -----------------------------------------------------------
-- No public access. Service-role client bypasses RLS for INSERT.
-- Seller can only SELECT (read audit trail).

CREATE POLICY "Seller can view audit logs"
    ON audit_logs FOR SELECT
    TO authenticated
    USING (
        auth.uid()::text = current_setting('app.seller_uid', true)
    );


-- =============================================================================
-- SECTION 6: STORAGE SETUP
-- =============================================================================
--
-- SQL cannot create Storage buckets. Follow the manual steps below in the
-- Supabase Dashboard (Storage tab) before the backend goes live.
--
-- 1. Bucket: payment-proofs
--    - Visibility: PRIVATE (public read disabled)
--    - Purpose: buyer payment proof images uploaded by FastAPI backend via
--      service-role client; seller reads via signed URLs (1-hour expiry).
--    - Backend upload path: payment-proofs/{order_id}/{uuid4}.{ext}
--    - After creating the bucket, run the Storage policy below.
--
-- 2. Bucket: menu-images
--    - Visibility: PUBLIC (public read enabled)
--    - Purpose: menu item images uploaded by seller via FastAPI backend.
--    - Backend upload path: menu-images/{uuid4}.{ext}
--    - No extra read policy needed (bucket is public).
--    - Write (INSERT) is handled by the service-role client in the backend;
--      no Storage policy required for write from unauthenticated users.

-- Storage policy: seller can read payment proofs (view proof in order detail).
-- Run this AFTER creating the 'payment-proofs' bucket in the Dashboard.
CREATE POLICY "Seller can read payment proofs"
    ON storage.objects FOR SELECT
    USING (
        bucket_id = 'payment-proofs'
        AND auth.uid()::text = current_setting('app.seller_uid', true)
    );


-- =============================================================================
-- SECTION 7: REALTIME
-- =============================================================================
-- Enable Postgres Changes replication for the seller dashboard.
-- The frontend (Vue 3 + supabase-js) subscribes to these tables directly using
-- the seller's Supabase Auth JWT. RLS policies above automatically filter events
-- so the seller only receives rows they are authorized to see.
--
-- BUYER NOTE: Buyers do NOT use Realtime. They poll GET /orders/track/{token}.
--
-- FRONTEND SUBSCRIPTION PATTERN (supabase-js):
--
--   import { createClient } from '@supabase/supabase-js'
--
--   const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
--   await supabase.auth.setSession({ access_token: sellerJwt, refresh_token: '' })
--
--   const channel = supabase
--     .channel('seller-orders')
--     .on('postgres_changes', {
--       event: '*',
--       schema: 'public',
--       table: 'orders'
--     }, (payload) => {
--       console.log('Order changed:', payload)
--       // payload.eventType: 'INSERT' | 'UPDATE' | 'DELETE'
--       // payload.new: the new row (for INSERT/UPDATE)
--       // payload.old: the old row (for UPDATE/DELETE)
--     })
--     .subscribe()
--
--   // To filter by status (e.g. only active orders):
--   // Add filter: { filter: "order_status=in.(awaiting_payment,waiting_processing,processing)" }
--
-- SECURITY: RLS on 'orders' table (seller SELECT policy) ensures the seller JWT
-- only receives events for rows their policy allows. The anon key is public and
-- safe to include in frontend code; the seller JWT provides the access gate.
-- Service role key is NEVER used in frontend code.
--
-- RLS REALTIME COVERAGE CONFIRMED:
--   orders     → "Seller can view all orders"     (SELECT, authenticated, auth.uid() check) ✓
--   order_items → "Seller can view order items"   (SELECT, authenticated, auth.uid() check) ✓
--   Supabase Realtime Postgres Changes respects these policies automatically when
--   the frontend subscribes using the seller's session JWT.
-- =============================================================================
ALTER PUBLICATION supabase_realtime ADD TABLE orders;
ALTER PUBLICATION supabase_realtime ADD TABLE order_items;
