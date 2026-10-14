<template>
  <div>
    <div v-if="loading && orders.length === 0" class="og">
      <div v-for="i in 3" :key="i" class="card oc" style="min-height:160px;opacity:.4"></div>
    </div>

    <div v-else-if="error" class="empty" style="color:var(--line)">{{ error }}</div>

    <p v-else-if="orders.length === 0" class="empty">
      Belum ada pesanan aktif. Pesanan baru akan muncul otomatis.
    </p>

    <!-- Order cards -->
    <div v-else class="og">
      <article
        v-for="o in orders"
        :key="o.order_number"
        class="card oc"
        :class="o.order_status"
      >
        <!-- Header -->
        <div class="oc-head">
          <div>
            <h3 class="name oc-meja">Meja {{ o.table_number }}</h3>
            <p class="oc-sub">{{ o.buyer_name }} · {{ fmtDate(o.created_at) }} · {{ o.order_number }}</p>
          </div>
          <span class="badge">{{ STATUS_LABEL[o.order_status] ?? o.order_status }}</span>
        </div>

        <!-- Summary row -->
        <div class="total-row">
          <span>{{ o.item_count }} item · {{ o.payment_method === 'qris' ? 'QRIS' : 'Tunai' }}</span>
          <span>{{ rp(o.total_amount) }}</span>
        </div>

        <!-- Action buttons -->
        <div class="oc-actions">
          <!-- awaiting_payment (QRIS) -->
          <template v-if="o.order_status === 'awaiting_payment'">
            <button class="act main" type="button" :disabled="!!actingOn" @click="verifyPay(o)">Konfirmasi Bayar</button>
            <button class="act" type="button" :disabled="!!actingOn" @click="openReject(o)">Tolak</button>
          </template>
          <!-- waiting_processing (Cash) -->
          <template v-else-if="o.order_status === 'waiting_processing'">
            <button class="act main" type="button" :disabled="!!actingOn" @click="startProc(o)">Proses Pesanan</button>
            <button class="act" type="button" :disabled="!!actingOn" @click="openCancel(o)">Batalkan</button>
          </template>
          <!-- processing -->
          <template v-else-if="o.order_status === 'processing'">
            <button class="act" type="button" :disabled="!!actingOn" @click="openDetail(o.order_number)">Buka Pesanan</button>
            <button class="act main" type="button" :disabled="!!actingOn" @click="markReadyOrder(o)">Siap Disajikan</button>
          </template>
          <!-- ready -->
          <template v-else-if="o.order_status === 'ready'">
            <button class="act" type="button" :disabled="!!actingOn" @click="openDetail(o.order_number)">Buka Pesanan</button>
            <button class="act main" type="button" :disabled="!!actingOn" @click="complete(o)">
              {{ o.payment_method === 'cash' ? 'Terima Tunai & Selesai' : 'Selesai' }}
            </button>
          </template>
        </div>
      </article>
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
      description="Masukkan alasan penolakan (opsional)."
      confirm-label="Tolak Pembayaran"
      :submitting="!!actingOn"
      @confirm="doReject"
      @cancel="rejectTarget = null"
    />

    <!-- Cancel reason dialog -->
    <ReasonDialog
      v-if="cancelTarget"
      title="Batalkan Pesanan"
      description="Masukkan alasan pembatalan (opsional)."
      confirm-label="Batalkan Pesanan"
      :submitting="!!actingOn"
      @confirm="doCancel"
      @cancel="cancelTarget = null"
    />

    <!-- Toast -->
    <transition name="t">
      <div v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  getSellerOrders, getOrderDetail,
  verifyPayment, rejectPayment, startProcessing, markReady, completeOrder, cancelOrder,
} from '@/lib/api'
import { ApiError, type OrderListItem, type OrderDetailResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'
import OrderDetailModal from '@/components/seller/OrderDetailModal.vue'
import ReasonDialog from '@/components/seller/ReasonDialog.vue'

const authStore = useAuthStore()
const token = computed(() => authStore.accessToken ?? '')

const STATUS_LABEL: Record<string, string> = {
  awaiting_payment: 'Menunggu Pembayaran',
  waiting_processing: 'Pesanan Dibuat',
  processing: 'Sedang Diproses',
  ready: 'Siap Disajikan',
  completed: 'Selesai',
  cancelled: 'Dibatalkan',
}

const orders = ref<OrderListItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const actingOn = ref<string | null>(null)
const detailOrder = ref<OrderDetailResponse | null>(null)
const rejectTarget = ref<OrderListItem | null>(null)
const cancelTarget = ref<OrderListItem | null>(null)
const toastMsg = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

function rp(n: number | string) {
  const num = typeof n === 'string' ? parseFloat(n) : n
  return 'Rp ' + num.toLocaleString('id-ID')
}

function fmtDate(t: string) {
  return t ? new Date(t).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-'
}

function say(msg: string) {
  toastMsg.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, 3600)
}

async function load() {
  if (document.hidden) return
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
    say(e instanceof ApiError ? e.message : 'Gagal memuat detail.')
  }
}

async function verifyPay(o: OrderListItem) {
  actingOn.value = o.order_number
  try {
    await verifyPayment(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Pembayaran dikonfirmasi`)
    load()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal verifikasi.')
  } finally { actingOn.value = null }
}

function openReject(o: OrderListItem) { rejectTarget.value = o }
function openCancel(o: OrderListItem) { cancelTarget.value = o }

async function doReject(reason: string | null) {
  if (!rejectTarget.value) return
  actingOn.value = rejectTarget.value.order_number
  try {
    await rejectPayment(rejectTarget.value.order_number, reason, token.value)
    say(`Pesanan ${rejectTarget.value.order_number}: Ditolak`)
    rejectTarget.value = null
    load()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal menolak.')
  } finally { actingOn.value = null }
}

async function startProc(o: OrderListItem) {
  actingOn.value = o.order_number
  try {
    await startProcessing(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Sedang Diproses`)
    load()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal memulai.')
  } finally { actingOn.value = null }
}

async function markReadyOrder(o: OrderListItem) {
  actingOn.value = o.order_number
  try {
    await markReady(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Siap Disajikan`)
    load()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal menandai siap.')
  } finally { actingOn.value = null }
}

async function complete(o: OrderListItem) {
  actingOn.value = o.order_number
  try {
    await completeOrder(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Selesai`)
    load()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal menyelesaikan.')
  } finally { actingOn.value = null }
}

async function doCancel(reason: string | null) {
  if (!cancelTarget.value) return
  actingOn.value = cancelTarget.value.order_number
  try {
    await cancelOrder(cancelTarget.value.order_number, reason, token.value)
    say(`Pesanan ${cancelTarget.value.order_number}: Dibatalkan`)
    cancelTarget.value = null
    load()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal membatalkan.')
  } finally { actingOn.value = null }
}

let interval: ReturnType<typeof setInterval> | null = null

onMounted(() => { load(); interval = setInterval(load, 8_000) })
onUnmounted(() => { if (interval !== null) clearInterval(interval) })
</script>

<style scoped>
.t-enter-active, .t-leave-active { transition: opacity .25s, transform .25s; }
.t-enter-from, .t-leave-to { opacity: 0; transform: translate(-50%, 10px); }
.toast {
  position: fixed; z-index: 60; left: 50%;
  bottom: calc(20px + env(safe-area-inset-bottom, 0px));
  transform: translateX(-50%);
  max-width: calc(100% - 32px);
  background: var(--toast-bg); color: var(--toast-ink);
  padding: 12px 18px; border-radius: 12px;
  font-size: .85rem; font-weight: 500;
  box-shadow: 0 8px 24px rgba(0,0,0,.3); text-align: center;
}
</style>
