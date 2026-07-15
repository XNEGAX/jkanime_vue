<template>
  <div>
    <div class="header-actions">
      <div>
        <button class="btn btn-secondary btn-sm" style="margin-right:12px;" @click="volver">Volver</button>
        <h2 style="display:inline">{{ serie?.nombre || 'Cargando...' }}</h2>
        <button
          v-if="serie"
          class="fav-btn-inline"
          :class="{ active: isFav }"
          @click="toggleFav"
          :title="isFav ? 'Quitar de favoritos' : 'Agregar a favoritos'"
        >
          &#9829;
        </button>
      </div>
      <button
        class="btn btn-success"
        @click="descargarTodos"
        :disabled="descargandoTodos || !capitulos.length"
      >
        {{ descargandoTodos ? 'Descargando...' : 'Descargar todos' }}
      </button>
    </div>

    <div v-if="mensaje" :class="['alert', mensajeTipo === 'ok' ? 'alert-success' : 'alert-error']">
      {{ mensaje }}
    </div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Verificando episodios...
    </div>

    <template v-else>
      <div class="serie-info" v-if="serie">
        <img v-if="serie.portada_url" :src="serie.portada_url" class="cover-large" />
        <div class="info-text">
          <p><strong>Total en JKanime:</strong> {{ totalJk }} episodios</p>
          <p><strong>Registrados:</strong> {{ capitulos.length }}</p>
          <p><strong>Nuevos encontrados:</strong> {{ nuevosEncontrados }}</p>
        </div>
      </div>

      <table v-if="capitulos.length">
        <thead>
          <tr>
            <th style="width:80px">Ep.</th>
            <th>Nombre del archivo</th>
            <th style="width:150px">Publicado</th>
            <th style="width:100px">Estado</th>
            <th style="width:140px">Accion</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="cap in capitulos" :key="cap.id">
            <td><strong>{{ cap.numero }}</strong></td>
            <td>{{ cap.nombre_archivo }}</td>
            <td class="date-cell">{{ formatDate(cap.fecha_publicacion) }}</td>
            <td>
              <span :class="['status-badge', cap.archivo_existe ? 'badge-ok' : 'badge-pending']">
                {{ cap.archivo_existe ? 'Descargado' : 'Pendiente' }}
              </span>
            </td>
            <td>
              <button
                v-if="cap.archivo_existe"
                class="btn btn-success btn-sm"
                @click="reproducir(cap.id)"
              >
                Reproducir
              </button>
              <button
                v-else
                class="btn btn-primary btn-sm"
                @click="iniciarDescarga(cap)"
                :disabled="cap._downloading"
              >
                {{ cap._downloading ? 'Descargando...' : 'Descargar' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>

    <VideoPlayerModal
      v-if="playerCapituloId"
      :capituloId="playerCapituloId"
      @close="playerCapituloId = null"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSerieDetail, getCapitulos, descargarCapitulo, descargarTodos as apiDescargarTodos } from '../api'
import { useDownloadStore } from '../stores/downloads'
import { useFavoritesStore } from '../stores/favorites'
import VideoPlayerModal from '../components/VideoPlayerModal.vue'

const route = useRoute()
const router = useRouter()
const store = useDownloadStore()
const favStore = useFavoritesStore()
const serieId = route.params.id

const serie = ref(null)
const capitulos = ref([])
const totalJk = ref(0)
const nuevosEncontrados = ref(0)
const loading = ref(true)
const mensaje = ref('')
const mensajeTipo = ref('ok')
const descargandoTodos = ref(false)
const playerCapituloId = ref(null)

const isFav = computed(() => serie.value ? favStore.isFavorito(serie.value.id) : false)

function reproducir(id) {
  playerCapituloId.value = id
}

function volver() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/')
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '-'
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

async function toggleFav() {
  if (!serie.value) return
  const result = await favStore.toggle(serie.value.id)
  if (result !== null) {
    serie.value.favorito = result
  }
}

onMounted(async () => {
  try {
    const [serieRes, capsRes] = await Promise.all([
      getSerieDetail(serieId),
      getCapitulos(serieId),
    ])
    serie.value = serieRes.data
    capitulos.value = capsRes.data.capitulos.map(c => ({ ...c, _downloading: false })).sort((a, b) => b.numero - a.numero)
    totalJk.value = capsRes.data.total_jk
    nuevosEncontrados.value = capsRes.data.nuevos_encontrados
  } catch (e) {
    mensaje.value = 'Error: ' + e.message
    mensajeTipo.value = 'error'
  } finally {
    loading.value = false
  }
})

async function iniciarDescarga(cap) {
  cap._downloading = true
  try {
    const { data } = await descargarCapitulo(cap.id)
    if (data.task_id) {
      store.addDownload(data.task_id, cap.id, serie.value.nombre, cap.numero, () => {
        cap.archivo_existe = true
        cap._downloading = false
      })
    } else if (data.skip) {
      cap.archivo_existe = true
    }
  } catch (e) {
    mensaje.value = 'Error: ' + (e.response?.data?.error || e.message)
    mensajeTipo.value = 'error'
  } finally {
    if (!store.downloads.find(d => d.capituloId === cap.id)) {
      cap._downloading = false
    }
  }
}

async function descargarTodos() {
  descargandoTodos.value = true
  mensaje.value = ''
  try {
    const { data } = await apiDescargarTodos(serieId)
    if (data.tasks && data.tasks.length) {
      for (const t of data.tasks) {
        const cap = capitulos.value.find(c => c.id === t.capitulo_id)
        store.addDownload(t.task_id, t.capitulo_id, serie.value.nombre, t.numero, () => {
          if (cap) {
            cap.archivo_existe = true
            cap._downloading = false
          }
        })
        if (cap) cap._downloading = true
      }
      store.drawerOpen = true
      mensaje.value = data.message
      mensajeTipo.value = 'ok'
    } else {
      mensaje.value = data.message || 'No hay capitulos para descargar'
      mensajeTipo.value = 'ok'
    }
  } catch (e) {
    mensaje.value = 'Error: ' + (e.response?.data?.error || e.message)
    mensajeTipo.value = 'error'
  } finally {
    descargandoTodos.value = false
  }
}
</script>

<style scoped>
.serie-info {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
  align-items: flex-start;
}
.cover-large { width: 200px; border-radius: 8px; object-fit: cover; }
.info-text { color: #888; }
.info-text p { margin-bottom: 4px; }
.alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 0.9rem; }
.alert-success { background: #1a3a1a; border: 1px solid #27ae60; color: #27ae60; }
.alert-error { background: #3a1a1a; border: 1px solid #e94560; color: #e94560; }

.fav-btn-inline {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: #444;
  transition: all 0.2s;
  padding: 4px 8px;
  line-height: 1;
  vertical-align: middle;
}

.fav-btn-inline:hover {
  color: #e94560;
  transform: scale(1.2);
}

.fav-btn-inline.active {
  color: #e94560;
}

.date-cell {
  color: #888;
  font-size: 0.8rem;
}
</style>
