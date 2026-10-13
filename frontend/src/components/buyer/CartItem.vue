<template>
  <div class="flex items-center justify-between py-2 border-b last:border-0">
    <div class="flex-1 min-w-0">
      <p class="font-medium truncate">{{ item.menu.name }}</p>
      <p class="text-sm text-muted-foreground">{{ formatRupiah(item.menu.price) }} / item</p>
    </div>
    <div class="flex items-center gap-2 ml-4">
      <button
        class="w-7 h-7 rounded border text-sm flex items-center justify-center hover:bg-muted"
        @click="change(-1)"
      >−</button>
      <span class="w-8 text-center text-sm font-medium">{{ item.quantity }}</span>
      <button
        class="w-7 h-7 rounded border text-sm flex items-center justify-center hover:bg-muted"
        @click="change(1)"
      >+</button>
      <span class="w-20 text-right text-sm font-medium">{{ formatRupiah(subtotal) }}</span>
      <button
        class="ml-2 text-destructive hover:underline text-sm"
        @click="cart.removeItem(item.menu.id)"
      >Hapus</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore, type CartItem } from '@/stores/cart'
import { formatRupiah } from '@/utils/format'

const props = defineProps<{ item: CartItem }>()
const cart = useCartStore()

const subtotal = computed(() => parseFloat(props.item.menu.price) * props.item.quantity)

function change(delta: number) {
  cart.updateQuantity(props.item.menu.id, props.item.quantity + delta)
}
</script>
