<template>
  <div style="min-height:100vh;background:var(--bg)">
    <!-- Top bar -->
    <header style="
      background:var(--bg);
      border-bottom:1.5px solid var(--line);
      padding:10px 18px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      position:sticky;top:0;z-index:30;
    ">
      <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:1.15rem;font-weight:800;letter-spacing:-.01em">Warung Wak Haji</span>
        <span style="font-size:.72rem;color:var(--wwh-muted);display:none" class="sm-show">Dashboard Penjual</span>
      </div>
      <div style="display:flex;align-items:center;gap:12px;font-size:.82rem">
        <span style="color:var(--wwh-muted);font-size:.72rem" class="sm-show">{{ authStore.session?.user?.email }}</span>
        <RouterLink to="/" style="font-size:.76rem;border:1.5px solid var(--brand-dark);border-radius:7px;padding:4px 10px;font-weight:600;text-decoration:none;color:var(--ink)">
          ← Pembeli
        </RouterLink>
        <button
          style="font-size:.76rem;font-weight:600;color:var(--line);background:none;border:0;cursor:pointer;padding:4px 0"
          @click="logout"
        >Keluar</button>
      </div>
    </header>

    <!-- Tab navigation (.snav) — bottom bar on mobile, top tab row on desktop -->
    <nav class="snav" role="tablist" aria-label="Menu penjual">
      <RouterLink
        v-for="link in navLinks"
        :key="link.to"
        :to="link.to"
        custom
        v-slot="{ navigate, isActive }"
      >
        <button
          type="button"
          role="tab"
          :class="{ on: isActive }"
          :aria-selected="isActive"
          @click="navigate"
        >
          <span class="ni" v-html="link.icon"></span>
          <span>{{ link.label }}</span>
          <i v-if="link.badge && link.badge > 0" class="cnt">{{ link.badge }}</i>
        </button>
      </RouterLink>
    </nav>

    <!-- Main content -->
    <main style="flex:1;padding:24px 18px 80px;max-width:1080px;margin:0 auto;width:100%">
      <router-view />
    </main>

    <!-- Bottom spacer on mobile (snav is fixed) -->
    <div class="snav-space" aria-hidden="true"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getSellerOrders } from '@/lib/api'

const authStore = useAuthStore()
const router = useRouter()

// Badge count for active orders
const activeCount = ref(0)

async function refreshBadge() {
  if (!authStore.accessToken || document.hidden) return
  try {
    const orders = await getSellerOrders(authStore.accessToken)
    activeCount.value = orders.filter(o =>
      ['awaiting_payment', 'waiting_processing', 'processing', 'ready'].includes(o.order_status)
    ).length
  } catch {
    // silently ignore
  }
}

let badgeInterval: ReturnType<typeof setInterval> | null = null
onMounted(() => { refreshBadge(); badgeInterval = setInterval(refreshBadge, 10_000) })
onUnmounted(() => { if (badgeInterval) clearInterval(badgeInterval) })

const TAB_ICONS = {
  orders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/></svg>',
  history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>',
  menus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/></svg>',
}

const navLinks = computed(() => [
  { to: '/seller/orders', label: 'Pemesanan', icon: TAB_ICONS.orders, badge: activeCount.value },
  { to: '/seller/history', label: 'History', icon: TAB_ICONS.history, badge: 0 },
  { to: '/seller/menus', label: 'Edit', icon: TAB_ICONS.menus, badge: 0 },
])

async function logout() {
  await authStore.logout()
  router.push('/seller/login')
}
</script>

<style scoped>
.sm-show { display: none; }
@media (min-width: 640px) { .sm-show { display: inline; } }
</style>
