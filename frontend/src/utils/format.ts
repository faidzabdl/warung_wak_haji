export function formatRupiah(amount: number | string): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num)
}

export function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('id-ID', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(dateStr))
}

export const ORDER_STATUS_LABEL: Record<string, string> = {
  awaiting_payment: 'Menunggu Pembayaran',
  waiting_processing: 'Menunggu Diproses',
  processing: 'Sedang Diproses',
  completed: 'Selesai',
  cancelled: 'Dibatalkan',
}

export const PAYMENT_STATUS_LABEL: Record<string, string> = {
  pending_payment: 'Belum Bayar',
  pending_verification: 'Menunggu Verifikasi',
  paid: 'Sudah Dibayar',
  rejected: 'Ditolak',
}

export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABEL[status] ?? status
}

export function paymentStatusLabel(status: string): string {
  return PAYMENT_STATUS_LABEL[status] ?? status
}

export const ORDER_STATUS_COLOR: Record<string, string> = {
  awaiting_payment: 'bg-yellow-100 text-yellow-800',
  waiting_processing: 'bg-blue-100 text-blue-800',
  processing: 'bg-orange-100 text-orange-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
}

export const PAYMENT_STATUS_COLOR: Record<string, string> = {
  pending_payment: 'bg-gray-100 text-gray-700',
  pending_verification: 'bg-yellow-100 text-yellow-800',
  paid: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
}
