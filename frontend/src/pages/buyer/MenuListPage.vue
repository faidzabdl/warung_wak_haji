<template>
  <main class="wrap wrap-flush">
    <!-- ── BUYER VIEW ──────────────────────────────────────────────────────── -->
    <template v-if="role === 'pembeli'">
      <!-- Header full-bleed (flush ke tepi atas, tanpa padding wrap) -->
      <header class="hero-header">
        <!-- Foto full width -->
        <div class="hero-bg">
          <img src="@/assets/image.png" alt="Kedai Wak Haji" class="hero-img" />
          
          <!-- Logo bulatan pojok kiri atas -->
          <div class="hero-logo" aria-hidden="true">
            <img
              src="@/assets/logo.jpeg"
              alt=""
              width="104"
              height="104"
              loading="lazy"
              decoding="async"
            />
          </div>
          <h1 class="hero-title">Kedai Wak Haji</h1>
        </div>
        <!-- Bar coklat KEDAI WAK HAJI tepat di bawah foto -->
        
        <!-- Tagline -->
        <div class="hero-tagline">
          <p>"Menghadirkan Cita Rasa Klasik<br>Menyimpan Cerita di Setiap Sajian"</p>
        </div>
      </header>

      <!-- Konten dengan padding -->
      <div class="inner">

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
        <p v-if="tried && !mejaValid" class="err-msg">Nomor meja harus angka 1–8.</p>

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

      </div><!-- /inner -->
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

    <!-- Toggle role (always visible when logged in) -->
    <div v-if="authStore.isLoggedIn" class="hero-roles hero-roles-float" role="tablist" aria-label="Mode tampilan">
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
import { createOrder, trackOrder, getMenus } from '@/lib/api'
import { ApiError, type MenuResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'
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
const authStore = useAuthStore()
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
let lastOrderToken = ''
let pollTimer: ReturnType<typeof setInterval> | null = null
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

// Seller pending count (imported from SellerApp via provide/inject or just 0 for now)
const pendingCount = ref(0)

// ── Computed ──────────────────────────────────────────────────────────────
const CATS_BY_TYPE: Record<string, string[]> = {
  Makanan: ['Main Dish', 'Side Dish'],
  Minuman: ['Coffee', 'Non Coffee'],
}

const cats = computed(() => ['Semua', ...(CATS_BY_TYPE[activeType.value] ?? [])])


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
const mejaValid = computed(() => /^[1-8]$/.test(meja.value.trim()))
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
      lastOrderToken = res.tracking_token
      lastOrder.value = {
        order_number: res.order_number,
        table_number: savedDraft.meja,
        item_count: lines.value.reduce((s, l) => s + l.qty, 0),
        total_amount: res.total_amount,
        payment_method: savedDraft.payment_method,
        order_status: savedDraft.payment_method === 'qris' ? 'awaiting_payment' : 'waiting_processing',
      }
      startStatusPoll()
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

// ── Poll status lastOrder ─────────────────────────────────────────────────
function startStatusPoll() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!lastOrderToken || document.hidden) return
    try {
      const track = await trackOrder(lastOrderToken)
      if (lastOrder.value) lastOrder.value.order_status = track.order_status
      if (track.order_status === 'completed' || track.order_status === 'cancelled') {
        clearInterval(pollTimer!)
        pollTimer = null
      }
    } catch { /* silent */ }
  }, 5_000)
}

// ── Load menus ────────────────────────────────────────────────────────────
onMounted(async () => {
  // Init auth session agar toggle Pembeli/Penjual muncul jika sudah login
  if (authStore.loading) await authStore.init()
  try {
    menus.value = await getMenus()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Gagal memuat menu'
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.t-enter-active, .t-leave-active { transition: opacity .25s, transform .25s; }
.t-enter-from, .t-leave-to { opacity: 0; transform: translate(-50%, 10px); }
.toast { position: fixed; z-index: 60; left: 50%; bottom: calc(20px + env(safe-area-inset-bottom,0px)); transform: translateX(-50%); max-width: calc(100% - 32px); background: var(--toast-bg); color: var(--toast-ink); padding: 12px 18px; border-radius: 12px; font-size: .85rem; font-weight: 500; box-shadow: 0 8px 24px rgba(0,0,0,.3); text-align: center; }

/* ── Konten bawah header ── */
.inner { padding: 0 18px; }

/* ── Toggle role pojok kanan atas foto ── */
.hero-roles {
  position: absolute;
  top: 10px; right: 10px;
  display: flex;
   background: rgba(63,42,26,.55);   /* sebelumnya rgba(255,255,255,.18) */
  backdrop-filter: blur(6px);
  border-radius: 999px;
  padding: 3px;
  gap: 2px;
  z-index: 2;
}
.hero-roles button {
  border: none; background: transparent;
  color: #fff; font-size: .78rem; font-weight: 600;
  padding: 5px 14px; border-radius: 999px;
  cursor: pointer; transition: background .15s, color .15s;
}
.hero-roles button.on { background: var(--brand-dark); color: #fff; }

/* ── Toggle float: fixed di atas seller view ── */
.hero-roles-float {
  position: fixed;
  top: 10px; right: 10px;
  z-index: 50;
}

/* ── Hero Header ── */
.hero-header {
  /* full viewport width, break keluar dari max-width wrap */
  position: relative;
  left: 50%; right: 50%;
  margin-left: -50vw;
  margin-right: -50vw;
  width: 100vw;
}
.hero-bg {
  position: relative;
  width: 100%;
  height: clamp(190px, 38vw, 420px);   /* layar lebar tidak terlalu gepeng */
  overflow: hidden;
  border-bottom: 8px solid #3f2a1a;
}
.hero-img {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  max-width: none;                      /* cegah batas lebar bawaan Tailwind */
  object-fit: cover;
  object-position: center 40%;
  display: block;
}
.hero-logo {
  position: absolute; top: 12px; left: 14px;
  width: clamp(64px, 17vw, 104px);
  aspect-ratio: 1;
  border-radius: 50%;
  background: #fff;                 /* menyatu dengan background putih logo */
  border: 3px solid #3f2a1a;
  box-shadow: 0 2px 10px rgba(0,0,0,.35);
  overflow: hidden;
  z-index: 2;
}
.hero-logo img {
  width: 100%; height: 100%;
  max-width: none;
  object-fit: contain;              /* logo utuh, tidak terpotong */
  padding: 6px;
  display: block;
}
.hero-title {
  position: absolute; left: 0; right: 0; bottom: 6px;
  z-index: 1;
  margin: 0; padding: 0 8px;
  background: transparent;
  color: #3f2a1a;
  font-family: 'Sansita Swashed', 'Playfair Display', Georgia, serif;
  font-size: clamp(2rem, 10.5vw, 4.6rem);
  font-weight: 800;
  font-style: normal;
  white-space: nowrap;
  text-align: center;
  line-height: 1;
  /* outline krem supaya tetap terbaca di atas foto tanpa overlay */
  text-shadow:
    -2px -2px 0 #e6d4a9, 2px -2px 0 #e6d4a9,
    -2px 2px 0 #e6d4a9, 2px 2px 0 #e6d4a9,
    0 0 12px rgba(230,212,169,.9);
}
.hero-tagline {
  background: var(--bg);
  text-align: center;
  padding: 28px 20px 28px;
  font-family: 'Cherry Swash', Georgia, serif;
  font-weight: 700;
  font-size: clamp(1.05rem, 4.4vw, 1.4rem);
  font-style: normal;
  color: #3f2a1a;
  line-height: 1.4;
}
</style>
