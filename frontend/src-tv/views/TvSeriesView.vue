<template>
  <div>
    <header class="tv-page-header"><div><h1>Series</h1><p>Catálogo completo</p></div></header>
    <div class="tv-search"><input ref="searchInput" v-model="query" :class="['tv-input', { 'tv-input--editing': searchEditing }]" data-tv-focus readonly placeholder="Buscar una serie…" @click="activateSearch" @keydown.enter.stop.prevent="activateSearch"></div>
    <div v-if="loading" class="tv-loading"><span class="tv-spinner"></span></div>
    <div v-else-if="error" class="tv-status tv-status--error">{{ error }}</div>
    <div v-else-if="!series.length" class="tv-empty">No se encontraron series</div>
    <div v-else class="tv-grid">
      <TvCard v-for="serie in series" :key="serie.id" :image="serie.portada_url" :title="serie.nombre" :subtitle="`${serie.descargados_count}/${serie.capitulos_count} descargados`" :badge="serie.estado === 'en_emision' ? 'En emisión' : serie.estado === 'concluido' ? 'Concluido' : ''" @select="open(serie.id)" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { getSeries } from '../../src/api'
import { useSpatialNavigation, focusFirst } from '../composables/useSpatialNavigation'
import TvCard from '../components/TvCard.vue'
import { editTvValue } from '../plugins/tvKeyboard'
const router = useRouter()
const query = ref('')
const series = ref([])
const loading = ref(true)
const error = ref('')
const searchInput = ref(null)
const searchEditing = ref(false)
let initialLoad = true
async function load() {
  loading.value = true; error.value = ''
  try { series.value = (await getSeries(query.value.trim())).data }
  catch { error.value = 'No se pudo cargar el catálogo.' }
  finally {
    loading.value = false
    if (initialLoad) {
      initialLoad = false
      focusFirst('.tv-grid .tv-card')
    }
  }
}
async function activateSearch() {
  if (searchEditing.value) return
  searchEditing.value = true
  const result = await editTvValue({ value: query.value, kind: 'text', title: 'Buscar una serie' })
  if (!result.cancelled) {
    query.value = result.value
    await load()
  }
  searchEditing.value = false
  await nextTick()
  searchInput.value?.focus({ preventScroll: true })
}
function open(id) { router.push({ name: 'tv-chapters', params: { id } }) }
onMounted(load)
useSpatialNavigation({ onBack: () => router.push('/') })
</script>

<style scoped>.tv-search { max-width: 680px; margin-bottom: 34px; }</style>
