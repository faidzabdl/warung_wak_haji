import {
  ApiError,
  type ApiErrorResponse,
  type AvailabilityUpdate,
  type HistoryParams,
  type ImageUploadResponse,
  type MenuCreate,
  type MenuResponse,
  type MenuUpdate,
  type OrderCreateRequest,
  type OrderCreateResponse,
  type OrderDetailResponse,
  type OrderDuplicateResponse,
  type OrderListItem,
  type OrderTrackResponse,
  type HistoryResponse,
} from '@/types/api'

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

// ─── Internal helper ────────────────────────────────────────────────────────

async function request<T>(
  method: string,
  path: string,
  options: {
    token?: string
    body?: unknown
    formData?: FormData
    headers?: Record<string, string>
  } = {}
): Promise<T> {
  const headers: Record<string, string> = { ...options.headers }

  if (options.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
  })

  if (!res.ok) {
    let errBody: ApiErrorResponse | null = null
    try {
      errBody = (await res.json()) as ApiErrorResponse
    } catch {
      // non-JSON error body
    }
    const detail = errBody?.error ?? { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    throw new ApiError(res.status, detail)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T

  return res.json() as Promise<T>
}

// ─── Public — Menu ───────────────────────────────────────────────────────────

export async function getMenus(): Promise<MenuResponse[]> {
  return request<MenuResponse[]>('GET', '/menus')
}

export async function getMenuDetail(menuId: string): Promise<MenuResponse> {
  return request<MenuResponse>('GET', `/menus/${menuId}`)
}

// ─── Buyer — Orders ──────────────────────────────────────────────────────────

export async function createOrder(
  body: OrderCreateRequest,
  idempotencyKey?: string
): Promise<{ data: OrderCreateResponse | OrderDuplicateResponse; status: number }> {
  const extraHeaders: Record<string, string> = {}
  if (idempotencyKey) extraHeaders['Idempotency-Key'] = idempotencyKey

  // We need the raw status code to distinguish 201 vs 200
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  }
  const res = await fetch(`${BASE_URL}/orders`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    let errBody: ApiErrorResponse | null = null
    try { errBody = await res.json() } catch { /* empty */ }
    const detail = errBody?.error ?? { code: 'HTTP_ERROR', message: `HTTP ${res.status}` }
    throw new ApiError(res.status, detail)
  }

  const data = await res.json()
  return { data, status: res.status }
}

export async function trackOrder(token: string): Promise<OrderTrackResponse> {
  return request<OrderTrackResponse>('GET', `/orders/track/${token}`)
}

// ─── Seller — Menus ──────────────────────────────────────────────────────────

export async function getSellerMenus(token: string): Promise<MenuResponse[]> {
  return request<MenuResponse[]>('GET', '/seller/menus', { token })
}

export async function uploadMenuImage(file: File, token: string): Promise<ImageUploadResponse> {
  const fd = new FormData()
  fd.append('file', file)
  return request<ImageUploadResponse>('POST', '/seller/menus/upload-image', { token, formData: fd })
}

export async function createMenu(body: MenuCreate, token: string): Promise<MenuResponse> {
  return request<MenuResponse>('POST', '/seller/menus', { token, body })
}

export async function updateMenu(
  menuId: string,
  body: MenuUpdate,
  token: string
): Promise<MenuResponse> {
  return request<MenuResponse>('PATCH', `/seller/menus/${menuId}`, { token, body })
}

export async function setMenuAvailability(
  menuId: string,
  isAvailable: boolean,
  token: string
): Promise<MenuResponse> {
  const body: AvailabilityUpdate = { is_available: isAvailable }
  return request<MenuResponse>('PATCH', `/seller/menus/${menuId}/availability`, { token, body })
}

export async function deleteMenu(menuId: string, token: string): Promise<void> {
  return request<void>('DELETE', `/seller/menus/${menuId}`, { token })
}

// ─── Seller — Orders ─────────────────────────────────────────────────────────

export async function getSellerOrders(token: string): Promise<OrderListItem[]> {
  return request<OrderListItem[]>('GET', '/seller/orders', { token })
}

export async function getOrderDetail(orderNumber: string, token: string): Promise<OrderDetailResponse> {
  return request<OrderDetailResponse>('GET', `/seller/orders/${orderNumber}`, { token })
}

export async function verifyPayment(
  orderNumber: string,
  token: string
): Promise<{ order_number: string; order_status: string; payment_status: string }> {
  return request('POST', `/seller/orders/${orderNumber}/verify-payment`, { token })
}

export async function rejectPayment(
  orderNumber: string,
  reason: string | null | undefined,
  token: string
): Promise<{ order_number: string; order_status: string; payment_status: string }> {
  return request('POST', `/seller/orders/${orderNumber}/reject-payment`, { token, body: { reason: reason ?? null } })
}

export async function startProcessing(
  orderNumber: string,
  token: string
): Promise<{ order_number: string; order_status: string }> {
  return request('POST', `/seller/orders/${orderNumber}/start-processing`, { token })
}

export async function markReady(
  orderNumber: string,
  token: string
): Promise<{ order_number: string; order_status: string }> {
  return request('POST', `/seller/orders/${orderNumber}/mark-ready`, { token })
}

export async function completeOrder(
  orderNumber: string,
  token: string
): Promise<{ order_number: string; order_status: string }> {
  return request('POST', `/seller/orders/${orderNumber}/complete`, { token })
}

export async function cancelOrder(
  orderNumber: string,
  reason: string | null | undefined,
  token: string
): Promise<{ order_number: string; order_status: string }> {
  return request('POST', `/seller/orders/${orderNumber}/cancel`, { token, body: { reason: reason ?? null } })
}

export async function getHistory(
  params: HistoryParams,
  token: string
): Promise<HistoryResponse> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  if (params.status) qs.set('status', params.status)
  if (params.date_from) qs.set('date_from', params.date_from)
  if (params.date_to) qs.set('date_to', params.date_to)
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return request<HistoryResponse>('GET', `/seller/history${query}`, { token })
}
