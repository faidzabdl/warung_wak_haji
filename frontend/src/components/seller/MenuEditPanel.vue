<template>
  <div class="border rounded-lg p-4 bg-muted/20 mt-2">
    <h3 class="font-semibold mb-4">Edit Menu: {{ menu.name }}</h3>

    <!-- Image upload -->
    <div class="mb-4">
      <Label>Ganti Gambar (opsional)</Label>
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
      <div v-if="form.image_url" class="mt-2">
        <img :src="form.image_url" alt="Preview" class="h-20 rounded border" />
      </div>
      <p v-if="imageError" class="text-xs text-destructive mt-1">{{ imageError }}</p>
    </div>

    <div class="grid grid-cols-1 gap-3">
      <div>
        <Label>Nama Menu</Label>
        <Input v-model="form.name" class="mt-1" />
      </div>
      <div>
        <Label>Harga (Rp)</Label>
        <Input v-model.number="form.price" type="number" min="1" class="mt-1" />
      </div>
      <div>
        <Label>Deskripsi</Label>
        <Textarea v-model="form.description" class="mt-1" />
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
        {{ submitting ? 'Menyimpan...' : 'Simpan Perubahan' }}
      </Button>
      <Button variant="outline" @click="$emit('cancel')">Batal</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { updateMenu, uploadMenuImage } from '@/lib/api'
import { ApiError, type MenuResponse } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{ menu: MenuResponse; token: string }>()
const emit = defineEmits<{ updated: [menu: MenuResponse]; cancel: [] }>()

const form = ref({
  name: props.menu.name,
  price: parseFloat(props.menu.price),
  description: props.menu.description ?? '',
  image_url: props.menu.image_url ?? '',
  is_available: props.menu.is_available,
  is_active: props.menu.is_active,
})

const imageFile = ref<File | null>(null)
const imageUploading = ref(false)
const imageError = ref('')
const formError = ref('')
const submitting = ref(false)

function onImageChange(e: Event) {
  const input = e.target as HTMLInputElement
  imageFile.value = input.files?.[0] ?? null
}

async function uploadImage() {
  if (!imageFile.value) return
  imageUploading.value = true
  imageError.value = ''
  try {
    const res = await uploadMenuImage(imageFile.value, props.token)
    form.value.image_url = res.image_url
  } catch (e) {
    imageError.value = e instanceof ApiError ? e.message : 'Gagal upload gambar.'
  } finally {
    imageUploading.value = false
  }
}

async function submit() {
  formError.value = ''
  if (!form.value.name.trim()) { formError.value = 'Nama wajib diisi.'; return }
  if (form.value.price <= 0) { formError.value = 'Harga harus lebih dari 0.'; return }

  submitting.value = true
  try {
    // Only send fields that differ from original to keep payload minimal
    const patch: Record<string, unknown> = {}
    if (form.value.name !== props.menu.name) patch.name = form.value.name.trim()
    if (form.value.price !== parseFloat(props.menu.price)) patch.price = form.value.price
    if (form.value.description !== (props.menu.description ?? '')) patch.description = form.value.description || null
    if (form.value.image_url !== (props.menu.image_url ?? '')) patch.image_url = form.value.image_url || null
    if (form.value.is_available !== props.menu.is_available) patch.is_available = form.value.is_available
    if (form.value.is_active !== props.menu.is_active) patch.is_active = form.value.is_active

    const updated = await updateMenu(props.menu.id, patch, props.token)
    emit('updated', updated)
  } catch (e) {
    formError.value = e instanceof ApiError ? e.message : 'Gagal menyimpan perubahan.'
  } finally {
    submitting.value = false
  }
}
</script>
