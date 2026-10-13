<template>
  <!-- Inline panel, not a modal — simpler and avoids Dialog dependency issues -->
  <div class="border rounded-lg p-4 bg-muted/20 mt-4">
    <h3 class="font-semibold mb-4">Tambah Menu Baru</h3>

    <!-- Step 1: Upload image (optional) -->
    <div class="mb-4">
      <Label>Gambar Menu (opsional)</Label>
      <div class="flex items-center gap-2 mt-1">
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          class="text-sm"
          @change="onImageChange"
        />
        <Button size="sm" variant="outline" :disabled="!imageFile || imageUploading" @click="uploadImage">
          {{ imageUploading ? 'Mengunggah...' : 'Upload' }}
        </Button>
      </div>
      <div v-if="imageUrl" class="mt-2">
        <img :src="imageUrl" alt="Preview" class="h-24 rounded border" />
        <p class="text-xs text-green-700 mt-1">✅ Gambar berhasil diunggah</p>
      </div>
      <p v-if="imageError" class="text-xs text-destructive mt-1">{{ imageError }}</p>
    </div>

    <div class="grid grid-cols-1 gap-3">
      <div>
        <Label>Nama Menu *</Label>
        <Input v-model="form.name" placeholder="Contoh: Nasi Goreng" class="mt-1" />
      </div>
      <div>
        <Label>Harga (Rp) *</Label>
        <Input v-model.number="form.price" type="number" min="1" placeholder="15000" class="mt-1" />
      </div>
      <div>
        <Label>Deskripsi</Label>
        <Textarea v-model="form.description" placeholder="Deskripsi singkat..." class="mt-1" />
      </div>
      <div class="flex gap-4">
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" v-model="form.is_available" class="w-4 h-4" />
          Tersedia
        </label>
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" v-model="form.is_active" class="w-4 h-4" />
          Aktif
        </label>
      </div>
    </div>

    <p v-if="formError" class="text-xs text-destructive mt-3">{{ formError }}</p>

    <div class="flex gap-2 mt-4">
      <Button :disabled="submitting" @click="submit">
        {{ submitting ? 'Menyimpan...' : 'Buat Menu' }}
      </Button>
      <Button variant="outline" @click="$emit('cancel')">Batal</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { uploadMenuImage, createMenu } from '@/lib/api'
import { ApiError } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{ created: []; cancel: [] }>()

const form = ref({ name: '', price: 0, description: '', is_available: true, is_active: true })
const imageFile = ref<File | null>(null)
const imageUrl = ref('')
const imageUploading = ref(false)
const imageError = ref('')
const formError = ref('')
const submitting = ref(false)

function onImageChange(e: Event) {
  const input = e.target as HTMLInputElement
  imageFile.value = input.files?.[0] ?? null
  imageError.value = ''
  imageUrl.value = ''
}

async function uploadImage() {
  if (!imageFile.value) return
  imageUploading.value = true
  imageError.value = ''
  try {
    const res = await uploadMenuImage(imageFile.value, props.token)
    imageUrl.value = res.image_url
  } catch (e) {
    imageError.value = e instanceof ApiError ? e.message : 'Gagal upload gambar.'
  } finally {
    imageUploading.value = false
  }
}

async function submit() {
  formError.value = ''
  if (!form.value.name.trim()) { formError.value = 'Nama wajib diisi.'; return }
  if (!form.value.price || form.value.price <= 0) { formError.value = 'Harga harus lebih dari 0.'; return }

  submitting.value = true
  try {
    await createMenu({
      name: form.value.name.trim(),
      price: form.value.price,
      description: form.value.description.trim() || null,
      image_url: imageUrl.value || null,
      is_available: form.value.is_available,
      is_active: form.value.is_active,
    }, props.token)
    emit('created')
  } catch (e) {
    formError.value = e instanceof ApiError ? e.message : 'Gagal membuat menu.'
  } finally {
    submitting.value = false
  }
}
</script>
