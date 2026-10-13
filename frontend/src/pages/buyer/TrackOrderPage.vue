<template>
  <div>
    <NavBar />
    <main class="max-w-2xl mx-auto px-4 py-6">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-bold">Status Pesanan</h1>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          {{ loading ? 'Memuat...' : 'Refresh' }}
        </Button>
      </div>

      <div v-if="loading && !order">
        <Skeleton class="h-8 w-48 mb-4" />
        <Skeleton class="h-4 w-full mb-2" />
        <Skeleton class="h-4 w-3/4" />
      </div>

      <div v-else-if="error" class="p-4 border border-destructive rounded-lg text-destructive text-sm">
        {{ error }}
      </div>

      <template v-else-if="order">
        <!-- Header -->
        <div class="border rounded-lg p-4 mb-4 space-y-2">
          <div class="flex items-center justify-between">
            <span class="font-semibold">{{ order.order_number }}</span>
            <span class="text-sm text-muted-foreground">{{ formatDate(order.created_at) }}</span>
          </div>
          <p class="text-sm">Pemesan: <strong>{{ order.buyer_name }}</strong></p>
          <div class="flex gap-2 flex-wrap">
            <StatusBadge :status="order.order_status" type="order" />
            <StatusBadge :status="order.payment_status" type="payment" />
          </div>
          <p v-if="order.notes" class="text-sm text-muted-foreground">Catatan: {{ order.notes }}</p>
        </div>

        <!-- Items -->
        <div class="border rounded-lg p-4 mb-4">
          <h2 class="font-semibold mb-3">Item Pesanan</h2>
          <div class="space-y-1">
            <div
              v-for="(item, i) in order.items"
              :key="i"
              class="flex justify-between text-sm"
            >
              <span>{{ item.menu_name }} × {{ item.quantity }}</span>
              <span>{{ formatRupiah(item.subtotal) }}</span>
            </div>
          </div>
          <div class="flex justify-between font-bold border-t mt-3 pt-3">
            <span>Total</span>
            <span>{{ formatRupiah(order.total_amount) }}</span>
          </div>
        </div>

        <!-- Upload proof link (only when pending payment) -->
        <div v-if="order.payment_status === 'pending_payment'" class="border rounded-lg p-4 bg-yellow-50">
          <p class="text-sm font-medium mb-2">Belum ada bukti pembayaran yang diunggah.</p>
          <RouterLink
            :to="`/order/${order.order_number}/proof`"
            class="text-sm text-primary underline"
          >Upload Bukti Pembayaran →</RouterLink>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { trackOrder } from '@/lib/api'
import type { OrderTrackResponse } from '@/types/api'
import { ApiError } from '@/types/api'
import { formatRupiah, formatDate } from '@/utils/format'
import NavBar from '@/components/NavBar.vue'
import StatusBadge from '@/components/buyer/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

const route = useRoute()
const token = route.params.token as string

const order = ref<OrderTrackResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    order.value = await trackOrder(token)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      error.value = 'Token tidak valid atau pesanan tidak ditemukan.'
    } else if (e instanceof ApiError && e.status === 429) {
      error.value = 'Terlalu banyak permintaan. Tunggu sebentar lalu refresh.'
    } else {
      error.value = e instanceof Error ? e.message : 'Gagal memuat status pesanan.'
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
