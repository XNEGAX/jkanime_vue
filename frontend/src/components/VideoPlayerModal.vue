<template>
  <Teleport to="body">
    <div class="vpm-overlay" @click.self="cerrar">
      <div class="vpm-container">
        <div class="vpm-header">
          <div class="vpm-info">
            <button class="vpm-back" @click="cerrar" title="Cerrar (Esc)">&larr; Volver</button>
            <span v-if="capitulo" class="vpm-title">{{ capitulo.serie_nombre }} — Ep. {{ capitulo.numero }}</span>
          </div>
          <div class="vpm-nav">
            <button
              v-if="capitulo?.anterior_id"
              class="vpm-nav-btn"
              @click="navegar(capitulo.anterior_id)"
              title="Anterior"
            >&#9664;&#9664;</button>
            <button
              v-if="capitulo?.siguiente_id"
              class="vpm-nav-btn"
              @click="navegar(capitulo.siguiente_id)"
              title="Siguiente"
            >&#9654;&#9654;</button>
          </div>
        </div>

        <div class="vpm-player-area">
          <div v-if="!capitulo || buffering" class="vpm-buffer-overlay">
            <span class="spinner"></span>
            <span>{{ !capitulo ? 'Cargando informacion...' : 'Cargando video...' }}</span>
          </div>

          <video
            v-if="capitulo"
            ref="videoEl"
            controls
            autoplay
            preload="auto"
            playsinline
            @waiting="buffering = true"
            @canplay="buffering = false"
            @canplaythrough="buffering = false"
            @error="onError"
          >
            <source :src="videoUrl" type="video/mp4">
          </video>
        </div>

        <div v-if="errorMsg" class="vpm-error">
          {{ errorMsg }}
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getCapituloDetail, getVideoUrl } from '../api'

const props = defineProps({
  capituloId: { type: [String, Number], required: true },
})

const emit = defineEmits(['close'])

const capitulo = ref(null)
const videoEl = ref(null)
const buffering = ref(true)
const errorMsg = ref('')
const loadingId = ref(null)

const videoUrl = computed(() => {
  if (!capitulo.value) return ''
  return getVideoUrl(capitulo.value.id)
})

function onError() {
  const v = videoEl.value
  if (!v) return
  const code = v.error ? v.error.code : -1
  if (code === 4) {
    errorMsg.value = 'El video no esta disponible o el formato no es compatible.'
  } else if (code === 3) {
    errorMsg.value = 'Error de decodificacion. Intenta de nuevo.'
  } else if (code === 2) {
    errorMsg.value = 'Error de red. Verifica la conexion.'
  } else if (code === 1) {
    errorMsg.value = 'Carga cancelada.'
  }
  buffering.value = false
}

function keyHandler(e) {
  if (e.target.tagName === 'INPUT') return
  const v = videoEl.value
  if (!v) return
  if (e.key === 'Escape') { e.preventDefault(); cerrar() }
  if (e.key === ' ') { e.preventDefault(); v.paused ? v.play() : v.pause() }
  if (e.key === 'ArrowLeft') { e.preventDefault(); v.currentTime = Math.max(0, v.currentTime - 10) }
  if (e.key === 'ArrowRight') { e.preventDefault(); v.currentTime = Math.min(v.duration, v.currentTime + 10) }
  if (e.key === 'f') {
    e.preventDefault()
    if (document.fullscreenElement) document.exitFullscreen()
    else v.requestFullscreen()
  }
}

async function cargar(id) {
  buffering.value = true
  errorMsg.value = ''
  loadingId.value = id
  try {
    const { data } = await getCapituloDetail(id)
    capitulo.value = data
    await nextTick()
    const v = videoEl.value
    if (v) {
      v.load()
      v.play().catch(() => {})
    }
  } catch {
    errorMsg.value = 'Error al cargar el capitulo.'
    capitulo.value = null
  } finally {
    if (loadingId.value === id) {
      buffering.value = false
    }
  }
}

function navegar(id) {
  cargar(id)
}

function cerrar() {
  emit('close')
}

watch(() => props.capituloId, (id) => {
  if (id) cargar(id)
}, { immediate: true })

onMounted(() => {
  document.addEventListener('keydown', keyHandler)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', keyHandler)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.vpm-overlay {
  position: fixed;
  inset: 0;
  background: #000;
  z-index: 5000;
  display: flex;
  flex-direction: column;
}

.vpm-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
}

.vpm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #111;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
  z-index: 10;
}

.vpm-info {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.vpm-back {
  background: #1a1a2e;
  color: #e94560;
  border: 1px solid #e94560;
  border-radius: 6px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
  transition: background 0.2s;
}

.vpm-back:hover {
  background: #e94560;
  color: #fff;
}

.vpm-title {
  color: #ccc;
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vpm-nav {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.vpm-nav-btn {
  background: #1a1a2e;
  color: #e94560;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.vpm-nav-btn:hover {
  border-color: #e94560;
  background: #222;
}

.vpm-player-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  position: relative;
  min-height: 0;
}

video {
  width: 100%;
  height: 100%;
  max-height: 100vh;
  display: block;
  object-fit: contain;
}

.vpm-buffer-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(0, 0, 0, 0.7);
  color: #888;
  z-index: 5;
  font-size: 0.95rem;
}

.vpm-error {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(233, 69, 96, 0.9);
  color: #fff;
  padding: 10px 20px;
  text-align: center;
  font-size: 0.85rem;
  z-index: 10;
}
</style>
