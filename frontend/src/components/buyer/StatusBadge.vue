<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="colorClass"
  >
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  orderStatusLabel,
  paymentStatusLabel,
  ORDER_STATUS_COLOR,
  PAYMENT_STATUS_COLOR,
} from '@/utils/format'

const props = defineProps<{
  status: string
  type: 'order' | 'payment'
}>()

const label = computed(() =>
  props.type === 'order' ? orderStatusLabel(props.status) : paymentStatusLabel(props.status)
)

const colorClass = computed(() =>
  props.type === 'order'
    ? (ORDER_STATUS_COLOR[props.status] ?? 'bg-gray-100 text-gray-700')
    : (PAYMENT_STATUS_COLOR[props.status] ?? 'bg-gray-100 text-gray-700')
)
</script>
