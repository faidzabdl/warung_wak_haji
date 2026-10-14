<template>
  <div class="ov" @mousedown.self="$emit('close')">
    <div
      class="modal bare"
      role="dialog"
      aria-modal="true"
      aria-label="Detail Pesanan"
      tabindex="-1"
      ref="box"
      @keydown.escape="$emit('close')"
    >
      <!-- Header -->
      <div class="dt-head">
        <p>Nama Pemesan: <strong>{{ order.buyer_name }}</strong></p>
        <p>No. Meja: <strong>{{ order.table_number }}</strong></p>
        <p v-if="order.notes" style="font-size:.8rem;color:var(--wwh-muted);margin-top:4px">Catatan: {{ order.notes }}</p>
        <p v-if="order.cancel_reason" style="font-size:.8rem;color:var(--line);margin-top:4px">Alasan Batal: {{ order.cancel_reason }}</p>
      </div>

      <!-- Items grouped by menu_type -->
      <div
        v-for="(g, i) in groups"
        :key="g.label"
        class="dt-grid"
      >
        <span class="dt-lab">{{ g.label }}</span>
        <span class="dt-lab">{{ i === 0 ? 'QTY' : '' }}</span>
        <span class="dt-lab">{{ i === 0 ? 'HARGA' : '' }}</span>
        <template v-for="item in g.items" :key="item.name + item.qty">
          <span class="dt-name">{{ item.name }}</span>
          <span class="dt-qty">{{ item.qty }}</span>
          <span class="dt-price">{{ rp(item.subtotal) }}</span>
        </template>
      </div>

      <!-- Total -->
      <div class="dt-total">
        <span>TOTAL</span>
        <span></span>
        <span>{{ rp(order.total_amount) }}</span>
      </div>

      <!-- Footer -->
      <div class="m-foot" style="justify-content:center;margin-top:20px">
        <button class="dt-close" type="button" @click="$emit('close')">TUTUP</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import type { OrderDetailResponse } from '@/types/api'

const props = defineProps<{ order: OrderDetailResponse }>()
defineEmits<{ close: [] }>()

const box = ref<HTMLElement | null>(null)

onMounted(() => {
  document.body.style.overflow = 'hidden'
  box.value?.focus()
})
onBeforeUnmount(() => {
  document.body.style.overflow = ''
})

function rp(n: number | string) {
  const num = typeof n === 'string' ? parseFloat(n) : n
  return 'Rp ' + num.toLocaleString('id-ID')
}

const groups = computed(() =>
  ['Makanan', 'Minuman']
    .map(t => ({
      label: t.toUpperCase(),
      items: props.order.items.filter(i => i.menu_type === t),
    }))
    .filter(g => g.items.length > 0)
)
</script>
