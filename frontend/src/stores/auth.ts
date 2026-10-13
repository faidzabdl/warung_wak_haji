import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { supabase } from '@/lib/supabase'
import type { Session } from '@supabase/supabase-js'
import { ApiError } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const session = ref<Session | null>(null)
  const loading = ref(true)

  const accessToken = computed(() => session.value?.access_token ?? null)
  const isLoggedIn = computed(() => session.value !== null)

  /** Restore session on app startup */
  async function init() {
    loading.value = true
    const { data } = await supabase.auth.getSession()
    session.value = data.session

    supabase.auth.onAuthStateChange((_event, newSession) => {
      session.value = newSession
    })
    loading.value = false
  }

  async function login(email: string, password: string): Promise<void> {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      throw new ApiError(401, { code: 'AUTH_ERROR', message: error.message })
    }
    session.value = data.session
  }

  async function logout(): Promise<void> {
    await supabase.auth.signOut()
    session.value = null
  }

  return { session, loading, accessToken, isLoggedIn, init, login, logout }
})
