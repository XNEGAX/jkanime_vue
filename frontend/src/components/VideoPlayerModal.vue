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

          <!-- Overlay de reanudar -->
          <div v-if="showResume" class="vpm-resume-overlay">
            <div class="vpm-resume-box">
              <span class="vpm-resume-icon">&#9654;</span>
              <span class="vpm-resume-text">Continuar desde {{ formatoSegundos(capitulo.ultimo_segundo) }}</span>
              <button class="vpm-resume-btn" @click="reanudar">Continuar</button>
              <button class="vpm-resume-btn secondary" @click="showResume = false">Empezar desde inicio</button>
            </div>
          </div>

          <button
            v-if="capitulo && !showResume"
            class="vpm-skip-op"
            @click="saltarOpening"
            title="Saltar opening (S)"
          >Saltar OP</button>

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
            @timeupdate="onTimeUpdate"
            @pause="guardarProgresoAhora"
            @error="onError"
          >
            <source :src="videoUrl" type="video/mp4">
          </video>
        </div>

        <div v-if="errorMsg" class="vpm-error">
          <span>{{ errorMsg }}</span>
          <button
            v-if="errorEsReparable && !reparandoVideo"
            class="vpm-repair-btn"
            @click="repararVideo"
          >Reparar y re-descargar</button>
          <span v-if="reparandoVideo" class="vpm-repair-spinner">
            <span class="spinner"></span> Reparando...
          </span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getCapituloDetail, getVideoUrl, guardarProgreso, repararCapitulo, descargarCapitulo } from '../api'
import { useDownloadStore } from '../stores/downloads'

const props = defineProps({
  capituloId: { type: [String, Number], required: true },
})

const emit = defineEmits(['close'])

const capitulo = ref(null)
const videoEl = ref(null)
const buffering = ref(true)
const errorMsg = ref('')
const loadingId = ref(null)
const showResume = ref(false)
const ultimoGuardado = ref(0)
const reparandoVideo = ref(false)
const errorEsReparable = ref(false)

const store = useDownloadStore()

const videoUrl = computed(() => {
  if (!capitulo.value) return ''
  return getVideoUrl(capitulo.value.id)
})

function formatoSegundos(seg) {
  const m = Math.floor(seg / 60)
  const s = seg % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// --- Progreso ---

function onTimeUpdate() {
  const v = videoEl.value
  if (!v || !capitulo.value) return

  // Cada 10 segundos, guarda
  const ahora = Math.floor(v.currentTime)
  if (ahora - ultimoGuardado.value >= 10) {
    guardarProgresoAhora()
  }
}

async function guardarProgresoAhora() {
  const v = videoEl.value
  if (!v || !capitulo.value) return
  const seg = Math.floor(v.currentTime)
  if (seg === ultimoGuardado.value) return
  ultimoGuardado.value = seg
  try {
    await guardarProgreso(capitulo.value.id, seg)
  } catch {
    // silencioso
  }
}

function guardarProgresoBeacon() {
  const c = capitulo.value
  const v = videoEl.value
  if (!c || !v) return
  const seg = Math.floor(v.currentTime)
  if (seg > 0) {
    const blob = new Blob([JSON.stringify({ segundo: seg })], { type: 'application/json' })
    navigator.sendBeacon(`/api/capitulos/${c.id}/progreso/`, blob)
  }
}

// --- Reanudar ---

function reanudar() {
  showResume.value = false
  const v = videoEl.value
  if (v && capitulo.value?.ultimo_segundo) {
    v.currentTime = capitulo.value.ultimo_segundo
  }
}

// --- Saltar opening ---

function saltarOpening() {
  const v = videoEl.value
  if (!v) return
  v.currentTime = Math.min(v.duration || Infinity, v.currentTime + 90)
}

// --- Video error ---

function onError() {
  const v = videoEl.value
  if (!v) return
  const code = v.error ? v.error.code : -1
  if (code === 4) {
    errorMsg.value = 'El video no esta disponible o el formato no es compatible.'
    errorEsReparable.value = false
  } else if (code === 3) {
    errorMsg.value = 'Error de decodificacion — el archivo podria estar corrupto.'
    errorEsReparable.value = true
  } else if (code === 2) {
    errorMsg.value = 'Error de red. Verifica la conexion.'
    errorEsReparable.value = false
  } else if (code === 1) {
    errorMsg.value = 'Carga cancelada.'
    errorEsReparable.value = false
  }
  buffering.value = false
}

async function repararVideo() {
  if (!capitulo.value || reparandoVideo.value) return
  reparandoVideo.value = true
  errorMsg.value = 'Reparando archivo...'
  errorEsReparable.value = false

  try {
    const { data } = await repararCapitulo(capitulo.value.id)
    if (data.skip) {
      errorMsg.value = ''
      reparandoVideo.value = false
      recargarVideo()
      return
    }
    if (data.task_id) {
      errorMsg.value = `Re-descargando ${capitulo.value.nombre_archivo}...`
      capitulo.value.archivo_existe = false
      store.addDownload(data.task_id, capitulo.value.id, capitulo.value.serie_nombre, capitulo.value.numero, () => {
        capitulo.value.archivo_existe = true
        reparandoVideo.value = false
        errorMsg.value = 'Archivo reparado — recargando...'
        setTimeout(() => recargarVideo(), 500)
      })
    }
  } catch (e) {
    errorMsg.value = 'Error al reparar: ' + (e.response?.data?.error || e.message)
    reparandoVideo.value = false
    errorEsReparable.value = true
  }
}

function recargarVideo() {
  errorMsg.value = ''
  reparandoVideo.value = false
  errorEsReparable.value = false
  const v = videoEl.value
  if (v) {
    v.load()
    v.play().catch(() => {})
  }
}

// --- Teclado ---

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
  if (e.key === 's' || e.key === 'S') {
    e.preventDefault()
    saltarOpening()
  }
}

// --- Cargar capitulo ---

async function cargar(id) {
  buffering.value = true
  errorMsg.value = ''
  showResume.value = false
  ultimoGuardado.value = 0
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
    // Mostrar reanudar si tiene progreso significativo (>30s)
    if (data.ultimo_segundo > 30) {
      showResume.value = true
      buffering.value = false
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
  guardarProgresoAhora()
  emit('close')
}

watch(() => props.capituloId, (id) => {
  if (id) cargar(id)
}, { immediate: true })

onMounted(() => {
  document.addEventListener('keydown', keyHandler)
  document.body.style.overflow = 'hidden'
  window.addEventListener('beforeunload', guardarProgresoBeacon)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', keyHandler)
  document.body.style.overflow = ''
  window.removeEventListener('beforeunload', guardarProgresoBeacon)
  guardarProgresoAhora()
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
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

.vpm-repair-btn {
  background: #fff;
  color: #e94560;
  border: none;
  border-radius: 6px;
  padding: 5px 14px;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
  white-space: nowrap;
}

.vpm-repair-btn:hover {
  opacity: 0.85;
}

.vpm-repair-spinner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
}

/* --- Reanudar --- */

.vpm-resume-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
  z-index: 8;
}

.vpm-resume-box {
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 12px;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  max-width: 320px;
}

.vpm-resume-icon {
  font-size: 2rem;
  color: #e94560;
}

.vpm-resume-text {
  color: #ccc;
  font-size: 1rem;
  text-align: center;
}

.vpm-resume-btn {
  background: #e94560;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 24px;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  width: 100%;
  transition: background 0.2s;
}

.vpm-resume-btn:hover {
  background: #d63850;
}

.vpm-resume-btn.secondary {
  background: transparent;
  border: 1px solid #555;
  color: #888;
}

.vpm-resume-btn.secondary:hover {
  border-color: #e94560;
  color: #e94560;
}

/* --- Saltar OP --- */

.vpm-skip-op {
  position: absolute;
  bottom: 80px;
  right: 20px;
  background: rgba(233, 69, 96, 0.85);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px 18px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  z-index: 6;
  transition: background 0.2s;
  backdrop-filter: blur(4px);
}

.vpm-skip-op:hover {
  background: #e94560;
}
</style>
