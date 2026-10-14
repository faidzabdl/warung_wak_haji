<template>
  <nav class="border-b bg-white px-4 py-3 flex items-center justify-between sticky top-0 z-20 shadow-sm">
    <RouterLink to="/" class="font-semibold text-lg">🍽️ Warung Wak Haji</RouterLink>
    <div class="flex items-center gap-4 text-sm">
      <RouterLink to="/track" class="hover:underline text-muted-foreground">Lacak Pesanan</RouterLink>
      <RouterLink to="/checkout" class="hover:underline font-medium">
        Keranjang
        <span v-if="cart.totalItems > 0" class="ml-1 bg-primary text-primary-foreground text-xs rounded-full px-1.5 py-0.5">
          {{ cart.totalItems }}
        </span>
      </RouterLink>
      <RouterLink to="/seller/login" class="hover:underline text-muted-foreground">Penjual</RouterLink>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useCartStore } from '@/stores/cart'
const cart = useCartStore()
</script>
