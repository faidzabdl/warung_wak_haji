<template>
  <main class="wrap">
    <!-- Role switch -->
    <div class="roles" role="tablist" aria-label="Mode tampilan">
      <button
        v-for="r in ROLES" :key="r.id" type="button" role="tab"
        :class="{ on: role === r.id }"
        :aria-selected="role === r.id"
        @click="role = (r.id as 'pembeli' | 'penjual')"
      >
        {{ r.label }}
        <i v-if="r.id === 'penjual' && pendingCount > 0" class="cnt">{{ pendingCount }}</i>
      </button>
    </div>

    <!-- ── BUYER VIEW ──────────────────────────────────────────────────────── -->
    <template v-if="role === 'pembeli'">
      <!-- Header -->
      <header>
        <div class="top">
          <div class="logo" aria-hidden="true">🍽️</div>
          <h1 class="brand">Warung Wak Haji</h1>
        </div>
        <div class="hero">
          <h2>Welcome To Our Restaurant</h2>
          <p>Sajian Lezat Dengan Cita Rasa Istimewa<br>Siap Menemani Setiap Momenmu</p>
        </div>
      </header>

      <!-- Filters -->
      <div class="filters">
        <!-- Type dropdown -->
        <div class="dd" :class="{ open: typeOpen }" ref="typeRef">
          <button class="dd-btn solid" type="button" @click="typeOpen = !typeOpen" aria-haspopup="listbox">
            {{ activeType }}<i class="caret"></i>
          </button>
          <ul v-if="typeOpen" class="dd-menu" role="listbox">
            <li v-for="t in TYPES" :key="t" role="option" :class="{ on: activeType === t }"
              @click="pickType(t)">{{ t }}</li>
          </ul>
        </div>
        <!-- Cat dropdown -->
        <div class="dd" :class="{ open: catOpen }" ref="catRef">
          <button class="dd-btn" type="button" @click="catOpen = !catOpen" aria-haspopup="listbox">
            {{ activeCat === 'Semua' ? 'Kategori' : activeCat }}<i class="caret"></i>
          </button>
          <ul v-if="catOpen" class="dd-menu" role="listbox">
            <li v-for="c in cats" :key="c" role="option" :class="{ on: activeCat === c }"
              @click="pickCat(c)">{{ c }}</li>
          </ul>
        </div>
      </div>

      <!-- Loading skeleton -->
      <div v-if="loading" class="menu-grid">
        <div v-for="i in 8" :key="i" class="wwh-card" style="min-height:220px;opacity:.5"></div>
      </div>
      <div v-else-if="loadError" class="empty" style="grid-column:1/-1">{{ loadError }}</div>

      <!-- Menu grid -->
      <div v-else class="menu-grid">
        <article
          v-for="m in filteredMenus" :key="m.id"
          class="wwh-card"
          :class="{ off: !m.is_available }"
        >
          <div class="thumb" aria-hidden="true">
            <img v-if="m.image_url" :src="m.image_url" :alt="m.name" />
            <svg v-else viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
              <circle cx="32" cy="36" r="18"/><circle cx="32" cy="36" r="10"/>
              <path d="M8 8v16M13 8v16M8 16h5M56 8c-5 3-6 10-6 16h6z"/>
            </svg>
          </div>
          <h3 class="item-name">{{ m.name }}</h3>
          <p class="item-price">{{ rp(m.price) }}</p>
          <p class="item-cat">{{ m.menu_type }} · {{ m.category }}</p>
          <!-- Habis -->
          <button v-if="!m.is_available" class="pesan" type="button" disabled>HABIS</button>
          <!-- Belum di keranjang -->
          <button v-else-if="!cart[m.id]" class="pesan" type="button" @click="addItem(m)">PESAN</button>
          <!-- Sudah di keranjang -->
          <div v-else class="step">
            <button type="button" aria-label="Kurangi" @click="removeItem(m)">−</button>
            <span>{{ cart[m.id] }}</span>
            <button type="button" aria-label="Tambah" @click="addItem(m)">+</button>
          </div>
        </article>
        <p v-if="!filteredMenus.length" class="empty">Menu belum tersedia.</p>
      </div>

      <!-- Order status (inline, muncul setelah pesan berhasil) -->
      <section
        v-if="lastOrder"
        class="status-box"
        :class="lastOrder.order_status"
        role="status"
      >
        <div>
          <span class="badge">{{ statusLabel(lastOrder.order_status) }}</span>
          <strong>Pesanan {{ lastOrder.order_number }}</strong>
        </div>
        <p>Meja {{ lastOrder.table_number }} · {{ lastOrder.item_count }} item · {{ rp(lastOrder.total_amount) }} · {{ lastOrder.payment_method === 'qris' ? 'QRIS' : 'Tunai' }}</p>
        <p class="s-note">{{ statusNote(lastOrder.order_status) }}</p>
        <button class="link-btn" type="button" @click="lastOrder = null">Tutup</button>
      </section>

      <!-- Order form -->
      <section class="order-form" aria-label="Data pemesan">
        <p class="order-sum">{{ totalItems ? totalItems + ' item dipilih · ' + rp(cartTotal) : 'Belum ada menu dipilih' }}</p>

        <div class="field" :class="{ err: tried && !nama.trim() }">
          <label for="nama">Nama Pemesan:</label>
          <input id="nama" v-model="nama" placeholder="masukkan nama..." autocomplete="name" @keyup.enter="submitForm" />
        </div>
        <p v-if="tried && !nama.trim()" class="err-msg">Nama wajib diisi.</p>

        <div class="field" :class="{ err: tried && !mejaValid }">
          <label for="meja">No. Meja:</label>
          <input id="meja" v-model="meja" placeholder="masukkan nomor meja" inputmode="numeric" @keyup.enter="submitForm" />
        </div>
        <p v-if="tried && !mejaValid" class="err-msg">Isi dengan nomor meja (angka).</p>

        <!-- Payment options -->
        <fieldset class="pay">
          <legend>Metode Pembayaran:</legend>
          <div class="pay-grid" role="radiogroup">
            <label v-for="p in PAYMENTS" :key="p.id" class="opt" :class="{ on: payMethod === p.id }">
              <input type="radio" name="pay" :value="p.id" :checked="payMethod === p.id" @change="payMethod = p.id" />
              <span class="ic" v-html="p.icon"></span>
              <span class="dot"></span>
              <b class="opt-label">{{ p.label }}</b>
              <small class="opt-desc">{{ p.desc }}</small>
            </label>
          </div>
          <p v-if="tried && !payMethod" class="err-msg" style="margin-left:0">Pilih metode pembayaran.</p>
        </fieldset>

        <div class="form-actions">
          <button class="submit" type="button" :disabled="busy" @click="submitForm">
            {{ busy ? 'Memproses…' : 'Submit' }}
          </button>
        </div>
      </section>
    </template>

    <!-- ── SELLER VIEW ─────────────────────────────────────────────────────── -->
    <SellerApp v-else @toast="showToast" />

    <!-- Payment modal (QRIS atau konfirmasi Cash) -->
    <div v-if="draft" class="ov" @mousedown.self="closeDraft">
      <div class="modal" role="dialog" aria-modal="true" tabindex="-1" @keydown.escape="closeDraft">
        <button class="x" type="button" aria-label="Tutup" @click="closeDraft">×</button>

        <h3 class="m-title">
          {{ draft.payment_method === 'qris' ? 'Pembayaran QRIS' : 'Konfirmasi Pesanan' }}
        </h3>

        <!-- QRIS -->
        <template v-if="draft.payment_method === 'qris'">
          <div class="qr-box"><QrDummy :seed="qrSeed" /></div>
          <p class="qr-total">{{ rp(draft.total) }}</p>
          <p class="qr-merch">Merchant: Warung Wak Haji · Meja {{ draft.meja }}</p>
          <ol class="qr-steps">
            <li>Buka aplikasi e-wallet atau m-banking Anda.</li>
            <li>Pilih menu <b>Scan / QRIS</b> lalu pindai kode di atas.</li>
            <li>Pastikan nama merchant dan nominal sudah sesuai.</li>
            <li>Selesaikan pembayaran, lalu tekan <b>Saya Sudah Bayar</b>.</li>
          </ol>
          <p class="note">Kasir akan memverifikasi pembayaran QRIS Anda. Simpan nomor pesanan untuk tracking.</p>
        </template>

        <!-- Cash -->
        <template v-else>
          <div class="meta">
            <div><span>No. Meja</span><b>{{ draft.meja }}</b></div>
            <div><span>Pemesan</span><b>{{ draft.nama }}</b></div>
          </div>
          <ul class="lines">
            <li v-for="l in draft.lines" :key="l.id">
              <span>{{ l.name }} × {{ l.qty }}</span>
              <span>{{ rp(l.subtotal) }}</span>
            </li>
          </ul>
          <div class="total-row"><span>Total</span><span>{{ rp(draft.total) }}</span></div>
          <p class="note">Pembayaran dilakukan langsung kepada kasir setelah pesanan dikonfirmasi.</p>
        </template>

        <div class="m-foot">
          <button class="btn-ghost" type="button" :disabled="busy" @click="closeDraft">
            {{ draft.payment_method === 'qris' ? 'Batal' : 'Kembali' }}
          </button>
          <button class="btn-main" type="button" :disabled="busy" @click="confirmOrder">
            {{ busy ? 'Memproses…' : (draft.payment_method === 'qris' ? 'Saya Sudah Bayar' : 'Konfirmasi Pesanan') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <transition name="t">
      <div v-if="toast" class="toast" :class="{ 'toast-lift': role === 'penjual' }" role="status">
        {{ toast }}
      </div>
    </transition>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { createOrder } from '@/lib/api'
import { getMenus } from '@/lib/api'
import { ApiError, type MenuResponse } from '@/types/api'
import SellerApp from '@/components/seller/SellerApp.vue'
import QrDummy from '@/components/buyer/QrDummy.vue'

// ── Data ──────────────────────────────────────────────────────────────────
const TYPES = ['Makanan', 'Minuman']
const PAYMENTS = [
  { id: 'qris', label: 'QRIS', desc: 'Scan dengan e-wallet atau m-banking',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h3M20 17v4"/></svg>' },
  { id: 'cash', label: 'Cash (Tunai)', desc: 'Bayar langsung ke kasir',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 10v.01M18 14v.01"/></svg>' },
]
const ROLES = [{ id: 'pembeli', label: 'Pembeli' }, { id: 'penjual', label: 'Penjual' }]
const STATUS_INFO: Record<string, { label: string; note: string }> = {
  awaiting_payment: { label: 'Menunggu Pembayaran', note: 'Pembayaran QRIS belum diverifikasi. Status akan berubah setelah kasir memastikan dana masuk.' },
  waiting_processing: { label: 'Pesanan Dibuat', note: 'Pembayaran dilakukan secara tunai langsung kepada kasir atau petugas.' },
  processing: { label: 'Sedang Diproses', note: 'Pesanan Anda sedang disiapkan oleh dapur.' },
  ready: { label: 'Siap Disajikan', note: 'Pesanan siap dan segera diantar ke meja Anda.' },
  completed: { label: 'Selesai', note: 'Pesanan selesai. Terima kasih sudah makan di Warung Wak Haji!' },
  cancelled: { label: 'Dibatalkan', note: 'Pesanan dibatalkan oleh penjual. Silakan hubungi kasir.' },
}

// ── State ─────────────────────────────────────────────────────────────────
const role = ref<'pembeli' | 'penjual'>('pembeli')
const menus = ref<MenuResponse[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

// Filters
const activeType = ref('Makanan')
const activeCat = ref('Semua')
const typeOpen = ref(false)
const catOpen = ref(false)
const typeRef = ref<HTMLElement | null>(null)
const catRef = ref<HTMLElement | null>(null)

// Cart: { menuId: qty }
const cart = ref<Record<string, number>>({})

// Form
const nama = ref('')
const meja = ref('')
const payMethod = ref<string>('')
const tried = ref(false)
const busy = ref(false)
const draft = ref<null | { nama: string; meja: string; payment_method: string; lines: any[]; total: number }>(null)
const lastOrder = ref<any>(null)
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

// Seller pending count (imported from SellerApp via provide/inject or just 0 for now)
const pendingCount = ref(0)

// ── Computed ──────────────────────────────────────────────────────────────
const cats = computed(() => {
  const s = new Set<string>()
  menus.value.filter(m => m.menu_type === activeType.value).forEach(m => s.add(m.category))
  return ['Semua', ...Array.from(s)]
})

const filteredMenus = computed(() =>
  menus.value.filter(m =>
    m.menu_type === activeType.value &&
    (activeCat.value === 'Semua' || m.category === activeCat.value)
  )
)

const totalItems = computed(() => Object.values(cart.value).reduce((a, b) => a + b, 0))
const cartTotal = computed(() =>
  menus.value.reduce((s, m) => s + (cart.value[m.id] || 0) * parseFloat(m.price), 0)
)
const mejaValid = computed(() => /^\d{1,4}$/.test(meja.value.trim()))
const lines = computed(() =>
  menus.value
    .filter(m => cart.value[m.id])
    .map(m => ({ id: m.id, name: m.name, qty: cart.value[m.id], subtotal: parseFloat(m.price) * cart.value[m.id] }))
)
const qrSeed = computed(() => draft.value ? draft.value.nama + draft.value.meja + draft.value.total : 'wwh')

// ── Helpers ───────────────────────────────────────────────────────────────
function rp(n: number | string) {
  const num = typeof n === 'string' ? parseFloat(n) : n
  return 'Rp ' + num.toLocaleString('id-ID')
}
function statusLabel(s: string) { return STATUS_INFO[s]?.label ?? s }
function statusNote(s: string)  { return STATUS_INFO[s]?.note ?? '' }

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 3600)
}

// ── Dropdown close on outside click ──────────────────────────────────────
function handleOutsideClick(e: MouseEvent) {
  if (typeRef.value && !typeRef.value.contains(e.target as Node)) typeOpen.value = false
  if (catRef.value  && !catRef.value.contains(e.target as Node))  catOpen.value = false
}
function handleEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') { typeOpen.value = false; catOpen.value = false }
}
onMounted(() => {
  document.addEventListener('click', handleOutsideClick)
  document.addEventListener('keydown', handleEsc)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', handleOutsideClick)
  document.removeEventListener('keydown', handleEsc)
})

// ── Watch cats to reset cat filter when type changes ──────────────────────
watch(cats, (newCats) => { if (!newCats.includes(activeCat.value)) activeCat.value = 'Semua' })

// ── Filter pickers ────────────────────────────────────────────────────────
function pickType(t: string) { activeType.value = t; activeCat.value = 'Semua'; typeOpen.value = false }
function pickCat(c: string)  { activeCat.value = c; catOpen.value = false }

// ── Cart ──────────────────────────────────────────────────────────────────
function addItem(m: MenuResponse) {
  cart.value = { ...cart.value, [m.id]: (cart.value[m.id] || 0) + 1 }
}
function removeItem(m: MenuResponse) {
  const c = { ...cart.value }
  if (c[m.id] > 1) c[m.id]--
  else delete c[m.id]
  cart.value = c
}

// ── Form submit → open modal ──────────────────────────────────────────────
function submitForm() {
  tried.value = true
  if (!totalItems.value) { showToast('Pilih minimal satu menu dulu ya.'); return }
  if (!nama.value.trim() || !mejaValid.value || !payMethod.value) return
  draft.value = {
    nama: nama.value.trim(),
    meja: meja.value.trim(),
    payment_method: payMethod.value,
    lines: lines.value,
    total: cartTotal.value,
  }
}

function closeDraft() { if (!busy.value) draft.value = null }

// ── Confirm order → POST to backend ──────────────────────────────────────
async function confirmOrder() {
  if (!draft.value) return
  busy.value = true
  const savedDraft = draft.value
  try {
    const { data, status } = await createOrder({
      buyer_name: savedDraft.nama,
      table_number: savedDraft.meja,
      payment_method: savedDraft.payment_method as 'qris' | 'cash',
      items: lines.value.map(l => ({ menu_id: l.id, quantity: l.qty })),
    })

    draft.value = null
    cart.value = {}
    nama.value = ''
    meja.value = ''
    payMethod.value = ''
    tried.value = false

    if (status === 201) {
      const res = data as any
      lastOrder.value = {
        order_number: res.order_number,
        table_number: savedDraft.meja,
        item_count: lines.value.reduce((s, l) => s + l.qty, 0),
        total_amount: res.total_amount,
        payment_method: savedDraft.payment_method,
        order_status: savedDraft.payment_method === 'qris' ? 'awaiting_payment' : 'waiting_processing',
      }
      showToast(
        lastOrder.value.payment_method === 'cash'
          ? `Pesanan berhasil dibuat! Pembayaran tunai ke kasir untuk meja ${lastOrder.value.table_number}.`
          : 'Menunggu pembayaran. Kasir akan memverifikasi QRIS Anda.'
      )
    }
  } catch (e) {
    if (e instanceof ApiError) {
      showToast(`Error: [${e.code}] ${e.message}`)
    } else {
      showToast('Terjadi kendala. Silakan coba lagi.')
    }
  } finally {
    busy.value = false
  }
}

// ── Load menus ────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    menus.value = await getMenus()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Gagal memuat menu'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.t-enter-active, .t-leave-active { transition: opacity .25s, transform .25s; }
.t-enter-from, .t-leave-to { opacity: 0; transform: translate(-50%, 10px); }
.toast { position: fixed; z-index: 60; left: 50%; bottom: calc(20px + env(safe-area-inset-bottom,0px)); transform: translateX(-50%); max-width: calc(100% - 32px); background: var(--toast-bg); color: var(--toast-ink); padding: 12px 18px; border-radius: 12px; font-size: .85rem; font-weight: 500; box-shadow: 0 8px 24px rgba(0,0,0,.3); text-align: center; }
</style>
