<template>
  <div>
    <NavBar />
    <main class="max-w-5xl mx-auto px-4 py-6">
      <h1 class="text-2xl font-bold mb-6">Menu Kami</h1>

      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        <Skeleton v-for="i in 6" :key="i" class="h-48 rounded-xl" />
      </div>

      <div v-else-if="error" class="text-destructive">{{ error }}</div>

      <div v-else-if="menus.length === 0" class="text-muted-foreground">
        Belum ada menu tersedia.
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        <div
          v-for="menu in menus"
          :key="menu.id"
          class="border rounded-xl overflow-hidden flex flex-col"
        >
          <img
            v-if="menu.image_url"
            :src="menu.image_url"
            :alt="menu.name"
            class="w-full h-36 object-cover"
          />
          <div v-else class="w-full h-36 bg-muted flex items-center justify-center text-muted-foreground text-sm">
            Tidak ada gambar
          </div>
          <div class="p-3 flex flex-col flex-1">
            <div class="flex items-start justify-between gap-2">
              <RouterLink :to="`/menu/${menu.id}`" class="font-semibold hover:underline leading-tight">
                {{ menu.name }}
              </RouterLink>
              <span
                class="text-xs px-1.5 py-0.5 rounded-full shrink-0"
                :class="menu.is_available ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
              >
                {{ menu.is_available ? 'Tersedia' : 'Habis' }}
              </span>
            </div>
            <p v-if="menu.description" class="text-sm text-muted-foreground mt-1 flex-1">
              {{ menu.description }}
            </p>
            <div class="flex items-center justify-between mt-3">
              <span class="font-bold">{{ formatRupiah(menu.price) }}</span>
              <Button
                size="sm"
                :disabled="!menu.is_available"
                @click="addToCart(menu)"
              >
                Tambah
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import { getMenus } from '@/lib/api'
import type { MenuResponse } from '@/types/api'
import { useCartStore } from '@/stores/cart'
import { formatRupiah } from '@/utils/format'
import NavBar from '@/components/NavBar.vue'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Toaster } from '@/components/ui/sonner'

const menus = ref<MenuResponse[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const cart = useCartStore()

onMounted(async () => {
  try {
    menus.value = await getMenus()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Gagal memuat menu'
  } finally {
    loading.value = false
  }
})

function addToCart(menu: MenuResponse) {
  cart.addItem(menu)
  toast.success(`${menu.name} ditambahkan ke keranjang`)
}
</script>
