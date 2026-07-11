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
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getCapituloDetail, getVideoUrl } from '../api'

const route = useRoute()
const capitulo = ref(null)
const videoEl = ref(null)
const videoLoading = ref(false)

const videoUrl = computed(() => capitulo.value ? getVideoUrl(capitulo.value.id) : '')

function keyHandler(e) {
  if (e.target.tagName === 'INPUT') return
  const v = videoEl.value
  if (!v) return
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
  videoLoading.value = true
  try {
    const { data } = await getCapituloDetail(id)
    capitulo.value = data
  } finally {
    videoLoading.value = false
  }
}

onMounted(() => {
  document.addEventListener('keydown', keyHandler)
  cargar(route.params.id)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', keyHandler)
})

watch(() => route.params.id, (newId) => {
  if (newId) cargar(newId)
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

video {
  width: 100%;
  display: block;
  max-height: 75vh;
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
