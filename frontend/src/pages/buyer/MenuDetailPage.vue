<template>
  <div>
    <NavBar />
    <main class="max-w-2xl mx-auto px-4 py-6">
      <RouterLink to="/" class="text-sm text-muted-foreground hover:underline">← Kembali ke Menu</RouterLink>

      <div v-if="loading" class="mt-6">
        <Skeleton class="h-64 w-full rounded-xl" />
        <Skeleton class="h-8 w-48 mt-4" />
        <Skeleton class="h-4 w-full mt-2" />
      </div>

      <div v-else-if="error" class="mt-6 text-destructive">{{ error }}</div>

      <div v-else-if="menu" class="mt-6">
        <img
          v-if="menu.image_url"
          :src="menu.image_url"
          :alt="menu.name"
          class="w-full h-64 object-cover rounded-xl"
        />
        <div v-else class="w-full h-64 bg-muted rounded-xl flex items-center justify-center text-muted-foreground">
          Tidak ada gambar
        </div>

        <div class="mt-4">
          <div class="flex items-start justify-between gap-2">
            <h1 class="text-2xl font-bold">{{ menu.name }}</h1>
            <span
              class="text-xs px-2 py-1 rounded-full"
              :class="menu.is_available ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
            >
              {{ menu.is_available ? 'Tersedia' : 'Habis' }}
            </span>
          </div>
          <p class="text-2xl font-bold text-primary mt-1">{{ formatRupiah(menu.price) }}</p>
          <p v-if="menu.description" class="mt-3 text-muted-foreground">{{ menu.description }}</p>

          <div class="mt-6 flex items-center gap-4">
            <div class="flex items-center border rounded-lg overflow-hidden">
              <button
                class="px-3 py-2 hover:bg-muted text-lg"
                @click="qty = Math.max(1, qty - 1)"
              >−</button>
              <span class="px-4 py-2 font-medium">{{ qty }}</span>
              <button
                class="px-3 py-2 hover:bg-muted text-lg"
                @click="qty++"
              >+</button>
            </div>
            <Button
              class="flex-1"
              :disabled="!menu.is_available"
              @click="addToCart"
            >
              Tambah ke Keranjang
            </Button>
          </div>

          <div v-if="!menu.is_available" class="mt-3 text-sm text-destructive">
            Menu ini sedang tidak tersedia.
          </div>
        </div>
      </div>
    </main>
    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from 'vue-sonner'
import { getMenuDetail } from '@/lib/api'
import type { MenuResponse } from '@/types/api'
import { useCartStore } from '@/stores/cart'
import { formatRupiah } from '@/utils/format'
import NavBar from '@/components/NavBar.vue'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Toaster } from '@/components/ui/sonner'

const route = useRoute()
const cart = useCartStore()
const menu = ref<MenuResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const qty = ref(1)

onMounted(async () => {
  try {
    menu.value = await getMenuDetail(route.params.id as string)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Menu tidak ditemukan'
  } finally {
    loading.value = false
  }
})

function addToCart() {
  if (!menu.value) return
  cart.addItem(menu.value, qty.value)
  toast.success(`${menu.value.name} × ${qty.value} ditambahkan ke keranjang`)
}
</script>
