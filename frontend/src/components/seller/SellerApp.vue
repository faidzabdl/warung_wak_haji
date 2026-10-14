<template>
  <div>
    <!-- Not logged in: prompt to seller dashboard -->
    <template v-if="!authStore.isLoggedIn">
      <div class="flex flex-col items-center justify-center py-20 gap-4 text-center">
        <p class="font-bold text-lg">Mode Penjual</p>
        <p class="text-sm" style="color:var(--wwh-muted)">Login sebagai penjual untuk mengelola pesanan.</p>
        <RouterLink
          to="/seller/login"
          class="submit"
          style="display:inline-block;text-decoration:none;padding:9px 28px"
        >
          Login Penjual →
        </RouterLink>
      </div>
    </template>

    <!-- Logged in: embedded seller panel -->
    <template v-else>
      <!-- Tab nav (.snav) -->
      <nav class="snav" role="tablist" aria-label="Menu penjual">
        <button
          v-for="t in tabs"
          :key="t.id"
          type="button"
          role="tab"
          :class="{ on: tab === t.id }"
          :aria-selected="tab === t.id"
          @click="tab = (t.id as 'orders' | 'history' | 'edit')"
        >
          <span class="ni" v-html="t.icon"></span>
          <span>{{ t.label }}</span>
          <i v-if="t.n" class="cnt">{{ t.n }}</i>
        </button>
      </nav>

      <!-- Pemesanan -->
      <section v-if="tab === 'orders'" aria-label="Pemesanan masuk">
        <div v-if="loadingOrders" class="empty">Memuat pesanan…</div>
        <div v-else-if="ordersError" class="empty" style="color:var(--line)">{{ ordersError }}</div>
        <div v-else-if="orders.length === 0" class="empty">Belum ada pesanan aktif.</div>
        <div v-else class="og">
          <article
            v-for="o in orders"
            :key="o.order_number"
            class="card oc"
            :class="o.order_status"
          >
            <div class="oc-head">
              <div>
                <h3 class="name oc-meja">Meja {{ o.table_number }}</h3>
                <p class="oc-sub">{{ o.buyer_name }} · {{ fmtDate(o.created_at) }} · {{ o.order_number }}</p>
              </div>
              <span class="badge">{{ STATUS_LABEL[o.order_status] ?? o.order_status }}</span>
            </div>
            <div class="total-row">
              <span>{{ o.item_count }} item · {{ o.payment_method === 'qris' ? 'QRIS' : 'Tunai' }}</span>
              <span>{{ rp(o.total_amount) }}</span>
            </div>
            <div class="oc-actions" @click.stop>
              <!-- awaiting_payment (QRIS) -->
              <template v-if="o.order_status === 'awaiting_payment'">
                <button class="act main" type="button" :disabled="!!acting" @click="doVerify(o)">Konfirmasi Bayar</button>
                <button class="act" type="button" :disabled="!!acting" @click="openReject(o)">Tolak</button>
              </template>
              <!-- waiting_processing (Cash) -->
              <template v-else-if="o.order_status === 'waiting_processing'">
                <button class="act main" type="button" :disabled="!!acting" @click="doStart(o)">Proses Pesanan</button>
                <button class="act" type="button" :disabled="!!acting" @click="openCancel(o)">Batalkan</button>
              </template>
              <!-- processing -->
              <template v-else-if="o.order_status === 'processing'">
                <button class="act" type="button" :disabled="!!acting" @click="openDetail(o.order_number)">Buka Pesanan</button>
                <button class="act main" type="button" :disabled="!!acting" @click="doMarkReady(o)">Siap Disajikan</button>
              </template>
              <!-- ready -->
              <template v-else-if="o.order_status === 'ready'">
                <button class="act" type="button" :disabled="!!acting" @click="openDetail(o.order_number)">Buka Pesanan</button>
                <button class="act main" type="button" :disabled="!!acting" @click="doComplete(o)">
                  {{ o.payment_method === 'cash' ? 'Terima Tunai & Selesai' : 'Selesai' }}
                </button>
              </template>
            </div>
          </article>
        </div>

        <!-- Order detail modal (prototype-style) -->
        <div v-if="detail" class="ov" @mousedown.self="detail = null">
          <div class="modal bare" role="dialog" aria-modal="true" tabindex="-1" @keydown.escape="detail = null">
            <div class="dt-head">
              <p>Nama Pemesan: {{ detail.buyer_name }}</p>
              <p>No. Meja: {{ detail.table_number }}</p>
            </div>
            <template v-for="(g, i) in detailGroups" :key="g.label">
              <div class="dt-grid">
                <span class="dt-lab">{{ g.label }}</span>
                <span class="dt-lab">{{ i === 0 ? 'QTY' : '' }}</span>
                <span class="dt-lab">{{ i === 0 ? 'HARGA' : '' }}</span>
                <template v-for="item in g.items" :key="item.name + item.qty">
                  <span class="dt-name">{{ item.name }}</span>
                  <span class="dt-qty">{{ item.qty }}</span>
                  <span class="dt-price">{{ rp(item.subtotal) }}</span>
                </template>
              </div>
            </template>
            <div class="dt-total">
              <span>TOTAL</span>
              <span></span>
              <span>{{ rp(detail.total_amount) }}</span>
            </div>
            <div class="m-foot" style="justify-content:center;margin-top:20px">
              <button class="dt-close" type="button" @click="detail = null">TUTUP</button>
            </div>
          </div>
        </div>

        <!-- Reject dialog -->
        <div v-if="rejectTarget" class="ov" @mousedown.self="rejectTarget = null">
          <div class="modal" role="dialog" aria-modal="true" tabindex="-1" @keydown.escape="rejectTarget = null">
            <button class="x" type="button" @click="rejectTarget = null">×</button>
            <h3 class="m-title">Tolak Pembayaran</h3>
            <div class="mf">
              <label for="reject-reason">Alasan (opsional)</label>
              <input id="reject-reason" v-model="rejectReason" placeholder="Masukkan alasan..." />
            </div>
            <div class="m-foot">
              <button class="btn-ghost" type="button" :disabled="!!acting" @click="rejectTarget = null">Batal</button>
              <button class="btn-main" type="button" :disabled="!!acting" @click="doReject">
                {{ acting ? 'Memproses…' : 'Tolak Pembayaran' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Cancel dialog -->
        <div v-if="cancelTarget" class="ov" @mousedown.self="cancelTarget = null">
          <div class="modal" role="dialog" aria-modal="true" tabindex="-1" @keydown.escape="cancelTarget = null">
            <button class="x" type="button" @click="cancelTarget = null">×</button>
            <h3 class="m-title">Batalkan Pesanan</h3>
            <div class="mf">
              <label for="cancel-reason">Alasan (opsional)</label>
              <input id="cancel-reason" v-model="cancelReason" placeholder="Masukkan alasan..." />
            </div>
            <div class="m-foot">
              <button class="btn-ghost" type="button" :disabled="!!acting" @click="cancelTarget = null">Kembali</button>
              <button class="btn-main" type="button" :disabled="!!acting" @click="doCancel">
                {{ acting ? 'Memproses…' : 'Batalkan Pesanan' }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- History -->
      <section v-else-if="tab === 'history'" aria-label="Riwayat pesanan">
        <div v-if="loadingHistory" class="empty">Memuat…</div>
        <div v-else-if="historyError" class="empty" style="color:var(--line)">{{ historyError }}</div>
        <template v-else>
          <div class="stats">
            <div class="stat wide"><span>Total Pendapatan</span><b>{{ rp(history.total_revenue) }}</b></div>
            <div class="stat"><span>Selesai</span><b>{{ history.completed_count }}</b></div>
            <div class="stat"><span>Dibatalkan</span><b>{{ history.cancelled_count }}</b></div>
          </div>
          <div v-if="history.data.length">
            <p class="hist-top" style="margin-bottom:10px"><strong style="font-size:.9rem">Riwayat Pesanan</strong></p>
            <ul class="hist">
              <li v-for="o in history.data" :key="o.order_number" :class="o.order_status">
                <div class="h-main">
                  <b>Meja {{ o.table_number }} · {{ o.buyer_name }}</b>
                  <p>{{ o.items.map(i => i.name + ' ×' + i.qty).join(', ') }}</p>
                  <p>{{ o.order_number }} · {{ fmtDate(o.created_at) }} · {{ o.payment_method === 'qris' ? 'QRIS' : 'Tunai' }}</p>
                </div>
                <div class="h-side">
                  <b>{{ rp(o.total_amount) }}</b>
                  <span class="badge">{{ STATUS_LABEL[o.order_status] ?? o.order_status }}</span>
                </div>
              </li>
            </ul>
          </div>
          <p v-else class="empty">Belum ada riwayat pesanan.</p>
        </template>
      </section>

      <!-- Edit menu → link to proper seller page -->
      <section v-else aria-label="Edit menu" class="flex flex-col items-center justify-center py-16 gap-3 text-center">
        <p class="font-semibold">Kelola Menu</p>
        <p class="text-sm" style="color:var(--wwh-muted)">Untuk mengelola menu secara lengkap, gunakan halaman Kelola Menu.</p>
        <RouterLink
          to="/seller/menus"
          class="submit"
          style="display:inline-block;text-decoration:none;padding:9px 28px"
        >
          Kelola Menu →
        </RouterLink>
      </section>

      <div class="snav-space" aria-hidden="true"></div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  getSellerOrders, getOrderDetail,
  verifyPayment, rejectPayment, startProcessing, markReady, completeOrder, cancelOrder,
  getHistory,
} from '@/lib/api'
import { ApiError, type OrderListItem, type OrderDetailResponse, type HistoryResponse } from '@/types/api'

const emit = defineEmits<{ toast: [msg: string] }>()

const authStore = useAuthStore()
const token = computed(() => authStore.accessToken ?? '')

// ── Icons ────────────────────────────────────────────────────────────────────
const TAB_ICONS = {
  orders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/></svg>',
  history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/></svg>',
}

const STATUS_LABEL: Record<string, string> = {
  awaiting_payment: 'Menunggu Pembayaran',
  waiting_processing: 'Pesanan Dibuat',
  processing: 'Sedang Diproses',
  ready: 'Siap Disajikan',
  completed: 'Selesai',
  cancelled: 'Dibatalkan',
}

// ── State ─────────────────────────────────────────────────────────────────────
const tab = ref<'orders' | 'history' | 'edit'>('orders')

const orders = ref<OrderListItem[]>([])
const loadingOrders = ref(false)
const ordersError = ref<string | null>(null)
const acting = ref<string | null>(null)

const detail = ref<OrderDetailResponse | null>(null)
const rejectTarget = ref<OrderListItem | null>(null)
const cancelTarget = ref<OrderListItem | null>(null)
const rejectReason = ref('')
const cancelReason = ref('')

const history = ref<HistoryResponse>({
  data: [], total: 0, page: 1, page_size: 20,
  total_revenue: '0', completed_count: 0, cancelled_count: 0,
})
const loadingHistory = ref(false)
const historyError = ref<string | null>(null)

// ── Computed ─────────────────────────────────────────────────────────────────
const activeCount = computed(() =>
  orders.value.filter(o =>
    ['awaiting_payment', 'waiting_processing', 'processing', 'ready'].includes(o.order_status)
  ).length
)

const tabs = computed(() => [
  { id: 'orders', label: 'Pemesanan', icon: TAB_ICONS.orders, n: activeCount.value },
  { id: 'history', label: 'History', icon: TAB_ICONS.history, n: 0 },
  { id: 'edit', label: 'Edit', icon: TAB_ICONS.edit, n: 0 },
])

const detailGroups = computed(() => {
  if (!detail.value) return []
  return ['Makanan', 'Minuman']
    .map(t => ({
      label: t.toUpperCase(),
      items: detail.value!.items.filter(i => i.menu_type === t),
    }))
    .filter(g => g.items.length > 0)
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function rp(n: number | string) {
  const num = typeof n === 'string' ? parseFloat(n) : n
  return 'Rp ' + num.toLocaleString('id-ID')
}

function fmtDate(t: string) {
  return t ? new Date(t).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-'
}

function say(msg: string) {
  emit('toast', msg)
}

// ── Load orders ───────────────────────────────────────────────────────────────
async function loadOrders() {
  if (!authStore.isLoggedIn || document.hidden) return
  loadingOrders.value = true
  ordersError.value = null
  try {
    orders.value = await getSellerOrders(token.value)
  } catch (e) {
    ordersError.value = e instanceof ApiError ? e.message : 'Gagal memuat pesanan.'
  } finally {
    loadingOrders.value = false
  }
}

async function loadHistory() {
  if (!authStore.isLoggedIn) return
  loadingHistory.value = true
  historyError.value = null
  try {
    history.value = await getHistory({ page: 1, page_size: 20 }, token.value)
  } catch (e) {
    historyError.value = e instanceof ApiError ? e.message : 'Gagal memuat riwayat.'
  } finally {
    loadingHistory.value = false
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────
async function openDetail(orderNumber: string) {
  try {
    detail.value = await getOrderDetail(orderNumber, token.value)
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal memuat detail.')
  }
}

async function doVerify(o: OrderListItem) {
  acting.value = o.order_number
  try {
    await verifyPayment(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Pembayaran dikonfirmasi`)
    loadOrders()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal verifikasi.')
  } finally {
    acting.value = null
  }
}

function openReject(o: OrderListItem) { rejectTarget.value = o; rejectReason.value = '' }
function openCancel(o: OrderListItem) { cancelTarget.value = o; cancelReason.value = '' }

async function doReject() {
  if (!rejectTarget.value) return
  const target = rejectTarget.value
  acting.value = target.order_number
  try {
    await rejectPayment(target.order_number, rejectReason.value.trim() || null, token.value)
    say(`Pesanan ${target.order_number}: Pembayaran ditolak`)
    rejectTarget.value = null
    loadOrders()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal menolak.')
  } finally {
    acting.value = null
  }
}

async function doStart(o: OrderListItem) {
  acting.value = o.order_number
  try {
    await startProcessing(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Sedang Diproses`)
    loadOrders()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal memulai.')
  } finally {
    acting.value = null
  }
}

async function doMarkReady(o: OrderListItem) {
  acting.value = o.order_number
  try {
    await markReady(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Siap Disajikan`)
    loadOrders()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal menandai siap.')
  } finally {
    acting.value = null
  }
}

async function doComplete(o: OrderListItem) {
  acting.value = o.order_number
  try {
    await completeOrder(o.order_number, token.value)
    say(`Pesanan ${o.order_number}: Selesai`)
    loadOrders()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal menyelesaikan.')
  } finally {
    acting.value = null
  }
}

async function doCancel() {
  if (!cancelTarget.value) return
  const target = cancelTarget.value
  acting.value = target.order_number
  try {
    await cancelOrder(target.order_number, cancelReason.value.trim() || null, token.value)
    say(`Pesanan ${target.order_number}: Dibatalkan`)
    cancelTarget.value = null
    loadOrders()
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal membatalkan.')
  } finally {
    acting.value = null
  }
}

// ── Watch tab changes ─────────────────────────────────────────────────────────
watch(tab, (newTab) => {
  if (newTab === 'orders') loadOrders()
  else if (newTab === 'history') loadHistory()
})

// ── Polling ───────────────────────────────────────────────────────────────────
let pollInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  if (authStore.isLoggedIn) {
    loadOrders()
    pollInterval = setInterval(loadOrders, 8_000)
  }
})

onUnmounted(() => {
  if (pollInterval !== null) clearInterval(pollInterval)
})
</script>
