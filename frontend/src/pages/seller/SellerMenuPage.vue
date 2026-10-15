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

        <!-- Foto menu -->
        <div class="mf">
          <span>Foto Menu</span>
          <div class="img-upload" @click="triggerFileInput" :class="{ uploading: uploadingImg }">
            <img v-if="draft.image_url" :src="draft.image_url" alt="Preview foto" class="img-preview" />
            <div v-else class="img-placeholder">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              <span>{{ uploadingImg ? 'Mengupload…' : 'Tambah Foto' }}</span>
            </div>
            <div v-if="draft.image_url" class="img-change-label">Ganti Foto</div>
          </div>
          <input ref="fileInputRef" type="file" accept="image/jpeg,image/png,image/webp" style="display:none" @change="onFileChange" />
          <p v-if="uploadError" class="err-msg" style="margin:4px 0 0">{{ uploadError }}</p>
        </div>

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
          <div class="dd" :class="{ open: catDraftOpen }" style="position:relative">
            <button
              id="f-cat"
              class="dd-btn"
              type="button"
              style="width:100%"
              @click="catDraftOpen = !catDraftOpen; addingCat = false; newCatInput = ''"
              aria-haspopup="listbox"
            >
              {{ draft.category || 'Pilih kategori…' }}<i class="caret"></i>
            </button>
            <ul v-if="catDraftOpen" class="dd-menu" role="listbox" style="width:100%">
              <li
                v-for="c in draftCatOptions"
                :key="c"
                role="option"
                class="cat-option"
                :class="{ on: draft.category === c }"
                @click="draft.category = c; catDraftOpen = false; addingCat = false"
              >
                <span class="cat-label">{{ c }}</span>
                <!-- Hapus kategori hanya saat Tambah Menu (bukan Edit) -->
                <button
                  v-if="!draft.id && !isDefaultCat(draft.menu_type, c)"
                  type="button"
                  class="cat-del"
                  title="Hapus kategori"
                  @click.stop="deleteCategory(draft.menu_type, c)"
                >×</button>
              </li>
              <!-- Tambah kategori hanya saat Tambah Menu (bukan Edit) -->
              <template v-if="!draft.id">
                <li v-if="!addingCat" role="option" class="add-cat-btn" @click.stop="addingCat = true">
                  + Tambah Kategori
                </li>
                <li v-else role="option" class="add-cat-input-row" @click.stop>
                  <input
                    v-model="newCatInput"
                    class="add-cat-input"
                    placeholder="Nama kategori baru…"
                    maxlength="40"
                    @keydown.enter.prevent="saveNewCat"
                    @keydown.escape.prevent="addingCat = false; newCatInput = ''"
                  />
                  <button type="button" class="add-cat-ok" @click.stop="saveNewCat">OK</button>
                </li>
              </template>
            </ul>
          </div>
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
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getSellerMenus, createMenu, updateMenu, setMenuAvailability, deleteMenu, uploadMenuImage } from '@/lib/api'
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
const catDraftOpen = ref(false)
const uploadingImg = ref(false)
const uploadError = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const toastMsg = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

// ── Computed ─────────────────────────────────────────────────────────────────
// reactive agar kategori baru yang ditambah user langsung muncul di filter & dropdown
const DEFAULT_CATS: Record<string, string[]> = {
  Makanan: ['Main Dish', 'Side Dish'],
  Minuman: ['Coffee', 'Non Coffee'],
}
const CATS_BY_TYPE = reactive<Record<string, string[]>>({
  Makanan: ['Main Dish', 'Side Dish'],
  Minuman: ['Coffee', 'Non Coffee'],
})

const addingCat = ref(false)
const newCatInput = ref('')

const cats = computed(() => {
  if (filterType.value === 'Semua') {
    const all = new Set([...CATS_BY_TYPE.Makanan, ...CATS_BY_TYPE.Minuman])
    return ['Semua', ...all]
  }
  return ['Semua', ...(CATS_BY_TYPE[filterType.value] ?? [])]
})

const draftCatOptions = computed(() =>
  draft.value ? (CATS_BY_TYPE[draft.value.menu_type] ?? []) : []
)


const filteredMenus = computed(() =>
  menus.value.filter(m =>
    (filterType.value === 'Semua' || m.menu_type === filterType.value) &&
    (filterCat.value === 'Semua' || m.category === filterCat.value)
  )
)

watch(cats, (newCats) => {
  if (!newCats.includes(filterCat.value)) filterCat.value = 'Semua'
})

// Reset kategori & tutup dropdown saat jenis menu berubah di form
watch(() => draft.value?.menu_type, () => {
  if (draft.value) draft.value.category = ''
  catDraftOpen.value = false
  addingCat.value = false
  newCatInput.value = ''
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

// ── Image upload ──────────────────────────────────────────────────────────────
function triggerFileInput() {
  if (!uploadingImg.value) fileInputRef.value?.click()
}

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file || !draft.value) return
  uploadError.value = ''
  uploadingImg.value = true
  try {
    const res = await uploadMenuImage(file, token.value)
    draft.value.image_url = res.image_url
  } catch (err) {
    uploadError.value = err instanceof ApiError ? err.message : 'Gagal mengupload foto.'
  } finally {
    uploadingImg.value = false
    // reset input agar file yang sama bisa dipilih lagi
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
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
  addingCat.value = false
  newCatInput.value = ''
  draft.value = { id: null, name: '', price: '', description: '', menu_type: 'Makanan', category: '', is_available: true, image_url: null }
}

function openEdit(m: MenuResponse) {
  draftError.value = ''
  addingCat.value = false
  newCatInput.value = ''
  // pastikan kategori existing menu ada di daftar agar muncul di dropdown
  if (m.category && m.menu_type) {
    if (!CATS_BY_TYPE[m.menu_type]) CATS_BY_TYPE[m.menu_type] = []
    if (!CATS_BY_TYPE[m.menu_type].includes(m.category)) {
      CATS_BY_TYPE[m.menu_type].push(m.category)
    }
  }
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
  if (!saving.value) {
    draft.value = null
    addingCat.value = false
    newCatInput.value = ''
  }
}

function isDefaultCat(type: string, cat: string) {
  return (DEFAULT_CATS[type] ?? []).includes(cat)
}

function deleteCategory(type: string, cat: string) {
  const list = CATS_BY_TYPE[type]
  if (!list) return
  CATS_BY_TYPE[type] = list.filter(c => c !== cat)
  // jika kategori yang dihapus sedang dipilih, reset
  if (draft.value && draft.value.category === cat) {
    draft.value.category = ''
  }
}

function saveNewCat() {
  const cat = newCatInput.value.trim()
  if (!cat || !draft.value) return
  const type = draft.value.menu_type
  if (!CATS_BY_TYPE[type]) CATS_BY_TYPE[type] = []
  // hindari duplikat (case-insensitive)
  if (!CATS_BY_TYPE[type].some(c => c.toLowerCase() === cat.toLowerCase())) {
    CATS_BY_TYPE[type].push(cat)
  }
  draft.value.category = CATS_BY_TYPE[type].find(c => c.toLowerCase() === cat.toLowerCase()) ?? cat
  catDraftOpen.value = false
  addingCat.value = false
  newCatInput.value = ''
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

/* ── Image upload ── */
.img-upload {
  width: 100%;
  height: 140px;
  border: 2px dashed var(--line);
  border-radius: 12px;
  cursor: pointer;
  overflow: hidden;
  position: relative;
  transition: border-color .2s;
}
.img-upload:hover { border-color: var(--brand); }
.img-upload.uploading { opacity: .6; cursor: wait; }
.img-preview {
  width: 100%; height: 100%;
  object-fit: cover; display: block;
}
.img-placeholder {
  width: 100%; height: 100%;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 8px; color: var(--wwh-muted);
  font-size: .8rem;
}
.img-change-label {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: rgba(0,0,0,.5);
  color: #fff; font-size: .75rem; font-weight: 600;
  text-align: center; padding: 5px 0;
}

/* ── Tambah kategori baru ── */
.add-cat-btn {
  color: var(--brand);
  font-size: .82rem;
  font-weight: 600;
  border-top: 1px solid var(--line);
  margin-top: 2px;
  padding-top: 8px !important;
}
.add-cat-btn:hover { background: var(--surface); }
.add-cat-input-row {
  display: flex !important;
  gap: 6px;
  padding: 6px 8px !important;
  border-top: 1px solid var(--line);
  cursor: default;
}
.add-cat-input {
  flex: 1;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 5px 8px;
  font-size: .82rem;
  background: var(--bg);
  color: var(--ink);
  outline: none;
}
.add-cat-input:focus { border-color: var(--brand); }
.add-cat-ok {
  padding: 5px 12px;
  border-radius: 8px;
  background: var(--brand);
  color: #fff;
  font-size: .82rem;
  font-weight: 600;
  border: none;
  cursor: pointer;
  white-space: nowrap;
}
.add-cat-ok:hover { opacity: .85; }

/* ── Item kategori dengan tombol hapus ── */
.cat-option {
  display: flex !important;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}
.cat-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-del {
  flex-shrink: 0;
  width: 18px; height: 18px;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 4px;
  background: transparent;
  color: var(--wwh-muted);
  font-size: .85rem; line-height: 1;
  cursor: pointer;
  padding: 0;
  opacity: 0;
  transition: opacity .15s, background .15s, color .15s;
}
.cat-option:hover .cat-del { opacity: 1; }
.cat-del:hover { background: #fee2e2; color: #dc2626; }
</style>
