<template>
  <div class="min-h-screen flex items-center justify-center bg-muted/40 px-4">
    <div class="w-full max-w-sm border rounded-xl bg-white p-6 shadow-sm">
      <h1 class="text-xl font-bold mb-1">Login Penjual</h1>
      <p class="text-sm text-muted-foreground mb-6">Masuk dengan akun Supabase Auth.</p>

      <div class="space-y-4">
        <div>
          <Label for="email">Email</Label>
          <Input
            id="email"
            v-model="email"
            type="email"
            placeholder="seller@example.com"
            class="mt-1"
            autocomplete="email"
          />
        </div>
        <div>
          <Label for="password">Password</Label>
          <Input
            id="password"
            v-model="password"
            type="password"
            placeholder="••••••••"
            class="mt-1"
            autocomplete="current-password"
            @keydown.enter="login"
          />
        </div>

        <div v-if="error" class="text-sm text-destructive">{{ error }}</div>

        <Button class="w-full" :disabled="loading" @click="login">
          {{ loading ? 'Memproses...' : 'Masuk' }}
        </Button>
      </div>

      <!-- Setup hint -->
      <div class="mt-6 p-3 bg-blue-50 rounded text-xs text-blue-800">
        <p class="font-semibold mb-1">Belum punya akun?</p>
        <p>1. Buat akun di Supabase Dashboard → Authentication → Users.</p>
        <p>2. Salin UID akun tersebut ke <code>ALLOWED_SELLER_UID</code> di <code>backend/.env</code>.</p>
        <p>3. Isi <code>VITE_SUPABASE_URL</code> dan <code>VITE_SUPABASE_ANON_KEY</code> di <code>frontend/.env</code>.</p>
      </div>
    </div>
    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Toaster } from '@/components/ui/sonner'

const authStore = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

// Redirect if already logged in
if (authStore.isLoggedIn) {
  router.replace('/seller/orders')
}

async function login() {
  error.value = null
  if (!email.value || !password.value) {
    error.value = 'Email dan password wajib diisi.'
    return
  }
  loading.value = true
  try {
    await authStore.login(email.value, password.value)
    toast.success('Login berhasil!')
    router.push('/seller/orders')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Login gagal.'
  } finally {
    loading.value = false
  }
}
</script>
