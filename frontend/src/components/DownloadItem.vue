<template>
  <div class="download-item" :class="statusClass">
    <div class="item-header">
      <span class="item-serie">{{ download.serie }}</span>
      <span class="item-ep">Ep. {{ download.numero }}</span>
    </div>

    <div class="item-phase">{{ phaseText }}</div>

    <div class="progress-bar" v-if="download.state !== 'FAILURE'">
      <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
    </div>

    <div class="item-details">
      <span v-if="download.state === 'PROGRESS'">
        {{ download.descargado_str || '0 B' }} / {{ download.total_str || '?' }}
        ({{ download.porcentaje || 0 }}%)
      </span>
      <span v-else-if="download.state === 'SUCCESS'" class="text-success">
        Completado
      </span>
      <span v-else-if="download.state === 'FAILURE'" class="text-error">
        {{ download.message || 'Error' }}
      </span>
      <span v-else class="text-muted">En cola...</span>

      <span v-if="download.servidor" class="item-server">
        {{ download.servidor }}
      </span>
    </div>

    <div class="item-actions">
      <button
        v-if="download.state === 'PENDING' || download.state === 'PROGRESS'"
        class="btn-cancel"
        @click="cancelar"
        title="Cancelar descarga"
      >&#10005;</button>
      <button
        v-else
        class="btn-remove"
        @click="store.removeDownload(download.taskId)"
      >&#10005;</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDownloadStore } from '../stores/downloads'

const props = defineProps({
  download: { type: Object, required: true },
})

const store = useDownloadStore()

const statusClass = computed(() => {
  if (props.download.state === 'SUCCESS') return 'status-success'
  if (props.download.state === 'FAILURE') return 'status-failure'
  return ''
})

const progressPercent = computed(() => {
  if (props.download.state === 'SUCCESS') return 100
  return props.download.porcentaje || 0
})

const phaseText = computed(() => {
  const d = props.download
  if (d.state === 'PENDING') return 'En cola...'
  if (d.state === 'SUCCESS') return 'Descarga completada'
  if (d.state === 'FAILURE') return 'Error en la descarga'
  if (d.fase === 'buscando_servidores') return 'Buscando servidores...'
  if (d.fase === 'completado_ep') return 'Capitulo completado'
  return 'Descargando...'
})

function cancelar() {
  store.cancelDownload(props.download.taskId)
}
</script>

<style scoped>
.download-item {
  background: #222;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  position: relative;
  border: 1px solid #333;
  transition: opacity 0.3s;
}

.download-item.status-success {
  border-color: #27ae60;
}

.download-item.status-failure {
  border-color: #e94560;
  opacity: 0.7;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  padding-right: 24px;
}

.item-serie {
  font-weight: 600;
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.item-ep {
  color: #888;
  font-size: 0.8rem;
}

.item-phase {
  color: #888;
  font-size: 0.75rem;
  margin-bottom: 6px;
}

.item-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 0.8rem;
}

.item-server {
  color: #555;
  font-size: 0.7rem;
}

.text-success { color: #27ae60; }
.text-error { color: #e94560; }
.text-muted { color: #555; }

.item-actions {
  position: absolute;
  top: 8px;
  right: 8px;
}

.btn-cancel, .btn-remove {
  background: none;
  border: none;
  color: #888;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 4px;
}

.btn-cancel:hover {
  color: #e94560;
}

.btn-remove:hover {
  color: #e94560;
}
</style>
