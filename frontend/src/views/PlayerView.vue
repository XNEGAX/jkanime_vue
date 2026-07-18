<template>
  <div v-if="capitulo">
    <div class="header-actions">
      <div>
        <router-link :to="{ name: 'chapters', params: { id: capitulo.serie_id } }" class="btn btn-secondary btn-sm" style="margin-right:12px;">
          Volver
        </router-link>
        <h2 style="display:inline">{{ capitulo.serie_nombre }}</h2>
      </div>
      <span style="color:#888;">Episodio {{ capitulo.numero }}</span>
    </div>

    <div class="player-wrapper" v-if="!videoLoading">
      <video
        ref="videoEl"
        id="player"
        controls
        autoplay
        preload="auto"
        playsinline
      >
        <source :src="videoUrl" type="video/mp4">
        Tu navegador no soporta video.
      </video>
    </div>

    <div class="player-wrapper player-loading" v-else>
      <span class="spinner"></span>
      <span>Cargando video...</span>
    </div>

    <div class="player-nav">
      <router-link
        v-if="capitulo.anterior_id"
        :to="{ name: 'player', params: { id: capitulo.anterior_id } }"
        class="btn btn-secondary"
      >
        &#9664; Anterior
      </router-link>
      <span v-else></span>

      <span style="color:#888;">{{ capitulo.nombre_archivo }}</span>

      <router-link
        v-if="capitulo.siguiente_id"
        :to="{ name: 'player', params: { id: capitulo.siguiente_id } }"
        class="btn btn-primary"
      >
        Siguiente &#9654;
      </router-link>
      <span v-else></span>
    </div>
  </div>

  <div v-else class="loading">
    <span class="spinner"></span> Cargando...
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { getCapituloDetail, getVideoUrl } from '../api'
import Plyr from 'plyr'
import 'plyr/dist/plyr.css'

const route = useRoute()
const capitulo = ref(null)
const videoEl = ref(null)
const videoLoading = ref(false)

const videoUrl = computed(() => capitulo.value ? getVideoUrl(capitulo.value.id) : '')

let player = null

function initPlayer() {
  if (player) {
    player.destroy()
    player = null
  }
  if (!videoEl.value) return

  player = new Plyr('#player', {
    controls: [
      'play-large',
      'play',
      'progress',
      'current-time',
      'duration',
      'mute',
      'volume',
      'captions',
      'settings',
      'pip',
      'fullscreen',
    ],
    settings: ['captions', 'quality', 'speed'],
    speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2] },
    keyboard: { focused: true, global: true },
    tooltips: { controls: true, seek: true },
    invertTime: false,
    toggleInvert: false,
    resetOnEnd: true,
    autoplay: true,
  })
}

onMounted(async () => {
  videoLoading.value = true
  try {
    const { data } = await getCapituloDetail(route.params.id)
    capitulo.value = data
    await nextTick()
    initPlayer()
  } finally {
    videoLoading.value = false
  }
})

onBeforeUnmount(() => {
  if (player) {
    player.destroy()
    player = null
  }
})

watch(() => route.params.id, async (newId) => {
  if (!newId) return
  videoLoading.value = true
  try {
    const { data } = await getCapituloDetail(newId)
    capitulo.value = data
    await nextTick()
    initPlayer()
  } finally {
    videoLoading.value = false
  }
})
</script>

<style scoped>
.player-wrapper {
  width: 100%;
  max-width: 1100px;
  margin: 0 auto 16px;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.player-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 400px;
  color: #888;
}

.player-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1100px;
  margin: 0 auto;
  padding: 8px 0;
}
</style>

<style>
:root {
  --plyr-color-main: #e94560;
  --plyr-video-background: #000;
  --plyr-font-family: inherit;
  --plyr-font-size-time: 14px;
  --plyr-font-size-menu: 14px;
  --plyr-control-icon-size: 20px;
  --plyr-control-spacing: 12px;
  --plyr-video-controls-background: linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0.85));
  --plyr-menu-color: #e0e0e0;
  --plyr-menu-background: #1a1a2e;
  --plyr-menu-border-color: #333;
  --plyr-menu-arrow-color: #e0e0e0;
}
</style>
