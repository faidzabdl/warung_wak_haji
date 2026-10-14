<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="cancel">
    <div class="bg-white rounded-xl shadow-lg w-full max-w-md p-6">
      <h2 class="font-bold mb-2">{{ title }}</h2>
      <p class="text-sm text-muted-foreground mb-4">{{ description }}</p>
      <div>
        <Label>{{ reasonLabel }}</Label>
        <Textarea v-model="reason" :placeholder="placeholder" class="mt-1" />
      </div>
      <div class="flex gap-2 mt-4 justify-end">
        <Button variant="outline" @click="cancel">Batal</Button>
        <Button :variant="confirmVariant" :disabled="submitting" @click="confirm">
          {{ submitting ? 'Memproses...' : confirmLabel }}
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

withDefaults(defineProps<{
  title: string
  description?: string
  reasonLabel?: string
  placeholder?: string
  confirmLabel?: string
  confirmVariant?: 'default' | 'destructive'
  submitting?: boolean
}>(), {
  description: '',
  reasonLabel: 'Alasan',
  placeholder: 'Masukkan alasan (opsional)...',
  confirmLabel: 'Konfirmasi',
  confirmVariant: 'destructive',
  submitting: false,
})

const emit = defineEmits<{
  confirm: [reason: string | null]
  cancel: []
}>()

const reason = ref('')

function confirm() {
  // reason is optional — pass null if empty
  emit('confirm', reason.value.trim() || null)
}

function cancel() {
  reason.value = ''
  emit('cancel')
}
</script>
