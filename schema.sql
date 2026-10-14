-- =============================================================================
-- UMKM Ordering API — Database Schema (v2)
-- =============================================================================
--
-- HOW TO RUN (fresh database):
--   1. Open your Supabase project → SQL Editor.
--   2. Search "TODO: replace with actual seller UID" and substitute the
--      placeholder UUID with the real Supabase Auth UID of the seller account.
--   3. Paste the entire file contents into the SQL Editor and click Run.
--
-- EXISTING DATABASE: run migration_v2.sql instead of this file.
--
-- STATUS TRANSITIONS (enforced in service layer):
--   order_status (QRIS):
--     awaiting_payment  → processing  (verify-payment, payment_status→paid)
--     awaiting_payment  → cancelled   (reject-payment, payment_status→rejected)
--     awaiting_payment  → cancelled   (cancel, payment_status stays pending_payment)
--   order_status (Cash):
--     waiting_processing → processing  (start-processing)
--     waiting_processing → cancelled   (cancel)
--   Both:
--     processing → ready      (mark-ready)
--     ready      → completed  (complete; cash also sets payment_status=paid)
--   cancel only allowed from: awaiting_payment, waiting_processing
--   verify-payment / reject-payment only for payment_method='qris'
-- =============================================================================


-- =============================================================================
-- SECTION 1: TABLES
-- =============================================================================

-- ---------------------------------------------------------------------------
-- menus
-- ---------------------------------------------------------------------------
CREATE TABLE menus (
    id           uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text          NOT NULL CHECK (char_length(trim(name)) > 0),
    description  text,
    price        numeric(12,2) NOT NULL CHECK (price > 0),
    image_url    text,
    menu_type    text          NOT NULL DEFAULT 'Makanan'
                     CHECK (menu_type IN ('Makanan', 'Minuman')),
    category     text          NOT NULL DEFAULT 'Umum',
    is_available boolean       NOT NULL DEFAULT true,
    is_active    boolean       NOT NULL DEFAULT true,
    created_at   timestamptz   NOT NULL DEFAULT now(),
    updated_at   timestamptz   NOT NULL DEFAULT now()
);

COMMENT ON TABLE  menus              IS 'Seller menu items. Public reads return all menus (including is_available=false) so UI can show HABIS button.';
COMMENT ON COLUMN menus.menu_type    IS 'Makanan or Minuman — used for grouping in order detail and category suggestions.';
COMMENT ON COLUMN menus.category     IS 'Free-text category, e.g. Main Dish, Side Dish, Coffee, Non Coffee.';
COMMENT ON COLUMN menus.is_available IS 'Seller can mark item temporarily unavailable (HABIS). Still returned by public API so UI shows disabled button.';
COMMENT ON COLUMN menus.is_active    IS 'Soft-delete flag. Inactive menus are hidden from all public endpoints.';

-- ---------------------------------------------------------------------------
-- orders
-- ---------------------------------------------------------------------------
CREATE TABLE orders (
    id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number        text          NOT NULL UNIQUE,
    idempotency_key     text          UNIQUE,
    buyer_name          text          NOT NULL CHECK (char_length(trim(buyer_name)) > 0),
    table_number        text          NOT NULL,
    payment_method      text          NOT NULL
                            CHECK (payment_method IN ('qris', 'cash')),
    notes               text,
    payment_status      text          NOT NULL DEFAULT 'pending_payment'
                            CHECK (payment_status IN (
                                'pending_payment',
                                'paid',
                                'rejected'
                            )),
    order_status        text          NOT NULL DEFAULT 'awaiting_payment'
                            CHECK (order_status IN (
                                'awaiting_payment',
                                'waiting_processing',
                                'processing',
                                'ready',
                                'completed',
                                'cancelled'
                            )),
    tracking_token_hash text          NOT NULL UNIQUE,
    total_amount        numeric(12,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    cancel_reason       text,
    created_at          timestamptz   NOT NULL DEFAULT now(),
    updated_at          timestamptz   NOT NULL DEFAULT now()
);

COMMENT ON TABLE  orders                     IS 'Buyer orders. All buyer writes go through FastAPI service-role client; no direct public inserts.';
COMMENT ON COLUMN orders.order_number        IS 'Human-readable unique identifier: ORD-YYYYMMDD-XXXX.';
COMMENT ON COLUMN orders.table_number        IS 'Meja number as text (1–9999). Stored as text for flexibility. Backend validates ^\d{1,4}$ on create.';
COMMENT ON COLUMN orders.payment_method      IS 'qris or cash. Determines initial order_status: qris→awaiting_payment, cash→waiting_processing.';
COMMENT ON COLUMN orders.idempotency_key     IS 'Optional client-supplied key for deduplication.';
COMMENT ON COLUMN orders.tracking_token_hash IS 'SHA-256(token_urlsafe(32)). Plain token shown to buyer once only.';
COMMENT ON COLUMN orders.total_amount        IS 'Sum of order_items.subtotal. Set by create_order_with_items RPC.';

-- ---------------------------------------------------------------------------
-- order_items
-- ---------------------------------------------------------------------------
CREATE TABLE order_items (
    id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id             uuid          NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_id              uuid          REFERENCES menus(id) ON DELETE SET NULL,
    menu_name_snapshot   text          NOT NULL,
    menu_price_snapshot  numeric(12,2) NOT NULL CHECK (menu_price_snapshot > 0),
    menu_type            text          NOT NULL,
    quantity             integer       NOT NULL CHECK (quantity > 0),
    subtotal             numeric(12,2) NOT NULL CHECK (subtotal > 0),
    created_at           timestamptz   NOT NULL DEFAULT now()
);

COMMENT ON TABLE  order_items                     IS 'Immutable snapshot of each line item at order creation time.';
COMMENT ON COLUMN order_items.menu_id             IS 'Nullable FK — set to NULL if source menu is deleted. Snapshot fields preserve original values.';
COMMENT ON COLUMN order_items.menu_name_snapshot  IS 'Name at time of order; immutable even if menu is later renamed.';
COMMENT ON COLUMN order_items.menu_price_snapshot IS 'Price at time of order; immutable even if menu price changes.';
COMMENT ON COLUMN order_items.menu_type           IS 'Snapshot of menu_type (Makanan/Minuman) for grouping in order detail popup even after menu deletion.';

-- ---------------------------------------------------------------------------
-- audit_logs
-- ---------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id   uuid        REFERENCES orders(id) ON DELETE SET NULL,
    action     text        NOT NULL,
    actor      text        NOT NULL,
    metadata   jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  audit_logs        IS 'Immutable append-only log of seller actions on orders.';
COMMENT ON COLUMN audit_logs.action IS 'payment_verified | payment_rejected | processing_started | order_ready | order_completed | order_cancelled';
COMMENT ON COLUMN audit_logs.actor  IS 'UID of the seller or the string ''system''.';


-- =============================================================================
-- SECTION 2: INDEXES
-- =============================================================================

CREATE INDEX ON orders (order_status);
CREATE INDEX ON orders (payment_status);
CREATE INDEX ON orders (payment_method);
CREATE INDEX ON orders (created_at DESC);
CREATE UNIQUE INDEX ON orders (tracking_token_hash);
CREATE UNIQUE INDEX ON orders (order_number);
CREATE INDEX ON orders (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX ON order_items (order_id);
CREATE INDEX ON audit_logs (order_id);


-- =============================================================================
-- SECTION 3: UPDATED_AT TRIGGER
-- =============================================================================

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
-- Determines initial order_status and payment_status from payment_method:
--   qris  → awaiting_payment  / pending_payment
--   cash  → waiting_processing / pending_payment
--
-- Validates each menu item: must exist, is_active=true, is_available=true.
-- Snapshots menu_type per item.
-- Calculates total_amount from DB prices (ignores any client-provided price).

CREATE OR REPLACE FUNCTION create_order_with_items(
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

    -- Determine initial statuses based on payment method
    IF v_payment_method = 'qris' THEN
        v_order_status   := 'awaiting_payment';
        v_payment_status := 'pending_payment';
    ELSIF v_payment_method = 'cash' THEN
        v_order_status   := 'waiting_processing';
        v_payment_status := 'pending_payment';
    ELSE
        RAISE EXCEPTION 'Invalid payment_method: %', v_payment_method;
    END IF;

    -- 1. Insert the order row
    INSERT INTO orders (
        order_number,
        idempotency_key,
        buyer_name,
        table_number,
        payment_method,
        notes,
        payment_status,
        order_status,
        tracking_token_hash
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

    -- 2. Insert all order_items rows with validation
    FOREACH v_item IN ARRAY items_data LOOP
        SELECT * INTO v_menu
        FROM   menus
        WHERE  id = (v_item->>'menu_id')::uuid;

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
            order_id,
            menu_id,
            menu_name_snapshot,
            menu_price_snapshot,
            menu_type,
            quantity,
            subtotal
        )
        VALUES (
            v_order.id,
            v_menu.id,
            v_menu.name,
            v_menu.price,
            v_menu.menu_type,
            (v_item->>'quantity')::integer,
            v_subtotal
        );
    END LOOP;

    -- 3. Update total_amount from computed sum
    UPDATE orders
       SET total_amount = v_total
     WHERE id = v_order.id
    RETURNING * INTO v_order;

    RETURN v_order;

EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$;

COMMENT ON FUNCTION create_order_with_items(jsonb, jsonb[]) IS
    'v2: Atomically inserts orders + order_items. '
    'Determines initial status from payment_method. '
    'Validates menu is_active and is_available. Snapshots menu_type per item. '
    'Calculates total from DB prices. SECURITY DEFINER runs as postgres.';


-- =============================================================================
-- SECTION 5: ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE menus       ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders      ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs  ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- SELLER UID PLACEHOLDER
-- TODO: replace '00000000-0000-0000-0000-000000000000' with actual seller UID
-- ---------------------------------------------------------------------------

-- ---- menus ----------------------------------------------------------------

-- Public SELECT: returns ALL menus for active items (including is_available=false)
-- so buyer UI can show "HABIS" button. Availability validated in create_order RPC.
CREATE POLICY "Public can view active menus"
    ON menus FOR SELECT
    TO anon
    USING (is_active = true);

CREATE POLICY "Seller can view all menus"
    ON menus FOR SELECT
    TO authenticated
    USING (auth.uid()::text = current_setting('app.seller_uid', true));

CREATE POLICY "Seller can insert menus"
    ON menus FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid()::text = current_setting('app.seller_uid', true));

CREATE POLICY "Seller can update menus"
    ON menus FOR UPDATE
    TO authenticated
    USING (auth.uid()::text = current_setting('app.seller_uid', true))
    WITH CHECK (auth.uid()::text = current_setting('app.seller_uid', true));

CREATE POLICY "Seller can delete menus"
    ON menus FOR DELETE
    TO authenticated
    USING (auth.uid()::text = current_setting('app.seller_uid', true));

-- ---- orders ---------------------------------------------------------------

CREATE POLICY "Seller can view all orders"
    ON orders FOR SELECT
    TO authenticated
    USING (auth.uid()::text = current_setting('app.seller_uid', true));

CREATE POLICY "Seller can update orders"
    ON orders FOR UPDATE
    TO authenticated
    USING (auth.uid()::text = current_setting('app.seller_uid', true))
    WITH CHECK (auth.uid()::text = current_setting('app.seller_uid', true));

-- ---- order_items ----------------------------------------------------------

CREATE POLICY "Seller can view order items"
    ON order_items FOR SELECT
    TO authenticated
    USING (auth.uid()::text = current_setting('app.seller_uid', true));

-- ---- audit_logs -----------------------------------------------------------

CREATE POLICY "Seller can view audit logs"
    ON audit_logs FOR SELECT
    TO authenticated
    USING (auth.uid()::text = current_setting('app.seller_uid', true));


-- =============================================================================
-- SECTION 6: STORAGE SETUP
-- =============================================================================
--
-- Only ONE bucket is needed (payment-proofs bucket removed in v2):
--
-- Bucket: menu-images
--   - Visibility: PUBLIC (public read enabled)
--   - Purpose: menu item images uploaded by seller via FastAPI backend
--   - Backend upload path: {uuid4}.{ext}
--   - No extra read policy needed (bucket is public)
--   - Write handled by service-role client in backend


-- =============================================================================
-- SECTION 7: REALTIME
-- =============================================================================
ALTER PUBLICATION supabase_realtime ADD TABLE orders;
ALTER PUBLICATION supabase_realtime ADD TABLE order_items;
