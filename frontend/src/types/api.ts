// ─── Menu ───────────────────────────────────────────────────────────────────

export interface MenuResponse {
  id: string
  name: string
  description: string | null
  price: string // Decimal serialised as string
  image_url: string | null
  is_available: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MenuCreate {
  name: string
  description?: string | null
  price: number
  image_url?: string | null
  is_available?: boolean
  is_active?: boolean
}

export interface MenuUpdate {
  name?: string | null
  description?: string | null
  price?: number | null
  image_url?: string | null
  is_available?: boolean | null
  is_active?: boolean | null
}

export interface AvailabilityUpdate {
  is_available: boolean
}

export interface ImageUploadResponse {
  image_url: string
}

// ─── Orders (buyer) ─────────────────────────────────────────────────────────

export interface OrderItemInput {
  menu_id: string
  quantity: number
}

export interface OrderCreateRequest {
  buyer_name: string
  items: OrderItemInput[]
  notes?: string | null
}

/** 201 — new order */
export interface OrderCreateResponse {
  order_number: string
  tracking_token: string
  total_amount: string
  message: string
}

/** 200 — duplicate idempotency key (no tracking_token) */
export interface OrderDuplicateResponse {
  order_number: string
  message: string
  total_amount: string
}

export interface OrderItemSnapshot {
  menu_name: string
  menu_price: string
  quantity: number
  subtotal: string
}

export interface OrderTrackResponse {
  order_number: string
  buyer_name: string
  order_status: string
  payment_status: string
  total_amount: string
  items: OrderItemSnapshot[]
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ProofUploadResponse {
  message: string
  payment_status: string
}

// ─── Orders (seller) ────────────────────────────────────────────────────────

export interface OrderListItem {
  order_number: string
  buyer_name: string
  order_status: string
  payment_status: string
  total_amount: string
  item_count: number
  created_at: string
}

export interface OrderItemDetail {
  menu_name: string
  menu_price: string
  quantity: number
  subtotal: string
  menu_id: string | null
}

export interface OrderDetailResponse {
  order_number: string
  buyer_name: string
  notes: string | null
  order_status: string
  payment_status: string
  total_amount: string
  items: OrderItemDetail[]
  payment_proof_url: string | null
  cancel_reason: string | null
  reject_reason: string | null
  created_at: string
  updated_at: string
}

export interface HistoryItem {
  order_number: string
  buyer_name: string
  order_status: string
  payment_status: string
  total_amount: string
  items: OrderItemDetail[]
  cancel_reason: string | null
  reject_reason: string | null
  created_at: string
}

export interface HistoryResponse {
  data: HistoryItem[]
  total: number
  page: number
  page_size: number
}

export interface HistoryParams {
  page?: number
  page_size?: number
  status?: string
  date_from?: string
  date_to?: string
}

// ─── Errors ─────────────────────────────────────────────────────────────────

export interface ApiErrorDetail {
  code: string
  message: string
  details?: Array<{ field: string; message: string }>
}

export interface ApiErrorResponse {
  error: ApiErrorDetail
}

export class ApiError extends Error {
  code: string
  status: number
  details?: Array<{ field: string; message: string }>

  constructor(status: number, detail: ApiErrorDetail) {
    super(detail.message)
    this.code = detail.code
    this.status = status
    this.details = detail.details
  }
}
