<template>
  <div>
    <header class="tv-page-header"><div><h1>Agregar serie</h1><p>JKanime o Latanime</p></div></header>
    <form class="tv-form" @submit.prevent="submit">
      <div class="tv-field">
        <label for="tv-series-url">URL completa de la serie</label>
        <input id="tv-series-url" v-model="url" class="tv-input" data-tv-focus inputmode="url" autocomplete="off" placeholder="https://jkanime.net/serie/">
      </div>
      <div v-if="message" :class="['tv-status', { 'tv-status--error': isError }]">{{ message }}</div>
      <div class="tv-actions">
        <button class="tv-button" data-tv-focus :disabled="loading || !url.trim()" type="submit">{{ loading ? 'Agregando…' : 'Agregar serie' }}</button>
        <button class="tv-button tv-button--secondary" data-tv-focus type="button" @click="router.push('/')">Cancelar</button>
      </div>
    </form>
    <aside class="tv-tip">
      <strong>Consejo para TV</strong>
      <p>Puedes pegar la URL usando la aplicación de control remoto de tu teléfono. También puedes agregar series desde la interfaz web del mismo servidor.</p>
    </aside>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { agregarSerieUrl } from '../../src/api'
import { useSpatialNavigation } from '../composables/useSpatialNavigation'
const router = useRouter(); const url = ref(''); const loading = ref(false); const message = ref(''); const isError = ref(false)
async function submit() {
  loading.value = true; message.value = ''; isError.value = false
  try {
    const { data } = await agregarSerieUrl(url.value.trim())
    if (data.serie_id) router.push({ name: 'tv-chapters', params: { id: data.serie_id } })
    else message.value = data.message || 'La serie no pudo agregarse.'
  } catch (e) { message.value = e.response?.data?.error || 'No se pudo conectar con el servidor.'; isError.value = true }
  finally { loading.value = false }
}
useSpatialNavigation({ onBack: () => router.push('/') })
</script>

<style scoped>.tv-tip { max-width: 760px; margin-top: 42px; padding: 20px 24px; border-radius: 14px; background: var(--tv-panel); color: var(--tv-muted); font-size: 18px; line-height: 1.5; }.tv-tip strong { color: var(--tv-yellow); }</style>
