import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // ── Buyer ────────────────────────────────────────────────────────────────
    {
      path: '/',
      name: 'menu-list',
      component: () => import('@/pages/buyer/MenuListPage.vue'),
    },
    {
      path: '/menu/:id',
      name: 'menu-detail',
      component: () => import('@/pages/buyer/MenuDetailPage.vue'),
    },
    {
      path: '/checkout',
      name: 'checkout',
      component: () => import('@/pages/buyer/CheckoutPage.vue'),
    },
    {
      path: '/order/:orderNumber/proof',
      name: 'proof',
      component: () => import('@/pages/buyer/ProofUploadPage.vue'),
    },
    {
      path: '/track',
      name: 'track-input',
      component: () => import('@/pages/buyer/TrackInputPage.vue'),
    },
    {
      path: '/track/:token',
      name: 'track-order',
      component: () => import('@/pages/buyer/TrackOrderPage.vue'),
    },

    // ── Seller ───────────────────────────────────────────────────────────────
    {
      path: '/seller/login',
      name: 'seller-login',
      component: () => import('@/pages/seller/SellerLoginPage.vue'),
    },
    {
      path: '/seller',
      component: () => import('@/layouts/SellerLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/seller/orders',
        },
        {
          path: 'orders',
          name: 'seller-orders',
          component: () => import('@/pages/seller/SellerOrdersPage.vue'),
        },
        {
          path: 'menus',
          name: 'seller-menus',
          component: () => import('@/pages/seller/SellerMenuPage.vue'),
        },
        {
          path: 'history',
          name: 'seller-history',
          component: () => import('@/pages/seller/SellerHistoryPage.vue'),
        },
      ],
    },
  ],
})

// Navigation guard — protect all /seller/* routes except login
router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true

  const authStore = useAuthStore()

  // Wait for session to be initialised on first load
  if (authStore.loading) {
    await authStore.init()
  }

  if (!authStore.isLoggedIn) {
    return { name: 'seller-login' }
  }

  return true
})

export default router
