<template>
  <div>
    <NavBar />
    <main class="max-w-2xl mx-auto px-4 py-6">
      <h1 class="text-2xl font-bold mb-6">Checkout</h1>

      <!-- ── 1. Pesanan berhasil dibuat → tampil token ─────────────────────
           Harus di luar v-else cart agar tidak hilang saat cart.clear()    -->
      <div v-if="orderResult" class="mb-6 border border-green-500 rounded-lg p-4 bg-green-50">
        <p class="font-bold text-green-800 mb-2">✅ Pesanan Berhasil Dibuat!</p>
        <p class="text-sm mb-1">Nomor Pesanan: <strong>{{ orderResult.order_number }}</strong></p>
        <p class="text-sm mb-1">Meja: <strong>{{ tableNumber }}</strong></p>
        <p class="text-sm mb-1">Metode Bayar: <strong>{{ paymentMethodLabel }}</strong></p>
        <div class="mt-3 p-3 bg-yellow-100 border border-yellow-400 rounded">
          <p class="text-xs font-bold text-yellow-800 mb-1">🔑 TOKEN TRACKING — SIMPAN SEKARANG!</p>
          <p class="font-mono text-xs break-all">{{ orderResult.tracking_token }}</p>
          <button
            class="mt-2 text-xs text-blue-700 underline"
            @click="copyToken"
          >Salin Token</button>
          <p class="text-xs text-yellow-800 mt-2">Token ini hanya muncul sekali dan tidak dapat dipulihkan.</p>
        </div>
        <p class="text-sm mt-3 font-medium">Total: {{ formatRupiah(orderResult.total_amount) }}</p>
        <Button class="mt-4 w-full" @click="goToTrack">Pantau Status Pesanan →</Button>
      </div>

      <!-- ── 2. Duplicate idempotency ──────────────────────────────────── -->
      <div v-else-if="duplicateResult" class="mb-6 border rounded-lg p-4 bg-gray-50">
        <p class="font-medium">Pesanan sudah ada (idempotency key dikenali).</p>
        <p class="text-sm mt-1">Nomor Pesanan: <strong>{{ duplicateResult.order_number }}</strong></p>
      </div>

      <!-- ── 3. Cart kosong dan belum ada order ────────────────────────── -->
      <div v-else-if="cart.items.length === 0" class="text-muted-foreground text-center py-12">
        <p class="text-4xl mb-3">🛒</p>
        <p>Keranjang kosong.</p>
        <RouterLink to="/" class="text-primary hover:underline text-sm mt-2 inline-block">Lihat menu →</RouterLink>
      </div>

      <!-- ── 4. Cart berisi → form checkout ───────────────────────────── -->
      <template v-else>
        <!-- Cart items -->
        <div class="border rounded-lg p-4 mb-6">
          <h2 class="font-semibold mb-3">Pesanan Anda</h2>
          <CartItem v-for="item in cart.items" :key="item.menu.id" :item="item" />
          <div class="flex justify-between font-bold mt-4 pt-3 border-t">
            <span>Total (estimasi)</span>
            <span>{{ formatRupiah(cart.total) }}</span>
          </div>
          <p class="text-xs text-muted-foreground mt-1">
            * Total final dihitung oleh server berdasarkan harga terkini.
          </p>
        </div>

        <!-- Order form -->
        <div class="border rounded-lg p-4 mb-6 space-y-4">
          <h2 class="font-semibold">Data Pemesan</h2>
          <div>
            <Label for="buyer_name">Nama Pemesan *</Label>
            <Input id="buyer_name" v-model="buyerName" placeholder="Masukkan nama Anda" class="mt-1" />
            <p v-if="nameError" class="text-xs text-destructive mt-1">{{ nameError }}</p>
          </div>
          <div>
            <Label for="table_number">Nomor Meja *</Label>
            <Input
              id="table_number"
              v-model="tableNumber"
              placeholder="Contoh: 5"
              inputmode="numeric"
              class="mt-1"
            />
            <p v-if="tableError" class="text-xs text-destructive mt-1">{{ tableError }}</p>
          </div>
          <div>
            <Label>Metode Pembayaran *</Label>
            <div class="flex gap-3 mt-2">
              <label
                class="flex items-center gap-2 cursor-pointer border rounded-lg px-4 py-2 flex-1 justify-center text-sm font-medium transition-colors"
                :class="paymentMethod === 'qris' ? 'border-primary bg-primary/5' : 'border-border'"
              >
                <input type="radio" v-model="paymentMethod" value="qris" class="accent-primary" />
                QRIS
              </label>
              <label
                class="flex items-center gap-2 cursor-pointer border rounded-lg px-4 py-2 flex-1 justify-center text-sm font-medium transition-colors"
                :class="paymentMethod === 'cash' ? 'border-primary bg-primary/5' : 'border-border'"
              >
                <input type="radio" v-model="paymentMethod" value="cash" class="accent-primary" />
                Cash
              </label>
            </div>
            <p v-if="methodError" class="text-xs text-destructive mt-1">{{ methodError }}</p>
          </div>
          <div>
            <Label for="notes">Catatan (opsional)</Label>
            <Textarea id="notes" v-model="notes" placeholder="Contoh: tidak pakai pedas" class="mt-1" />
          </div>
        </div>

        <!-- Info pembayaran -->
        <div class="border rounded-lg p-4 mb-6 bg-blue-50 text-sm">
          <p class="font-semibold mb-1">Info Pembayaran</p>
          <template v-if="paymentMethod === 'qris'">
            <p>Bayar via QRIS setelah pesanan diterima. Seller akan mengkonfirmasi pembayaran.</p>
          </template>
          <template v-else>
            <p>Bayar tunai saat pesanan siap diambil.</p>
          </template>
          <p class="mt-2 text-destructive font-medium">⚠️ Simpan token tracking yang muncul setelah memesan!</p>
        </div>

        <!-- API error -->
        <div v-if="apiError" class="mb-4 p-3 border border-destructive rounded-lg text-sm text-destructive">
          {{ apiError }}
        </div>

        <Button
          class="w-full"
          :disabled="submitting"
          @click="openConfirm"
        >
          {{ submitting ? 'Memproses...' : 'Buat Pesanan' }}
        </Button>
      </template>
    </main>

    <!-- ── Confirm Popup ─────────────────────────────────────────────────── -->
    <div v-if="showConfirm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
      <div class="bg-background rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
        <h2 class="font-bold text-lg">Konfirmasi Pesanan</h2>
        <div class="text-sm space-y-1">
          <p>Nama: <strong>{{ buyerName }}</strong></p>
          <p>Meja: <strong>{{ tableNumber }}</strong></p>
          <p>Metode Bayar: <strong>{{ paymentMethodLabel }}</strong></p>
          <p>Total Estimasi: <strong>{{ formatRupiah(cart.total) }}</strong></p>
        </div>
        <p class="text-xs text-muted-foreground">Pastikan data sudah benar sebelum memesan.</p>
        <div class="flex gap-3">
          <Button variant="outline" class="flex-1" @click="showConfirm = false">Batal</Button>
          <Button class="flex-1" :disabled="submitting" @click="submit">
            {{ submitting ? 'Memproses...' : 'Ya, Pesan' }}
          </Button>
        </div>
      </div>
    </div>

    <Toaster />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { createOrder } from '@/lib/api'
import type { OrderCreateResponse, OrderDuplicateResponse } from '@/types/api'
import { ApiError } from '@/types/api'
import { useCartStore } from '@/stores/cart'
import { formatRupiah } from '@/utils/format'
import NavBar from '@/components/NavBar.vue'
import CartItem from '@/components/buyer/CartItem.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Toaster } from '@/components/ui/sonner'

const cart = useCartStore()
const router = useRouter()

const buyerName = ref('')
const tableNumber = ref('')
const paymentMethod = ref<'qris' | 'cash'>('qris')
const notes = ref('')
const nameError = ref('')
const tableError = ref('')
const methodError = ref('')
const apiError = ref<string | null>(null)
const submitting = ref(false)
const showConfirm = ref(false)

const orderResult = ref<OrderCreateResponse | null>(null)
const duplicateResult = ref<OrderDuplicateResponse | null>(null)

// Generated once per checkout session — prevents duplicates on retry
const idempotencyKey = crypto.randomUUID()
let createdTrackingToken = ''

const paymentMethodLabel = computed(() =>
  paymentMethod.value === 'qris' ? 'QRIS' : 'Cash'
)

function validate(): boolean {
  let ok = true
  nameError.value = ''
  tableError.value = ''
  methodError.value = ''

  if (!buyerName.value.trim()) {
    nameError.value = 'Nama pemesan wajib diisi'
    ok = false
  }
  if (!tableNumber.value.trim()) {
    tableError.value = 'Nomor meja wajib diisi'
    ok = false
  } else if (!/^\d{1,4}$/.test(tableNumber.value.trim())) {
    tableError.value = 'Nomor meja harus 1–4 digit angka'
    ok = false
  }
  if (!paymentMethod.value) {
    methodError.value = 'Pilih metode pembayaran'
    ok = false
  }
  return ok
}

function openConfirm() {
  apiError.value = null
  if (!validate()) return
  showConfirm.value = true
}

async function submit() {
  showConfirm.value = false
  submitting.value = true
  apiError.value = null
  try {
    const { data, status } = await createOrder(
      {
        buyer_name: buyerName.value.trim(),
        table_number: tableNumber.value.trim(),
        payment_method: paymentMethod.value,
        items: cart.items.map(i => ({ menu_id: i.menu.id, quantity: i.quantity })),
        notes: notes.value.trim() || null,
      },
      idempotencyKey
    )

    if (status === 201) {
      const res = data as OrderCreateResponse
      orderResult.value = res
      createdTrackingToken = res.tracking_token
      cart.clear()
      toast.success('Pesanan berhasil dibuat!')
    } else {
      duplicateResult.value = data as OrderDuplicateResponse
    }
  } catch (e) {
    if (e instanceof ApiError) {
      apiError.value = `Error ${e.status}: [${e.code}] ${e.message}`
      if (e.details?.length) {
        apiError.value += ' — ' + e.details.map(d => `${d.field}: ${d.message}`).join(', ')
      }
    } else if (e instanceof TypeError && e.message.includes('fetch')) {
      apiError.value = 'Tidak bisa menghubungi server. Pastikan backend berjalan di http://localhost:8000'
    } else if (e instanceof Error) {
      apiError.value = e.message
    } else {
      apiError.value = String(e)
    }
  } finally {
    submitting.value = false
  }
}

async function copyToken() {
  if (!orderResult.value) return
  await navigator.clipboard.writeText(orderResult.value.tracking_token)
  toast.success('Token disalin!')
}

function goToTrack() {
  router.push({
    name: 'track-order',
    params: { token: createdTrackingToken },
  })
}
</script>
