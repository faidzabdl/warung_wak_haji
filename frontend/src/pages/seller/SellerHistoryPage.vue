<template>
  <div>
    <h1 class="text-xl font-bold mb-6">Riwayat Pesanan</h1>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-6">
      <div>
        <Label class="text-xs">Status</Label>
        <select
          v-model="filters.status"
          class="block mt-1 border rounded px-2 py-1.5 text-sm bg-white"
          @change="goPage(1)"
        >
          <option value="">Semua</option>
          <option value="completed">Selesai</option>
          <option value="cancelled">Dibatalkan</option>
        </select>
      </div>
      <div>
        <Label class="text-xs">Dari Tanggal</Label>
        <Input type="date" v-model="filters.date_from" class="mt-1 text-sm" @change="goPage(1)" />
      </div>
      <div>
        <Label class="text-xs">Sampai Tanggal</Label>
        <Input type="date" v-model="filters.date_to" class="mt-1 text-sm" @change="goPage(1)" />
      </div>
      <div class="flex items-end">
        <Button variant="outline" size="sm" @click="resetFilters">Reset</Button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading">
      <Skeleton v-for="i in 5" :key="i" class="h-12 rounded mb-2" />
    </div>

    <div v-else-if="error" class="text-destructive text-sm">{{ error }}</div>

    <div v-else>
      <div v-if="result.data.length === 0" class="text-muted-foreground text-center py-12">
        Tidak ada riwayat pesanan.
      </div>

      <div v-else class="border rounded-lg overflow-hidden mb-4">
        <table class="w-full text-sm">
          <thead class="bg-muted/40">
            <tr>
              <th class="text-left px-3 py-2">No. Pesanan</th>
              <th class="text-left px-3 py-2">Pembeli</th>
              <th class="text-left px-3 py-2">Status</th>
              <th class="text-left px-3 py-2">Pembayaran</th>
              <th class="text-left px-3 py-2">Total</th>
              <th class="text-left px-3 py-2">Waktu</th>
              <th class="text-left px-3 py-2">Alasan</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="order in result.data" :key="order.order_number">
              <tr
                class="border-t hover:bg-muted/20 cursor-pointer"
                @click="expanded = expanded === order.order_number ? null : order.order_number"
              >
                <td class="px-3 py-3 font-mono font-medium">{{ order.order_number }}</td>
                <td class="px-3 py-3">{{ order.buyer_name }}</td>
                <td class="px-3 py-3"><StatusBadge :status="order.order_status" type="order" /></td>
                <td class="px-3 py-3"><StatusBadge :status="order.payment_status" type="payment" /></td>
                <td class="px-3 py-3">{{ formatRupiah(order.total_amount) }}</td>
                <td class="px-3 py-3 text-muted-foreground text-xs">{{ formatDate(order.created_at) }}</td>
                <td class="px-3 py-3 text-xs text-muted-foreground">
                  {{ order.cancel_reason || order.reject_reason || '—' }}
                </td>
              </tr>
              <!-- Expanded items row -->
              <tr v-if="expanded === order.order_number" class="bg-muted/10">
                <td colspan="7" class="px-4 py-3">
                  <p class="text-xs font-semibold mb-2">Item Pesanan:</p>
                  <div class="space-y-1">
                    <div
                      v-for="(item, i) in order.items"
                      :key="i"
                      class="flex justify-between text-xs"
                    >
                      <span>{{ item.menu_name }} × {{ item.quantity }}</span>
                      <span>{{ formatRupiah(item.subtotal) }}</span>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between text-sm">
        <span class="text-muted-foreground">
          {{ result.total }} pesanan
        </span>
        <div class="flex gap-2">
          <Button variant="outline" size="sm" :disabled="page === 1" @click="goPage(page - 1)">
            ← Sebelumnya
          </Button>
          <span class="px-2 py-1 text-sm">Hal. {{ page }}</span>
          <Button
            variant="outline"
            size="sm"
            :disabled="page * pageSize >= result.total"
            @click="goPage(page + 1)"
          >
            Berikutnya →
          </Button>
        </div>
      </div>
    </div>
    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { getHistory } from '@/lib/api'
import { ApiError, type HistoryResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'
import { formatRupiah, formatDate } from '@/utils/format'
import StatusBadge from '@/components/buyer/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Toaster } from '@/components/ui/sonner'

const authStore = useAuthStore()
const token = computed(() => authStore.accessToken ?? '')

const pageSize = 20
const page = ref(1)
const filters = reactive({ status: '', date_from: '', date_to: '' })
const expanded = ref<string | null>(null)

const result = ref<HistoryResponse>({ data: [], total: 0, page: 1, page_size: pageSize })
const loading = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    result.value = await getHistory({
      page: page.value,
      page_size: pageSize,
      status: filters.status || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
    }, token.value)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Gagal memuat riwayat.'
  } finally {
    loading.value = false
  }
}

function goPage(p: number) {
  page.value = p
  load()
}

function resetFilters() {
  filters.status = ''
  filters.date_from = ''
  filters.date_to = ''
  goPage(1)
}

onMounted(load)
</script>
