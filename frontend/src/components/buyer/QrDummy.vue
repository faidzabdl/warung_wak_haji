<template>
  <svg viewBox="-2 -2 29 29" role="img" aria-label="QR Code contoh" shape-rendering="crispEdges">
    <rect x="-2" y="-2" width="29" height="29" fill="#fff"/>
    <path :d="path" fill="#111"/>
    <g v-for="f in finders" :key="f.join('-')">
      <rect :x="f[0]" :y="f[1]" width="7" height="7" fill="#111"/>
      <rect :x="f[0]+1" :y="f[1]+1" width="5" height="5" fill="#fff"/>
      <rect :x="f[0]+2" :y="f[1]+2" width="3" height="3" fill="#111"/>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ seed?: string }>(), { seed: 'wwh' })

const N = 25
const finders = [[0, 0], [N - 7, 0], [0, N - 7]]

const path = computed(() => {
  let h = 2166136261
  for (const c of props.seed) {
    h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0
  }
  h = h || 1
  const rnd = () => {
    h ^= h << 13; h >>>= 0
    h ^= h >>> 17
    h ^= h << 5; h >>>= 0
    return h / 4294967296
  }
  let d = ''
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const f = (x < 8 && y < 8) || (x >= N - 8 && y < 8) || (x < 8 && y >= N - 8)
      if (!f && rnd() > 0.52) d += `M${x} ${y}h1v1h-1z`
    }
  }
  return d
})
</script>
