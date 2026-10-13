import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { MenuResponse } from '@/types/api'

export interface CartItem {
  menu: MenuResponse
  quantity: number
}

export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>([])

  const total = computed(() =>
    items.value.reduce((sum, item) => sum + parseFloat(item.menu.price) * item.quantity, 0)
  )

  const totalItems = computed(() =>
    items.value.reduce((sum, item) => sum + item.quantity, 0)
  )

  function addItem(menu: MenuResponse, quantity = 1) {
    const existing = items.value.find(i => i.menu.id === menu.id)
    if (existing) {
      existing.quantity += quantity
    } else {
      items.value.push({ menu, quantity })
    }
  }

  function removeItem(menuId: string) {
    items.value = items.value.filter(i => i.menu.id !== menuId)
  }

  function updateQuantity(menuId: string, quantity: number) {
    const item = items.value.find(i => i.menu.id === menuId)
    if (item) {
      if (quantity <= 0) {
        removeItem(menuId)
      } else {
        item.quantity = quantity
      }
    }
  }

  function clear() {
    items.value = []
  }

  return { items, total, totalItems, addItem, removeItem, updateQuantity, clear }
})
