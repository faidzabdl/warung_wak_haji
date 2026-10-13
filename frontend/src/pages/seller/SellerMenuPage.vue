<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold">Kelola Menu</h1>
      <Button @click="showCreate = !showCreate">
        {{ showCreate ? 'Batal' : '+ Tambah Menu' }}
      </Button>
    </div>

    <!-- Create panel (inline) -->
    <MenuCreatePanel
      v-if="showCreate"
      :token="token"
      @created="onCreated"
      @cancel="showCreate = false"
    />

    <!-- Edit panel (inline, per row) -->
    <MenuEditPanel
      v-if="editingMenu"
      :menu="editingMenu"
      :token="token"
      @updated="onUpdated"
      @cancel="editingMenu = null"
    />

    <!-- Loading -->
    <div v-if="loading" class="space-y-2 mt-4">
      <Skeleton v-for="i in 4" :key="i" class="h-12 rounded" />
    </div>

    <div v-else-if="error" class="text-destructive text-sm">{{ error }}</div>

    <!-- Menu table -->
    <div v-else class="mt-4 border rounded-lg overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-muted/40">
          <tr>
            <th class="text-left px-4 py-2">Nama</th>
            <th class="text-left px-4 py-2">Harga</th>
            <th class="text-left px-4 py-2">Tersedia</th>
            <th class="text-left px-4 py-2">Status</th>
            <th class="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="menu in menus"
            :key="menu.id"
            class="border-t hover:bg-muted/20"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <img v-if="menu.image_url" :src="menu.image_url" alt="" class="w-8 h-8 rounded object-cover" />
                <div>
                  <p class="font-medium">{{ menu.name }}</p>
                  <p v-if="menu.description" class="text-xs text-muted-foreground truncate max-w-xs">{{ menu.description }}</p>
                </div>
              </div>
            </td>
            <td class="px-4 py-3">{{ formatRupiah(menu.price) }}</td>
            <td class="px-4 py-3">
              <button
                class="text-xs px-2 py-1 rounded border"
                :class="menu.is_available ? 'bg-green-50 text-green-700 border-green-300' : 'bg-red-50 text-red-700 border-red-300'"
                :disabled="togglingId === menu.id"
                @click="toggleAvailability(menu)"
              >
                {{ menu.is_available ? 'Tersedia' : 'Habis' }}
              </button>
            </td>
            <td class="px-4 py-3">
              <span
                class="text-xs px-1.5 py-0.5 rounded-full"
                :class="menu.is_active ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'"
              >
                {{ menu.is_active ? 'Aktif' : 'Nonaktif' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right">
              <Button size="sm" variant="outline" @click="startEdit(menu)">Edit</Button>
            </td>
          </tr>
          <tr v-if="menus.length === 0">
            <td colspan="5" class="px-4 py-6 text-center text-muted-foreground">Belum ada menu.</td>
          </tr>
        </tbody>
      </table>
    </div>
    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { toast } from 'vue-sonner'
import { getSellerMenus, setMenuAvailability } from '@/lib/api'
import { ApiError, type MenuResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'
import { formatRupiah } from '@/utils/format'
import MenuCreatePanel from '@/components/seller/MenuCreatePanel.vue'
import MenuEditPanel from '@/components/seller/MenuEditPanel.vue'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Toaster } from '@/components/ui/sonner'

const authStore = useAuthStore()
const token = computed(() => authStore.accessToken ?? '')

const menus = ref<MenuResponse[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const showCreate = ref(false)
const editingMenu = ref<MenuResponse | null>(null)
const togglingId = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    menus.value = await getSellerMenus(token.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Gagal memuat menu.'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function startEdit(menu: MenuResponse) {
  editingMenu.value = menu
  showCreate.value = false
}

function onCreated() {
  showCreate.value = false
  toast.success('Menu berhasil dibuat!')
  load()
}

function onUpdated(updated: MenuResponse) {
  editingMenu.value = null
  toast.success('Menu berhasil diperbarui!')
  const idx = menus.value.findIndex(m => m.id === updated.id)
  if (idx >= 0) menus.value[idx] = updated
}

async function toggleAvailability(menu: MenuResponse) {
  togglingId.value = menu.id
  const prev = menu.is_available
  menu.is_available = !prev // optimistic
  try {
    const updated = await setMenuAvailability(menu.id, menu.is_available, token.value)
    const idx = menus.value.findIndex(m => m.id === menu.id)
    if (idx >= 0) menus.value[idx] = updated
    toast.success(`Menu ${updated.is_available ? 'tersedia' : 'habis'}`)
  } catch (e) {
    menu.is_available = prev // revert
    toast.error(e instanceof ApiError ? e.message : 'Gagal mengubah ketersediaan.')
  } finally {
    togglingId.value = null
  }
}
</script>
