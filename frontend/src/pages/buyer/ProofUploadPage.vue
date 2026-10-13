<template>
  <div>
    <NavBar />
    <main class="max-w-xl mx-auto px-4 py-6">
      <h1 class="text-2xl font-bold mb-2">Upload Bukti Pembayaran</h1>
      <p class="text-muted-foreground text-sm mb-6">
        Nomor Pesanan: <strong>{{ orderNumber }}</strong>
      </p>

      <!-- Token input (shown if not passed via router state) -->
      <div v-if="!hasToken" class="border rounded-lg p-4 mb-6">
        <Label for="token-input">Token Tracking *</Label>
        <Input
          id="token-input"
          v-model="manualToken"
          placeholder="Masukkan token dari halaman pesanan"
          class="mt-1"
        />
        <p class="text-xs text-muted-foreground mt-1">
          Token diberikan saat pesanan dibuat. Tidak dapat dipulihkan jika hilang.
        </p>
      </div>

      <!-- File picker -->
      <div class="border rounded-lg p-4 mb-6">
        <Label>Bukti Pembayaran *</Label>
        <p class="text-xs text-muted-foreground mt-1 mb-3">Format: JPG, PNG, atau WebP. Ukuran maksimal 5 MB.</p>
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          class="block w-full text-sm"
          @change="onFileChange"
        />
        <div v-if="preview" class="mt-3">
          <img :src="preview" alt="Preview" class="max-h-48 rounded border" />
        </div>
        <p v-if="fileError" class="text-xs text-destructive mt-2">{{ fileError }}</p>
      </div>

      <!-- API error -->
      <div v-if="apiError" class="mb-4 p-3 border border-destructive rounded-lg text-sm text-destructive">
        {{ apiError }}
      </div>

      <!-- Success -->
      <div v-if="success" class="mb-4 p-4 border border-green-500 rounded-lg bg-green-50">
        <p class="font-semibold text-green-800">✅ Bukti berhasil diunggah!</p>
        <p class="text-sm mt-1">Status pembayaran: <strong>{{ success.payment_status }}</strong></p>
        <p class="text-sm text-muted-foreground mt-2">
          Pembayaran akan diverifikasi oleh penjual. Pantau status pesanan Anda.
        </p>
        <RouterLink
          v-if="effectiveToken"
          :to="`/track/${effectiveToken}`"
          class="mt-3 inline-block text-sm text-primary underline"
        >
          Lacak Status Pesanan →
        </RouterLink>
      </div>

      <Button
        v-if="!success"
        class="w-full"
        :disabled="uploading || !selectedFile"
        @click="upload"
      >
        {{ uploading ? 'Mengunggah...' : 'Upload Bukti Pembayaran' }}
      </Button>
    </main>
    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from 'vue-sonner'
import { uploadProof } from '@/lib/api'
import { ApiError, type ProofUploadResponse } from '@/types/api'
import NavBar from '@/components/NavBar.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Toaster } from '@/components/ui/sonner'

const route = useRoute()
const orderNumber = route.params.orderNumber as string

// Token passed via router state from checkout, or entered manually
const stateToken = (history.state?.trackingToken as string | undefined) ?? ''
const manualToken = ref('')
const hasToken = computed(() => !!stateToken)
const effectiveToken = computed(() => stateToken || manualToken.value.trim())

const selectedFile = ref<File | null>(null)
const preview = ref<string | null>(null)
const fileError = ref('')
const apiError = ref<string | null>(null)
const uploading = ref(false)
const success = ref<ProofUploadResponse | null>(null)

const MAX_SIZE = 5 * 1024 * 1024

function onFileChange(e: Event) {
  fileError.value = ''
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  if (file.size > MAX_SIZE) {
    fileError.value = 'File terlalu besar. Maksimal 5 MB.'
    selectedFile.value = null
    preview.value = null
    return
  }

  const allowed = ['image/jpeg', 'image/png', 'image/webp']
  if (!allowed.includes(file.type)) {
    fileError.value = 'Format tidak didukung. Gunakan JPG, PNG, atau WebP.'
    selectedFile.value = null
    preview.value = null
    return
  }

  selectedFile.value = file
  preview.value = URL.createObjectURL(file)
}

async function upload() {
  apiError.value = null
  const token = effectiveToken.value
  if (!token) {
    apiError.value = 'Masukkan token tracking terlebih dahulu.'
    return
  }
  if (!selectedFile.value) return

  uploading.value = true
  try {
    success.value = await uploadProof(orderNumber, selectedFile.value, token)
    toast.success('Bukti pembayaran berhasil diunggah!')
  } catch (e) {
    if (e instanceof ApiError) {
      apiError.value = e.message
    } else {
      apiError.value = 'Gagal mengunggah. Coba lagi.'
    }
  } finally {
    uploading.value = false
  }
}
</script>
