<template>
  <div>
    <header class="tv-page-header tv-page-header--tabs-only">
      <div class="tv-tabs">
        <button v-for="tab in tabs" :key="tab.key" data-tv-focus :class="['tv-button', activeTab === tab.key ? '' : 'tv-button--secondary']" @click="activeTab = tab.key">{{ tab.label }}</button>
      </div>
    </header>

    <div v-if="loading" class="tv-loading"><span class="tv-spinner"></span></div>
    <div v-else-if="error" class="tv-status tv-status--error">{{ error }}</div>

    <template v-else-if="activeTab === 'latest'">
      <TvSection v-for="group in latestGroups" :key="group.name" :title="group.name" :count="group.items.length">
        <TvCard v-for="episode in group.items" :key="episode.url" :image="episode.imagen" :title="episode.nombre" :subtitle="`Episodio ${episode.episodio}`" :badge="latestBadge(episode)" badge-tone="yellow" @select="selectEpisode(episode)" />
      </TvSection>
    </template>

    <template v-else-if="activeTab === 'airing'">
      <TvSection v-for="group in airingGroups" :key="group.name" :title="group.name" :count="group.items.length">
        <TvCard v-for="serie in group.items" :key="serie.id" :image="serie.portada_url" :title="serie.nombre" :subtitle="`${serie.capitulos_count} episodios`" @select="openSeries(serie.id)" />
      </TvSection>
    </template>

    <TvSection v-else title="Concluidos" :count="completed.length">
      <TvCard v-for="serie in completed" :key="serie.id" :image="serie.portada_url" :title="serie.nombre" :subtitle="`${serie.descargados_count}/${serie.capitulos_count} descargados`" @select="openSeries(serie.id)" />
    </TvSection>

    <TvPlayer v-if="playerId" :chapter-id="playerId" @close="playerId = null" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getUltimosEpisodios, getFavoritosByEstado, verificarCapitulo, descargarCapitulo } from '../../src/api'
import { useDownloadStore } from '../../src/stores/downloads'
import { useSpatialNavigation } from '../composables/useSpatialNavigation'
import TvSection from '../components/TvSection.vue'
import TvCard from '../components/TvCard.vue'
import TvPlayer from '../components/TvPlayer.vue'

const router = useRouter()
const downloads = useDownloadStore()
const tabs = [{ key: 'latest', label: 'Últimos' }, { key: 'airing', label: 'En emisión' }, { key: 'completed', label: 'Concluidos' }]
const activeTab = ref('latest')
const loading = ref(false)
const error = ref('')
const latest = ref([])
const airing = ref([])
const completed = ref([])
const loaded = new Set()
const playerId = ref(null)
const dayNames = { lunes: 'Lunes', martes: 'Martes', miercoles: 'Miércoles', jueves: 'Jueves', viernes: 'Viernes', sabado: 'Sábado', domingo: 'Domingo', unknown: 'Sin día' }

const latestGroups = computed(() => ['Animes', 'Donghuas', 'Ovas'].map(name => ({ name, items: latest.value.filter(ep => (ep.tab || 'Animes') === name) })).filter(g => g.items.length))
const airingGroups = computed(() => {
  const groups = new Map()
  for (const serie of airing.value) {
    const day = serie.dia_emision || 'unknown'
    if (!groups.has(day)) groups.set(day, [])
    groups.get(day).push(serie)
  }
  return [...groups].map(([day, items]) => ({ name: dayNames[day], items }))
})

async function loadTab(tab) {
  if (loaded.has(tab)) return
  loading.value = true
  error.value = ''
  try {
    if (tab === 'latest') latest.value = (await getUltimosEpisodios()).data.episodios || []
    else if (tab === 'airing') airing.value = (await getFavoritosByEstado('en_emision')).data
    else completed.value = (await getFavoritosByEstado('concluido')).data
    loaded.add(tab)
  } catch (e) { error.value = e.response?.data?.error || 'No se pudo conectar con el servidor.' }
  finally { loading.value = false }
}
function openSeries(id) { router.push({ name: 'tv-chapters', params: { id } }) }
function downloadProgress(id) {
  const item = downloads.downloads.find(d => d.capituloId === id && ['PENDING', 'PROGRESS'].includes(d.state))
  return item ? Number(item.porcentaje || 0) : null
}
function latestBadge(episode) {
  const progress = downloadProgress(episode.capitulo_id)
  if (progress !== null) return `${progress}%`
  return episode.archivo_existe ? '✓' : '⇩'
}
async function selectEpisode(ep) {
  if (!ep.capitulo_id) return ep.serie_id ? openSeries(ep.serie_id) : null
  error.value = ''
  try {
    const { data } = await verificarCapitulo(ep.capitulo_id)
    if (data.valido) { playerId.value = ep.capitulo_id; return }
    const response = await descargarCapitulo(ep.capitulo_id)
    if (response.data.skip) playerId.value = ep.capitulo_id
    else if (response.data.task_id) downloads.addDownload(response.data.task_id, ep.capitulo_id, ep.nombre, ep.episodio, () => { ep.archivo_existe = true })
  } catch (e) {
    const detail = e.response?.data?.error || e.response?.data?.detail || e.message
    error.value = `No se pudo preparar el episodio${detail ? `: ${detail}` : '.'}`
  }
}
watch(activeTab, loadTab, { immediate: true })
useSpatialNavigation({ onBack: () => {} })
</script>

<style scoped>
.tv-page-header--tabs-only { justify-content: flex-start; }
.tv-tabs { display: flex; gap: 12px; }
</style>
