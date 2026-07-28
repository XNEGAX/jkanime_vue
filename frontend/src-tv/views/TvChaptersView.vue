<template>
  <div class="tv-chapters-page">
    <header class="tv-chapters-hero">
      <button class="tv-button tv-button--secondary" data-tv-focus @click="router.back()">← Volver</button>
      <img v-if="serie?.portada_url" :src="serie.portada_url" :alt="serie.nombre">
      <div class="tv-chapters-info">
        <p class="eyebrow">{{ statusLabel }}</p>
        <h1>{{ serie?.nombre || 'Cargando…' }}</h1>
        <p>{{ chapters.length }} episodios · {{ downloadedCount }} descargados</p>
        <div class="tv-actions">
          <button v-if="downloadableCount > 1" class="tv-button" data-tv-focus :disabled="bulkLoading" @click="downloadAll">{{ bulkLoading ? 'Preparando…' : 'Descargar todos' }}</button>
          <button class="tv-button tv-button--secondary" data-tv-focus @click="toggleFavorite">{{ serie?.favorito ? '♥ Favorito' : '♡ Agregar favorito' }}</button>
        </div>
      </div>
    </header>

    <div v-if="message" :class="['tv-status', { 'tv-status--error': messageError }]">{{ message }}</div>
    <div v-if="loading" class="tv-loading"><span class="tv-spinner"></span></div>
    <section v-else class="tv-episodes">
      <h2>Episodios</h2>
      <div class="tv-episode-grid">
        <button v-for="chapter in chapters" :key="chapter.id" class="tv-episode" data-tv-focus @click="selectChapter(chapter)">
          <span class="tv-episode-copy"><strong>Episodio {{ chapter.numero }}</strong></span>
          <span v-if="activeDownload(chapter)" class="tv-episode-progress">{{ activeDownload(chapter).porcentaje || 0 }}%</span>
          <span v-else class="tv-episode-action">{{ chapter.archivo_existe ? '✓' : '⇩' }}</span>
        </button>
      </div>
    </section>
    <TvPlayer v-if="playerId" :chapter-id="playerId" @close="playerId = null" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSerieDetail, getCapitulos, toggleFavorito, verificarCapitulo, descargarCapitulo, descargarTodos } from '../../src/api'
import { useDownloadStore } from '../../src/stores/downloads'
import { useSpatialNavigation, focusFirst } from '../composables/useSpatialNavigation'
import TvPlayer from '../components/TvPlayer.vue'
const route = useRoute(); const router = useRouter(); const downloads = useDownloadStore()
const serie = ref(null); const chapters = ref([]); const loading = ref(true); const message = ref(''); const messageError = ref(false); const bulkLoading = ref(false); const playerId = ref(null)
const downloadedCount = computed(() => chapters.value.filter(c => c.archivo_existe).length)
const downloadableCount = computed(() => chapters.value.filter(chapter => !chapter.archivo_existe && !activeDownload(chapter)).length)
const statusLabel = computed(() => serie.value?.estado === 'en_emision' ? 'EN EMISIÓN' : serie.value?.estado === 'concluido' ? 'CONCLUIDO' : 'ANIMEWING')
function activeDownload(chapter) { return downloads.downloads.find(d => d.capituloId === chapter.id && ['PENDING', 'PROGRESS'].includes(d.state)) }
async function load() {
  loading.value = true
  try {
    const [detail, caps] = await Promise.all([getSerieDetail(route.params.id), getCapitulos(route.params.id)])
    serie.value = detail.data
    chapters.value = [...caps.data.capitulos].sort((a, b) => b.numero - a.numero)
  } catch { message.value = 'No se pudo cargar la serie.'; messageError.value = true }
  finally { loading.value = false; focusFirst() }
}
async function toggleFavorite() {
  if (!serie.value) return
  try { serie.value.favorito = (await toggleFavorito(serie.value.id)).data.favorito } catch { message.value = 'No se pudo cambiar el favorito.'; messageError.value = true }
}
async function selectChapter(chapter) {
  if (activeDownload(chapter)) return
  message.value = ''
  try {
    if (chapter.archivo_existe && (await verificarCapitulo(chapter.id)).data.valido) { playerId.value = chapter.id; return }
    const { data } = await descargarCapitulo(chapter.id)
    if (data.skip) playerId.value = chapter.id
    else if (data.task_id) downloads.addDownload(data.task_id, chapter.id, serie.value.nombre, chapter.numero, () => { chapter.archivo_existe = true })
  } catch (e) {
    const detail = e.response?.data?.error || e.response?.data?.detail || e.message
    message.value = `No se pudo preparar el episodio${detail ? `: ${detail}` : '.'}`
    messageError.value = true
  }
}
async function downloadAll() {
  bulkLoading.value = true
  try {
    const { data } = await descargarTodos(serie.value.id)
    for (const task of data.tasks || []) {
      const chapter = chapters.value.find(c => c.id === task.capitulo_id)
      downloads.addDownload(task.task_id, task.capitulo_id, serie.value.nombre, task.numero, () => { if (chapter) chapter.archivo_existe = true })
    }
    message.value = data.message; messageError.value = false
  } catch { message.value = 'No se pudieron iniciar las descargas.'; messageError.value = true }
  finally { bulkLoading.value = false }
}
onMounted(load)
useSpatialNavigation({ onBack: () => router.back() })
</script>

<style scoped>
.tv-chapters-page { min-height: 100vh; padding: 36px 54px 70px; background: linear-gradient(105deg, #07111f 25%, #102a45); }
.tv-chapters-hero { display: grid; grid-template-columns: auto 260px 1fr; align-items: start; gap: 34px; margin-bottom: 42px; }
.tv-chapters-hero > img { width: 260px; height: 340px; object-fit: cover; border-radius: 18px; }
.tv-chapters-info { align-self: center; max-width: 720px; }
.tv-chapters-info h1 { margin: 5px 0 13px; font-size: 48px; }
.tv-chapters-info > p { color: var(--tv-muted); font-size: 20px; }
.tv-chapters-info .eyebrow { color: var(--tv-yellow); font-weight: 800; letter-spacing: 2px; }
.tv-episodes h2 { font-size: 28px; }
.tv-episode-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.tv-episode { display: flex; align-items: center; gap: 15px; min-height: 86px; padding: 14px 16px; border: 0; border-radius: 14px; background: var(--tv-panel); color: white; text-align: left; cursor: pointer; }
.tv-episode-copy { min-width: 0; flex: 1; font-size: 19px; }
.tv-episode-action, .tv-episode-progress { color: var(--tv-yellow); font-size: 20px; font-weight: 800; }
.tv-episode-progress { min-width: 58px; text-align: right; font-variant-numeric: tabular-nums; }
</style>
