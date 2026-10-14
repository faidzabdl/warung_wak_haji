<template>
  <section aria-label="Edit menu">
    <!-- Top bar: filters + tambah button -->
    <div class="ed-bar">
      <div class="ed-filters">
        <!-- Type filter -->
        <div class="dd" :class="{ open: typeOpen }" ref="typeRef">
          <button class="dd-btn solid" type="button" @click="typeOpen = !typeOpen" aria-haspopup="listbox">
            {{ filterType === 'Semua' ? 'Semua menu' : filterType }}<i class="caret"></i>
          </button>
          <ul v-if="typeOpen" class="dd-menu" role="listbox">
            <li
              v-for="t in ['Semua', 'Makanan', 'Minuman']"
              :key="t"
              role="option"
              :class="{ on: filterType === t }"
              @click="pickType(t)"
            >{{ t }}</li>
          </ul>
        </div>
        <!-- Category filter -->
        <div class="dd" :class="{ open: catOpen }" ref="catRef">
          <button class="dd-btn" type="button" @click="catOpen = !catOpen" aria-haspopup="listbox">
            {{ filterCat === 'Semua' ? 'Kategori' : filterCat }}<i class="caret"></i>
          </button>
          <ul v-if="catOpen" class="dd-menu" role="listbox">
            <li
              v-for="c in cats"
              :key="c"
              role="option"
              :class="{ on: filterCat === c }"
              @click="pickCat(c)"
            >{{ c }}</li>
          </ul>
        </div>
      </div>
      <button class="submit" type="button" @click="openCreate">+ Tambah Menu</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="menu-grid">
      <div v-for="i in 6" :key="i" class="wwh-card" style="min-height:200px;opacity:.4"></div>
    </div>

    <p v-else-if="loadError" class="empty" style="color:var(--line)">{{ loadError }}</p>

    <!-- Menu grid -->
    <div v-else class="menu-grid">
      <article
        v-for="m in filteredMenus"
        :key="m.id"
        class="wwh-card"
        :class="{ off: !m.is_available }"
      >
        <!-- Thumbnail -->
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

        <!-- Availability toggle -->
        <button
          class="sw"
          type="button"
          role="switch"
          :aria-checked="m.is_available"
          :disabled="togglingId === m.id"
          @click="toggleAvailability(m)"
        >
          <i></i>
          <span>{{ m.is_available ? 'Tersedia' : 'Habis' }}</span>
        </button>

        <!-- Edit / Delete buttons -->
        <div class="oc-actions">
          <button class="act main" type="button" @click="openEdit(m)">Edit</button>
          <button class="act" type="button" @click="confirmDelete(m)">
            {{ deleteId === m.id ? 'Yakin?' : 'Hapus' }}
          </button>
        </div>
      </article>

      <p v-if="filteredMenus.length === 0" class="empty">Belum ada menu.</p>
    </div>

    <!-- Create / Edit modal -->
    <div v-if="draft" class="ov" @mousedown.self="closeDraft">
      <div class="modal" role="dialog" aria-modal="true" tabindex="-1" @keydown.escape="closeDraft">
        <button class="x" type="button" aria-label="Tutup" @click="closeDraft">×</button>
        <h3 class="m-title">{{ draft.id ? 'Edit Menu' : 'Tambah Menu' }}</h3>

        <div class="mf">
          <label for="f-name">Nama menu</label>
          <input id="f-name" v-model="draft.name" maxlength="40" placeholder="Typing.." />
        </div>
        <div class="mf">
          <label for="f-price">Harga (Rp)</label>
          <input id="f-price" v-model="draft.price" inputmode="numeric" placeholder="Typing.." />
        </div>
        <div class="mf">
          <label for="f-desc">Deskripsi (opsional)</label>
          <input id="f-desc" v-model="draft.description" maxlength="100" placeholder="Opsional.." />
        </div>
        <div class="mf">
          <span>Jenis</span>
          <div class="chips">
            <button
              v-for="t in ['Makanan', 'Minuman']"
              :key="t"
              type="button"
              class="chip"
              :class="{ on: draft.menu_type === t }"
              @click="draft.menu_type = t"
            >{{ t }}</button>
          </div>
        </div>
        <div class="mf">
          <label for="f-cat">Kategori</label>
          <input
            id="f-cat"
            v-model="draft.category"
            list="cat-list"
            maxlength="20"
            placeholder="mis. Nasi, Ayam"
          />
          <datalist id="cat-list">
            <option v-for="c in allCats" :key="c" :value="c"></option>
          </datalist>
        </div>
        <div class="mf">
          <span>Tersedia</span>
          <div class="chips">
            <button type="button" class="chip" :class="{ on: draft.is_available }" @click="draft.is_available = true">Ya</button>
            <button type="button" class="chip" :class="{ on: !draft.is_available }" @click="draft.is_available = false">Habis</button>
          </div>
        </div>

        <p v-if="draftError" class="err-msg" style="margin:0">{{ draftError }}</p>

        <div class="m-foot">
          <button class="btn-ghost" type="button" :disabled="saving" @click="closeDraft">Batal</button>
          <button class="btn-main" type="button" :disabled="saving" @click="saveDraft">
            {{ saving ? 'Menyimpan…' : 'Simpan' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <transition name="t">
      <div v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</div>
    </transition>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getSellerMenus, createMenu, updateMenu, setMenuAvailability, deleteMenu } from '@/lib/api'
import { ApiError, type MenuResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const token = computed(() => authStore.accessToken ?? '')

// ── State ─────────────────────────────────────────────────────────────────────
const menus = ref<MenuResponse[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const togglingId = ref<string | null>(null)
const deleteId = ref<string | null>(null)
let deleteTimer: ReturnType<typeof setTimeout> | null = null

const filterType = ref('Semua')
const filterCat = ref('Semua')
const typeOpen = ref(false)
const catOpen = ref(false)
const typeRef = ref<HTMLElement | null>(null)
const catRef = ref<HTMLElement | null>(null)

const draft = ref<null | {
  id: string | null
  name: string
  price: string
  description: string
  menu_type: string
  category: string
  is_available: boolean
  image_url: string | null
}>(null)
const draftError = ref('')
const saving = ref(false)
const toastMsg = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

// ── Computed ─────────────────────────────────────────────────────────────────
const cats = computed(() => {
  const s = new Set<string>()
  menus.value
    .filter(m => filterType.value === 'Semua' || m.menu_type === filterType.value)
    .forEach(m => s.add(m.category))
  return ['Semua', ...Array.from(s)]
})

const allCats = computed(() => [...new Set(menus.value.map(m => m.category))])

const filteredMenus = computed(() =>
  menus.value.filter(m =>
    (filterType.value === 'Semua' || m.menu_type === filterType.value) &&
    (filterCat.value === 'Semua' || m.category === filterCat.value)
  )
)

watch(cats, (newCats) => {
  if (!newCats.includes(filterCat.value)) filterCat.value = 'Semua'
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function rp(n: number | string) {
  const num = typeof n === 'string' ? parseFloat(n) : n
  return 'Rp ' + num.toLocaleString('id-ID')
}

function say(msg: string) {
  toastMsg.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, 3600)
}

// ── Dropdown close on outside click ─────────────────────────────────────────
function handleOutsideClick(e: MouseEvent) {
  if (typeRef.value && !typeRef.value.contains(e.target as Node)) typeOpen.value = false
  if (catRef.value && !catRef.value.contains(e.target as Node)) catOpen.value = false
}
function handleEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') { typeOpen.value = false; catOpen.value = false }
}
onMounted(() => {
  document.addEventListener('click', handleOutsideClick)
  document.addEventListener('keydown', handleEsc)
  loadMenus()
})
onBeforeUnmount(() => {
  document.removeEventListener('click', handleOutsideClick)
  document.removeEventListener('keydown', handleEsc)
})

function pickType(t: string) { filterType.value = t; filterCat.value = 'Semua'; typeOpen.value = false }
function pickCat(c: string) { filterCat.value = c; catOpen.value = false }

// ── Load ─────────────────────────────────────────────────────────────────────
async function loadMenus() {
  loading.value = true
  loadError.value = null
  try {
    menus.value = await getSellerMenus(token.value)
  } catch (e) {
    loadError.value = e instanceof ApiError ? e.message : 'Gagal memuat menu.'
  } finally {
    loading.value = false
  }
}

// ── Availability toggle ───────────────────────────────────────────────────────
async function toggleAvailability(m: MenuResponse) {
  togglingId.value = m.id
  const prev = m.is_available
  m.is_available = !prev
  try {
    const updated = await setMenuAvailability(m.id, m.is_available, token.value)
    const idx = menus.value.findIndex(x => x.id === m.id)
    if (idx >= 0) menus.value[idx] = updated
    say(`Menu "${m.name}" kini ${updated.is_available ? 'tersedia' : 'habis'}`)
  } catch (e) {
    m.is_available = prev
    say(e instanceof ApiError ? e.message : 'Gagal mengubah ketersediaan.')
  } finally {
    togglingId.value = null
  }
}

// ── Delete (two-step) ─────────────────────────────────────────────────────────
function confirmDelete(m: MenuResponse) {
  if (deleteId.value !== m.id) {
    deleteId.value = m.id
    if (deleteTimer) clearTimeout(deleteTimer)
    deleteTimer = setTimeout(() => { deleteId.value = null }, 3000)
    return
  }
  doDelete(m)
}

async function doDelete(m: MenuResponse) {
  deleteId.value = null
  try {
    await deleteMenu(m.id, token.value)
    menus.value = menus.value.filter(x => x.id !== m.id)
    say(`Menu "${m.name}" dihapus.`)
  } catch (e) {
    say(e instanceof ApiError ? e.message : 'Gagal menghapus menu.')
  }
}

// ── Draft modal ───────────────────────────────────────────────────────────────
function openCreate() {
  draftError.value = ''
  draft.value = { id: null, name: '', price: '', description: '', menu_type: 'Makanan', category: '', is_available: true, image_url: null }
}

function openEdit(m: MenuResponse) {
  draftError.value = ''
  draft.value = {
    id: m.id,
    name: m.name,
    price: String(m.price),
    description: m.description ?? '',
    menu_type: m.menu_type,
    category: m.category,
    is_available: m.is_available,
    image_url: m.image_url,
  }
}

function closeDraft() {
  if (!saving.value) draft.value = null
}

async function saveDraft() {
  if (!draft.value) return
  const d = draft.value
  const price = Math.round(Number(String(d.price).replace(/\D/g, '')))
  if (!d.name.trim()) { draftError.value = 'Nama menu wajib diisi.'; return }
  if (!(price > 0)) { draftError.value = 'Harga harus berupa angka lebih dari 0.'; return }
  draftError.value = ''
  saving.value = true
  try {
    const body = {
      name: d.name.trim(),
      price,
      description: d.description.trim() || null,
      menu_type: d.menu_type,
      category: (d.category.trim() || 'Umum'),
      is_available: d.is_available,
      image_url: d.image_url,
    }
    if (d.id) {
      const updated = await updateMenu(d.id, body, token.value)
      const idx = menus.value.findIndex(m => m.id === d.id)
      if (idx >= 0) menus.value[idx] = updated
      say(`Menu "${updated.name}" berhasil diperbarui.`)
    } else {
      const created = await createMenu({ ...body, is_active: true }, token.value)
      menus.value.unshift(created)
      say(`Menu "${created.name}" berhasil ditambahkan.`)
    }
    draft.value = null
  } catch (e) {
    draftError.value = e instanceof ApiError ? e.message : 'Gagal menyimpan menu.'
  } finally {
    saving.value = false
  }
}
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
