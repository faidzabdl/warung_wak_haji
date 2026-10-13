<template>
  <div class="min-h-screen flex flex-col">
    <!-- Top bar -->
    <header class="border-b bg-white px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="font-semibold">🍽️ UMKM</span>
        <span class="text-muted-foreground text-sm">Dashboard Penjual</span>
      </div>
      <div class="flex items-center gap-4 text-sm">
        <span class="text-muted-foreground text-xs">{{ authStore.session?.user?.email }}</span>
        <button class="hover:underline text-destructive text-sm" @click="logout">Keluar</button>
      </div>
    </header>

    <div class="flex flex-1">
      <!-- Sidebar -->
      <nav class="w-48 border-r bg-muted/30 p-4 space-y-1 shrink-0">
        <RouterLink
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          class="block px-3 py-2 rounded-md text-sm hover:bg-muted"
          :class="{ 'bg-muted font-medium': $route.path.startsWith(link.to) }"
        >
          {{ link.label }}
        </RouterLink>
      </nav>

      <!-- Main content -->
      <main class="flex-1 p-6 overflow-auto">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const navLinks = [
  { to: '/seller/orders', label: '📋 Pesanan Aktif' },
  { to: '/seller/menus', label: '🍽️ Kelola Menu' },
  { to: '/seller/history', label: '📜 Riwayat' },
]

async function logout() {
  await authStore.logout()
  router.push('/seller/login')
}
</script>
