<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
      <div class="flex items-start justify-between mb-4">
        <div>
          <h2 class="font-bold text-lg">{{ order.order_number }}</h2>
          <p class="text-sm text-muted-foreground">{{ formatDate(order.created_at) }}</p>
        </div>
        <button class="text-muted-foreground hover:text-foreground" @click="$emit('close')">✕</button>
      </div>

      <div class="space-y-4">
        <!-- Status -->
        <div class="flex gap-2 flex-wrap">
          <StatusBadge :status="order.order_status" type="order" />
          <StatusBadge :status="order.payment_status" type="payment" />
        </div>

        <!-- Buyer info -->
        <div class="text-sm space-y-1">
          <p>Nama Pembeli: <strong>{{ order.buyer_name }}</strong></p>
          <p v-if="order.notes">Catatan: {{ order.notes }}</p>
          <p v-if="order.cancel_reason" class="text-destructive">Alasan Batal: {{ order.cancel_reason }}</p>
          <p v-if="order.reject_reason" class="text-destructive">Alasan Tolak: {{ order.reject_reason }}</p>
        </div>

        <!-- Items -->
        <div>
          <h3 class="font-semibold text-sm mb-2">Item Pesanan</h3>
          <div class="border rounded">
            <div
              v-for="(item, i) in order.items"
              :key="i"
              class="flex justify-between text-sm px-3 py-2 border-b last:border-0"
            >
              <span>{{ item.menu_name }} × {{ item.quantity }}</span>
              <span>{{ formatRupiah(item.subtotal) }}</span>
            </div>
          </div>
          <div class="flex justify-between font-bold text-sm mt-2">
            <span>Total</span>
            <span>{{ formatRupiah(order.total_amount) }}</span>
          </div>
        </div>

        <!-- Payment proof -->
        <div v-if="order.payment_proof_url">
          <h3 class="font-semibold text-sm mb-2">Bukti Pembayaran</h3>
          <img
            :src="order.payment_proof_url"
            alt="Bukti Pembayaran"
            class="max-h-64 rounded border cursor-pointer"
            @click="openProof"
          />
          <p class="text-xs text-muted-foreground mt-1">Klik untuk membuka di tab baru. Link berlaku 1 jam.</p>
        </div>
        <div v-else-if="order.payment_status !== 'pending_payment'" class="text-sm text-muted-foreground">
          Bukti pembayaran belum diunggah.
        </div>
      </div>

      <div class="mt-6 flex justify-end">
        <Button variant="outline" @click="$emit('close')">Tutup</Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrderDetailResponse } from '@/types/api'
import { formatRupiah, formatDate } from '@/utils/format'
import StatusBadge from '@/components/buyer/StatusBadge.vue'
import { Button } from '@/components/ui/button'

const props = defineProps<{ order: OrderDetailResponse }>()
defineEmits<{ close: [] }>()

function openProof() {
  if (props.order.payment_proof_url) window.open(props.order.payment_proof_url, '_blank')
}
</script>
