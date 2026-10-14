<template>
  <nav style="
    border-bottom:1.5px solid var(--line);
    background:var(--bg);
    padding:10px 16px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    position:sticky;top:0;z-index:20;
  ">
    <RouterLink to="/" style="font-weight:700;font-size:1rem;text-decoration:none;color:var(--ink)">
      🍽️ Warung Wak Haji
    </RouterLink>
    <div style="display:flex;align-items:center;gap:14px;font-size:.85rem">
      <RouterLink to="/track" style="text-decoration:none;color:var(--wwh-muted)">Lacak</RouterLink>
      <RouterLink to="/checkout" style="text-decoration:none;font-weight:600;color:var(--ink)">
        Keranjang
        <span
          v-if="cart.totalItems > 0"
          style="margin-left:4px;background:var(--brand);color:var(--on-brand);font-size:.68rem;border-radius:9px;padding:1px 6px;font-weight:800;"
        >{{ cart.totalItems }}</span>
      </RouterLink>
      <RouterLink to="/seller/login" style="text-decoration:none;color:var(--wwh-muted)">Penjual</RouterLink>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useCartStore } from '@/stores/cart'
const cart = useCartStore()
</script>
