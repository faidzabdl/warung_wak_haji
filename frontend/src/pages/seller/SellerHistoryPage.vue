<template>
  <section aria-label="Riwayat pesanan">
    <!-- Summary stats -->
    <div class="stats">
      <div class="stat wide"><span>Total Pendapatan</span><b>{{ rp(result.total_revenue) }}</b></div>
      <div class="stat"><span>Selesai</span><b>{{ result.completed_count }}</b></div>
      <div class="stat"><span>Dibatalkan</span><b>{{ result.cancelled_count }}</b></div>
    </div>

    <!-- Filters -->
    <div style="display:flex;flex-wrap:wrap;gap:14px;margin-bottom:18px;align-items:flex-end">
      <div>
        <label style="font-size:.76rem;font-weight:600;display:block;margin-bottom:4px">Status</label>
        <select
          v-model="filters.status"
          class="dd-btn"
          style="min-width:120px;height:36px"
          @change="goPage(1)"
        >
          <option value="">Semua</option>
          <option value="completed">Selesai</option>
          <option value="cancelled">Dibatalkan</option>
        </select>
      </div>
      <div>
        <label style="font-size:.76rem;font-weight:600;display:block;margin-bottom:4px">Dari</label>
        <input
          type="date"
          v-model="filters.date_from"
          class="dd-btn"
          style="height:36px"
          @change="goPage(1)"
        />
      </div>
      <div>
        <label style="font-size:.76rem;font-weight:600;display:block;margin-bottom:4px">Sampai</label>
        <input
          type="date"
          v-model="filters.date_to"
          class="dd-btn"
          style="height:36px"
          @change="goPage(1)"
        />
      </div>
      <button class="act" type="button" style="height:36px;flex:none" @click="resetFilters">Reset</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="hist" style="gap:12px">
      <li v-for="i in 5" :key="i" style="min-height:60px;opacity:.4;border-radius:20px;border:1.5px solid var(--line);background:var(--card)"></li>
    </div>

    <p v-else-if="error" class="empty" style="color:var(--line)">{{ error }}</p>

    <template v-else>
      <p v-if="result.data.length === 0" class="empty">Belum ada riwayat pesanan.</p>

      <template v-else>
        <!-- History list -->
        <div class="hist-top">
          <strong style="font-size:.9rem">Riwayat Pesanan ({{ result.total }})</strong>
        </div>
        <ul class="hist">
          <li
            v-for="o in result.data"
            :key="o.order_number"
            :class="o.order_status"
            style="cursor:pointer"
            @click="expanded = expanded === o.order_number ? null : o.order_number"
          >
            <div class="h-main">
              <b>Meja {{ o.table_number }} · {{ o.buyer_name }}</b>
              <p>{{ o.items.map(i => i.name + ' ×' + i.qty).join(', ') }}</p>
              <p>{{ o.order_number }} · {{ fmtDate(o.created_at) }} · {{ o.payment_method === 'qris' ? 'QRIS' : 'Tunai' }}</p>
              <!-- Expanded detail -->
              <div v-if="expanded === o.order_number" style="margin-top:8px;padding-top:8px;border-top:1px dashed var(--wwh-muted)">
                <div
                  v-for="(item, i) in o.items"
                  :key="i"
                  style="display:flex;justify-content:space-between;font-size:.75rem;padding:2px 0"
                >
                  <span>{{ item.name }} × {{ item.qty }}</span>
                  <span>{{ rp(item.subtotal) }}</span>
                </div>
                <p v-if="o.cancel_reason" style="font-size:.72rem;color:var(--line);margin-top:4px">
                  Alasan: {{ o.cancel_reason }}
                </p>
              </div>
            </div>
            <div class="h-side">
              <b>{{ rp(o.total_amount) }}</b>
              <span class="badge">{{ STATUS_LABEL[o.order_status] ?? o.order_status }}</span>
            </div>
          </li>
        </ul>

        <!-- Pagination -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;font-size:.82rem">
          <span style="color:var(--wwh-muted)">{{ result.total }} pesanan</span>
          <div style="display:flex;gap:8px">
            <button class="act" type="button" :disabled="page === 1" @click="goPage(page - 1)">← Sebelumnya</button>
            <span style="padding:6px 8px">Hal. {{ page }}</span>
            <button class="act" type="button" :disabled="page * pageSize >= result.total" @click="goPage(page + 1)">Berikutnya →</button>
          </div>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { getHistory } from '@/lib/api'
import { ApiError, type HistoryResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const token = computed(() => authStore.accessToken ?? '')

const STATUS_LABEL: Record<string, string> = {
  completed: 'Selesai',
  cancelled: 'Dibatalkan',
}

const pageSize = 20
const page = ref(1)
const filters = reactive({ status: '', date_from: '', date_to: '' })
const expanded = ref<string | null>(null)

const result = ref<HistoryResponse>({
  data: [], total: 0, page: 1, page_size: pageSize,
  total_revenue: '0', completed_count: 0, cancelled_count: 0,
})
const loading = ref(false)
const error = ref<string | null>(null)

function rp(n: number | string) {
  const num = typeof n === 'string' ? parseFloat(n) : n
  return 'Rp ' + num.toLocaleString('id-ID')
}

function fmtDate(t: string) {
  return t ? new Date(t).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-'
}

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

function goPage(p: number) { page.value = p; load() }

function resetFilters() {
  filters.status = ''
  filters.date_from = ''
  filters.date_to = ''
  goPage(1)
}

onMounted(load)
</script>
