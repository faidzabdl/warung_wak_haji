<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold">Pesanan Aktif</h1>
      <div class="flex items-center gap-2">
        <span class="text-xs text-muted-foreground">Auto-refresh 30 detik</span>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">Refresh</Button>
      </div>
    </div>

    <div v-if="loading && orders.length === 0">
      <Skeleton v-for="i in 3" :key="i" class="h-16 rounded mb-2" />
    </div>

    <div v-else-if="error" class="text-destructive text-sm">{{ error }}</div>

    <div v-else-if="orders.length === 0" class="text-muted-foreground text-center py-12">
      Tidak ada pesanan aktif.
    </div>

    <div v-else class="border rounded-lg overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-muted/40">
          <tr>
            <th class="text-left px-3 py-2">No. Pesanan</th>
            <th class="text-left px-3 py-2">Pembeli</th>
            <th class="text-left px-3 py-2">Status</th>
            <th class="text-left px-3 py-2">Pembayaran</th>
            <th class="text-left px-3 py-2">Total</th>
            <th class="text-left px-3 py-2">Waktu</th>
            <th class="px-3 py-2">Aksi</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="order in orders"
            :key="order.order_number"
            class="border-t hover:bg-muted/20 cursor-pointer"
            @click="openDetail(order.order_number)"
          >
            <td class="px-3 py-3 font-mono font-medium">{{ order.order_number }}</td>
            <td class="px-3 py-3">{{ order.buyer_name }}</td>
            <td class="px-3 py-3"><StatusBadge :status="order.order_status" type="order" /></td>
            <td class="px-3 py-3"><StatusBadge :status="order.payment_status" type="payment" /></td>
            <td class="px-3 py-3">{{ formatRupiah(order.total_amount) }}</td>
            <td class="px-3 py-3 text-muted-foreground text-xs">{{ formatDate(order.created_at) }}</td>
            <td class="px-3 py-3" @click.stop>
              <div class="flex gap-1 flex-wrap justify-end">
                <!-- Verify / Reject payment -->
                <template v-if="order.order_status === 'awaiting_payment' && order.payment_status === 'pending_verification'">
                  <Button size="sm" class="text-xs" :disabled="!!actingOn" @click="verifyPay(order)">Verifikasi</Button>
                  <Button size="sm" variant="destructive" class="text-xs" :disabled="!!actingOn" @click="openReject(order)">Tolak</Button>
                </template>
                <!-- Start processing -->
                <template v-if="order.order_status === 'waiting_processing'">
                  <Button size="sm" class="text-xs" :disabled="!!actingOn" @click="startProc(order)">Proses</Button>
                </template>
                <!-- Complete -->
                <template v-if="order.order_status === 'processing'">
                  <Button size="sm" class="text-xs" :disabled="!!actingOn" @click="complete(order)">Selesai</Button>
                </template>
                <!-- Cancel (any non-terminal) -->
                <Button
                  v-if="!['completed', 'cancelled'].includes(order.order_status)"
                  size="sm"
                  variant="outline"
                  class="text-xs"
                  :disabled="!!actingOn"
                  @click="openCancel(order)"
                >
                  Batalkan
                </Button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Order detail modal -->
    <OrderDetailModal
      v-if="detailOrder"
      :order="detailOrder"
      @close="detailOrder = null"
    />

    <!-- Reject reason dialog -->
    <ReasonDialog
      v-if="rejectTarget"
      title="Tolak Pembayaran"
      description="Masukkan alasan penolakan pembayaran."
      reason-label="Alasan Penolakan"
      confirm-label="Tolak Pembayaran"
      :submitting="!!actingOn"
      @confirm="doReject"
      @cancel="rejectTarget = null"
    />

    <!-- Cancel reason dialog -->
    <ReasonDialog
      v-if="cancelTarget"
      title="Batalkan Pesanan"
      description="Masukkan alasan pembatalan pesanan."
      reason-label="Alasan Pembatalan"
      confirm-label="Batalkan Pesanan"
      :submitting="!!actingOn"
      @confirm="doCancel"
      @cancel="cancelTarget = null"
    />

    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { toast } from 'vue-sonner'
import {
  getSellerOrders, getOrderDetail,
  verifyPayment, rejectPayment, startProcessing, completeOrder, cancelOrder
} from '@/lib/api'
import { ApiError, type OrderListItem, type OrderDetailResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'
import { formatRupiah, formatDate } from '@/utils/format'
import StatusBadge from '@/components/buyer/StatusBadge.vue'
import OrderDetailModal from '@/components/seller/OrderDetailModal.vue'
import ReasonDialog from '@/components/seller/ReasonDialog.vue'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Toaster } from '@/components/ui/sonner'

const authStore = useAuthStore()
const token = computed(() => authStore.accessToken ?? '')

const orders = ref<OrderListItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const actingOn = ref<string | null>(null)
const detailOrder = ref<OrderDetailResponse | null>(null)
const rejectTarget = ref<OrderListItem | null>(null)
const cancelTarget = ref<OrderListItem | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    orders.value = await getSellerOrders(token.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Gagal memuat pesanan.'
  } finally {
    loading.value = false
  }
}

async function openDetail(orderNumber: string) {
  try {
    detailOrder.value = await getOrderDetail(orderNumber, token.value)
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : 'Gagal memuat detail.')
  }
}

async function verifyPay(order: OrderListItem) {
  actingOn.value = order.order_number
  try {
    await verifyPayment(order.order_number, token.value)
    toast.success('Pembayaran diverifikasi!')
    load()
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : 'Gagal verifikasi.')
  } finally {
    actingOn.value = null
  }
}

function openReject(order: OrderListItem) { rejectTarget.value = order }
function openCancel(order: OrderListItem) { cancelTarget.value = order }

async function doReject(reason: string) {
  if (!rejectTarget.value) return
  actingOn.value = rejectTarget.value.order_number
  try {
    await rejectPayment(rejectTarget.value.order_number, reason, token.value)
    toast.success('Pembayaran ditolak.')
    rejectTarget.value = null
    load()
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : 'Gagal menolak pembayaran.')
  } finally {
    actingOn.value = null
  }
}

async function startProc(order: OrderListItem) {
  actingOn.value = order.order_number
  try {
    await startProcessing(order.order_number, token.value)
    toast.success('Pesanan mulai diproses.')
    load()
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : 'Gagal memulai pemrosesan.')
  } finally {
    actingOn.value = null
  }
}

async function complete(order: OrderListItem) {
  actingOn.value = order.order_number
  try {
    await completeOrder(order.order_number, token.value)
    toast.success('Pesanan selesai!')
    load()
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : 'Gagal menyelesaikan pesanan.')
  } finally {
    actingOn.value = null
  }
}

async function doCancel(reason: string) {
  if (!cancelTarget.value) return
  actingOn.value = cancelTarget.value.order_number
  try {
    await cancelOrder(cancelTarget.value.order_number, reason, token.value)
    toast.success('Pesanan dibatalkan.')
    cancelTarget.value = null
    load()
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : 'Gagal membatalkan pesanan.')
  } finally {
    actingOn.value = null
  }
}

onMounted(() => {
  load()
  // Poll every 30 seconds (Realtime subscription is the better long-term solution)
  const interval = setInterval(load, 30_000)
  onUnmounted(() => clearInterval(interval))
})
</script>
