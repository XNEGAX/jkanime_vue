<template>
  <div>
    <header class="tv-page-header"><div><h1>Descargas</h1><p>{{ downloads.activeCount }} activas</p></div></header>
    <div v-if="!downloads.downloads.length" class="tv-empty">No hay descargas en esta sesión</div>
    <div v-else class="tv-download-list">
      <article v-for="item in downloads.downloads" :key="item.taskId" class="tv-download-item">
        <div class="tv-download-icon">{{ item.state === 'SUCCESS' ? '✓' : item.state === 'FAILURE' ? '!' : '⇩' }}</div>
        <div class="tv-download-data">
          <div><strong>{{ item.serie || 'Serie' }} · Episodio {{ item.numero || '—' }}</strong><span>{{ stateLabel(item) }}</span></div>
          <div class="tv-download-bar"><span :style="{ width: progress(item) + '%' }"></span></div>
          <small>{{ item.descargado_str || '0 B' }} / {{ item.total_str || '?' }} <template v-if="item.servidor">· {{ item.servidor }}</template></small>
        </div>
        <button v-if="['PENDING', 'PROGRESS'].includes(item.state)" class="tv-button tv-button--danger" data-tv-focus @click="downloads.cancelDownload(item.taskId)">Cancelar</button>
        <button v-else class="tv-button tv-button--secondary" data-tv-focus @click="downloads.removeDownload(item.taskId)">Quitar</button>
      </article>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useDownloadStore } from '../../src/stores/downloads'
import { useSpatialNavigation } from '../composables/useSpatialNavigation'
const router = useRouter(); const downloads = useDownloadStore()
function progress(item) { return item.state === 'SUCCESS' ? 100 : Number(item.porcentaje || 0) }
function stateLabel(item) {
  if (item.state === 'PENDING') return 'En cola'
  if (item.state === 'SUCCESS') return 'Completado'
  if (item.state === 'FAILURE') return item.message || 'Falló'
  return item.fase === 'buscando_servidores' ? 'Buscando servidor' : `Descargando ${progress(item)}%`
}
useSpatialNavigation({ onBack: () => router.push('/') })
</script>

<style scoped>
.tv-download-list { display: grid; gap: 18px; }
.tv-download-item { display: flex; align-items: center; gap: 22px; padding: 22px; border-radius: 16px; background: var(--tv-panel); }
.tv-download-icon { width: 60px; height: 60px; display: grid; place-items: center; border-radius: 15px; background: var(--tv-panel-2); color: var(--tv-yellow); font-size: 28px; font-weight: 900; }
.tv-download-data { min-width: 0; flex: 1; display: grid; gap: 9px; }
.tv-download-data > div:first-child { display: flex; justify-content: space-between; font-size: 19px; }
.tv-download-data span, .tv-download-data small { color: var(--tv-muted); }
.tv-download-bar { height: 8px; overflow: hidden; border-radius: 8px; background: #29445f; }
.tv-download-bar span { display: block; height: 100%; background: var(--tv-yellow); }
</style>
