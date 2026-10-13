<template>
  <div>
    <NavBar />
    <main class="max-w-md mx-auto px-4 py-12">
      <h1 class="text-2xl font-bold mb-2">Lacak Pesanan</h1>
      <p class="text-muted-foreground text-sm mb-6">
        Masukkan token tracking yang diberikan saat pesanan dibuat.
      </p>
      <div class="space-y-3">
        <div>
          <Label for="token">Token Tracking</Label>
          <Input
            id="token"
            v-model="token"
            placeholder="Tempel token di sini..."
            class="mt-1"
            @keydown.enter="go"
          />
        </div>
        <Button class="w-full" :disabled="!token.trim()" @click="go">Cek Status</Button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const token = ref('')
const router = useRouter()

function go() {
  const t = token.value.trim()
  if (t) router.push({ name: 'track-order', params: { token: t } })
}
</script>
