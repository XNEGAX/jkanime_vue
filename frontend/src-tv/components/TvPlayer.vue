<template>
  <div class="tv-player-overlay">
    <header class="tv-player-header" :class="{ hidden: !controlsVisible }">
      <div v-if="chapter">
        <strong>{{ chapter.serie_nombre }}</strong>
        <span>Episodio {{ chapter.numero }}</span>
      </div>
      <div class="tv-player-nav">
        <span class="tv-player-clock">{{ playerTime }}</span>
        <button v-if="chapter?.siguiente_id" class="tv-button tv-button--secondary" data-tv-focus @click="load(chapter.siguiente_id)">Siguiente</button>
      </div>
    </header>

    <video v-if="chapter" ref="video" :src="videoUrl" autoplay preload="auto" playsinline @timeupdate="onTimeUpdate" @play="isPlaying = true" @pause="onPause" @ended="onEnded" @error="onVideoError"></video>
    <div v-else class="tv-player-loading"><span class="tv-spinner"></span>Cargando episodio…</div>

    <div v-if="showResume" class="tv-player-dialog">
      <div>
        <h2>¿Continuar viendo?</h2>
        <p>Guardado en {{ formatTime(chapter.ultimo_segundo) }}</p>
        <div class="tv-actions">
          <button class="tv-button" data-tv-focus @click="resume">Continuar</button>
          <button class="tv-button tv-button--secondary" data-tv-focus @click="restart">Desde el inicio</button>
        </div>
      </div>
    </div>

    <footer class="tv-player-controls" :class="{ hidden: !controlsVisible }">
      <div class="tv-player-buttons">
        <button class="tv-player-control" data-tv-focus aria-label="Retroceder 10 segundos" @click="seek(-10)">−10 s</button>
        <button class="tv-player-control tv-player-control--play" data-tv-focus :aria-label="isPlaying ? 'Pausar' : 'Reproducir'" @click="togglePlay">{{ isPlaying ? '❚❚' : '▶' }}</button>
        <button class="tv-player-control" data-tv-focus aria-label="Adelantar 10 segundos" @click="seek(10)">+10 s</button>
        <button class="tv-player-control" data-tv-focus aria-label="Saltar 1 minuto y 26 segundos" @click="seek(86)">Saltar</button>
      </div>
      <span>{{ formatTime(currentTime) }}</span>
      <div class="tv-player-track"><span :style="{ width: progress + '%' }"></span></div>
      <span>{{ formatTime(duration) }}</span>
      <span class="tv-player-help">↑ controles · Atrás salir</span>
    </footer>

    <div v-if="error" class="tv-player-error">
      <p>{{ error }}</p>
      <button class="tv-button tv-button--danger" data-tv-focus :disabled="repairing" @click="repair">{{ repairing ? 'Reparando…' : 'Reparar y descargar' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getCapituloDetail, getVideoUrl, guardarProgreso, repararCapitulo } from '../../src/api'
import { useDownloadStore } from '../../src/stores/downloads'

const props = defineProps({ chapterId: { type: [String, Number], required: true } })
const emit = defineEmits(['close'])
const downloads = useDownloadStore()
const chapter = ref(null)
const video = ref(null)
const currentTime = ref(0)
const duration = ref(0)
const isPlaying = ref(false)
const playerTime = ref('')
const lastSaved = ref(0)
const controlsVisible = ref(true)
const showResume = ref(false)
const error = ref('')
const repairing = ref(false)
const closing = ref(false)
let controlsTimer
let clockTimer

function updatePlayerTime() {
  playerTime.value = new Date().toLocaleTimeString('es-CL', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

const videoUrl = computed(() => chapter.value ? getVideoUrl(chapter.value.id) : '')
const progress = computed(() => duration.value ? Math.min(100, currentTime.value * 100 / duration.value) : 0)

function formatTime(value = 0) {
  const total = Math.max(0, Math.floor(value || 0))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}` : `${minutes}:${String(seconds).padStart(2, '0')}`
}

async function load(id) {
  await saveNow()
  chapter.value = null
  error.value = ''
  showResume.value = false
  try {
    const { data } = await getCapituloDetail(id)
    chapter.value = data
    await nextTick()
    video.value?.load()
    if (data.ultimo_segundo > 30) {
      showResume.value = true
      await nextTick()
      focusPlayerButton('.tv-player-dialog [data-tv-focus]')
    } else video.value?.play().catch(() => {})
  } catch {
    error.value = 'No se pudo cargar el episodio.'
  }
}

function resume() {
  showResume.value = false
  if (video.value) video.value.currentTime = chapter.value.ultimo_segundo
  video.value?.play().catch(() => {})
}
function restart() {
  showResume.value = false
  if (video.value) video.value.currentTime = 0
  video.value?.play().catch(() => {})
}
function togglePlay() {
  if (!video.value || showResume.value) return
  video.value.paused ? video.value.play().catch(() => {}) : video.value.pause()
}
function seek(seconds) {
  if (!video.value) return
  video.value.currentTime = Math.max(0, Math.min(video.value.duration || Infinity, video.value.currentTime + seconds))
}
function showControls() {
  controlsVisible.value = true
  clearTimeout(controlsTimer)
  controlsTimer = setTimeout(() => {
    const playerButtonFocused = document.activeElement?.matches?.('.tv-player-overlay [data-tv-focus]')
    if (!playerButtonFocused) controlsVisible.value = false
  }, 3500)
}
function visiblePlayerButtons() {
  return [...document.querySelectorAll('.tv-player-overlay [data-tv-focus]:not([disabled])')]
    .filter(element => element.offsetParent !== null)
}
function focusPlayerButton(selector) {
  const element = selector ? document.querySelector(selector) : visiblePlayerButtons()[0]
  element?.focus({ preventScroll: true })
}
function movePlayerButton(direction, container) {
  const buttons = container
    ? [...container.querySelectorAll('[data-tv-focus]:not([disabled])')].filter(element => element.offsetParent !== null)
    : visiblePlayerButtons()
  if (!buttons.length) return
  const current = buttons.indexOf(document.activeElement)
  const delta = direction === 'next' ? 1 : -1
  const index = current < 0 ? 0 : (current + delta + buttons.length) % buttons.length
  buttons[index].focus({ preventScroll: true })
}
function onTimeUpdate() {
  currentTime.value = video.value?.currentTime || 0
  duration.value = video.value?.duration || 0
  if (Math.floor(currentTime.value) - lastSaved.value >= 10) saveNow()
}
function onPause() {
  isPlaying.value = false
  saveNow()
}
function onEnded() {
  isPlaying.value = false
  saveNow()
}
async function saveNow() {
  if (!chapter.value || !video.value) return
  const second = Math.floor(video.value.currentTime || 0)
  if (second === lastSaved.value) return
  lastSaved.value = second
  try { await guardarProgreso(chapter.value.id, second) } catch { /* sin bloquear reproducción */ }
}
function onVideoError() {
  error.value = 'El archivo no se puede reproducir o está dañado.'
}
async function repair() {
  if (!chapter.value || repairing.value) return
  repairing.value = true
  try {
    const { data } = await repararCapitulo(chapter.value.id)
    if (data.skip) return load(chapter.value.id)
    if (data.task_id) {
      downloads.addDownload(data.task_id, chapter.value.id, chapter.value.serie_nombre, chapter.value.numero, () => load(chapter.value.id))
      error.value = 'Descargando nuevamente. Puedes seguir el progreso en Descargas.'
    }
  } catch { error.value = 'No se pudo iniciar la reparación.' }
  finally { repairing.value = false }
}
async function close() {
  if (closing.value) return
  closing.value = true
  clearTimeout(controlsTimer)

  const element = video.value
  if (element) element.pause()
  await saveNow()

  // Libera explícitamente el stream antes de desmontar el reproductor.
  if (element) {
    element.removeAttribute('src')
    element.load()
  }
  emit('close')
}
function nativeBackHandler(event) { event.preventDefault(); close() }

function keyHandler(event) {
  if (!chapter.value) return
  const handled = ['Enter', ' ', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Escape', 'MediaPlayPause']
  if (!handled.includes(event.key)) return

  const buttonFocused = document.activeElement?.matches?.('.tv-player-overlay [data-tv-focus]')
  if (buttonFocused) {
    if (event.key === 'Enter' || event.key === ' ') {
      if (event.repeat) event.preventDefault()
      return
    }
    const activeContainer = document.activeElement.closest('.tv-player-header, .tv-player-controls, .tv-player-dialog, .tv-player-error')
    if (event.key === 'ArrowUp' && document.activeElement.closest('.tv-player-controls')) {
      event.preventDefault()
      event.stopImmediatePropagation()
      focusPlayerButton('.tv-player-header [data-tv-focus]')
      showControls()
      return
    }
    if (event.key === 'ArrowDown' && document.activeElement.closest('.tv-player-header')) {
      event.preventDefault()
      event.stopImmediatePropagation()
      focusPlayerButton('.tv-player-controls [data-tv-focus]')
      showControls()
      return
    }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      event.stopImmediatePropagation()
      movePlayerButton(event.key === 'ArrowRight' ? 'next' : 'previous', activeContainer)
      showControls()
      return
    }
    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
      event.preventDefault()
      event.stopImmediatePropagation()
      if (document.activeElement.closest('.tv-player-dialog, .tv-player-error')) {
        movePlayerButton(event.key === 'ArrowDown' ? 'next' : 'previous', activeContainer)
      }
      showControls()
      return
    }
  }

  event.preventDefault()
  event.stopImmediatePropagation()
  if (event.key === 'Enter' || event.key === ' ' || event.key === 'MediaPlayPause') togglePlay()
  else if (event.key === 'ArrowLeft') seek(-10)
  else if (event.key === 'ArrowRight') seek(10)
  else if (event.key === 'Escape') close()
  else if (event.key === 'ArrowUp') {
    showControls()
    focusPlayerButton('.tv-player-controls [data-tv-focus]')
  } else showControls()
  showControls()
}

onMounted(() => {
  updatePlayerTime()
  clockTimer = setInterval(updatePlayerTime, 30000)
  window.addEventListener('keydown', keyHandler, true)
  window.addEventListener('tv-back', nativeBackHandler)
  load(props.chapterId)
  showControls()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', keyHandler, true)
  window.removeEventListener('tv-back', nativeBackHandler)
  clearTimeout(controlsTimer)
  clearInterval(clockTimer)
  if (!closing.value) {
    video.value?.pause()
    saveNow()
  }
})
</script>

<style scoped>
.tv-player-overlay { position: fixed; inset: 0; z-index: 1000; background: #000; color: white; overflow: hidden; }
.tv-player-overlay video { width: 100vw; height: 100vh; object-fit: contain; }
.tv-player-header { position: absolute; inset: 0 0 auto; z-index: 5; display: flex; align-items: center; gap: 24px; padding: 24px 34px; background: linear-gradient(#000, transparent); transition: opacity .2s; }
.tv-player-header > div:nth-child(2) { display: grid; gap: 3px; font-size: 22px; }
.tv-player-header span { color: var(--tv-muted); font-size: 17px; }
.tv-player-nav { margin-left: auto; display: flex; gap: 12px; }
.tv-player-clock { min-width: 84px; align-self: center; text-align: center; font-size: 24px; font-weight: 800; font-variant-numeric: tabular-nums; }
.tv-player-controls { position: absolute; inset: auto 0 0; z-index: 5; display: flex; align-items: center; gap: 16px; padding: 50px 38px 28px; background: linear-gradient(transparent, #000); transition: opacity .2s; }
.tv-player-buttons { display: flex; align-items: center; gap: 10px; margin-right: 8px; }
.tv-player-control { min-width: 82px; height: 52px; padding: 0 16px; border: 0; border-radius: 13px; background: rgba(34, 58, 84, .94); color: white; font-size: 18px; font-weight: 800; cursor: pointer; }
.tv-player-control--play { min-width: 58px; width: 58px; padding: 0; border-radius: 50%; background: var(--tv-blue); font-size: 22px; }
.tv-player-track { flex: 1; height: 8px; overflow: hidden; border-radius: 9px; background: #435063; }
.tv-player-track span { display: block; height: 100%; background: var(--tv-yellow); }
.tv-player-help { margin-left: 18px; color: var(--tv-muted); }
.hidden { opacity: 0; pointer-events: none; }
.tv-player-loading, .tv-player-dialog { position: absolute; inset: 0; z-index: 4; display: flex; align-items: center; justify-content: center; gap: 20px; background: rgba(0,0,0,.76); font-size: 22px; }
.tv-player-dialog > div { padding: 34px; border-radius: 18px; background: var(--tv-panel); }
.tv-player-error { position: absolute; left: 50%; bottom: 100px; z-index: 10; transform: translateX(-50%); min-width: 520px; padding: 22px; border-radius: 15px; background: #441822; text-align: center; }
</style>
