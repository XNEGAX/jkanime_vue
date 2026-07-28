<template>
  <div class="tv-shell">
    <div class="tv-app-clock">{{ time }}</div>
    <TvSidebar v-if="route.name !== 'tv-chapters'" />
    <main :class="['tv-main', { 'tv-main--full': route.name === 'tv-chapters' }]">
      <router-view />
    </main>
    <div v-if="downloads.hasActive" class="tv-download-pill">
      {{ downloads.activeCount }} descarga{{ downloads.activeCount === 1 ? '' : 's' }}
    </div>
    <div v-if="exitNotice" class="tv-exit-notice" role="alert">{{ exitNotice }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { App } from '@capacitor/app'
import TvSidebar from './components/TvSidebar.vue'
import { useDownloadStore } from '../src/stores/downloads'

const route = useRoute()
const router = useRouter()
const downloads = useDownloadStore()
let backListener
let clockTimer
let exitTimer
let lastBackAt = 0
const time = ref('')
const exitNotice = ref('')

function updateTime() {
  time.value = new Date().toLocaleTimeString('es-CL', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

onMounted(async () => {
  updateTime()
  clockTimer = setInterval(updateTime, 30000)
  downloads.restoreFromServer()
  backListener = await App.addListener('backButton', () => {
    const now = Date.now()
    if (now - lastBackAt <= 2000) {
      clearTimeout(exitTimer)
      exitNotice.value = 'Cerrando AnimeWing TV…'
      lastBackAt = 0
      setTimeout(() => App.exitApp(), 350)
      return
    }

    lastBackAt = now
    exitNotice.value = 'Presiona Atrás nuevamente para cerrar'
    clearTimeout(exitTimer)
    exitTimer = setTimeout(() => {
      exitNotice.value = ''
      lastBackAt = 0
    }, 2000)

    const event = new Event('tv-back', { cancelable: true })
    window.dispatchEvent(event)
    if (event.defaultPrevented) return
    if (route.path !== '/') router.back()
  })
})

onBeforeUnmount(() => {
  clearInterval(clockTimer)
  clearTimeout(exitTimer)
  backListener?.remove()
})
</script>
