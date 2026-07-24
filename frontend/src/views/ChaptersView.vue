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
        :disabled="descargandoTodos || !capitulos.length || todosDescargados"
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
            <th style="width:140px">Reproducir</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="cap in capitulos" :key="cap.id">
            <td><strong>{{ cap.numero }}</strong></td>
            <td>
              {{ cap.nombre_archivo }}
              <span v-if="cap.ultimo_segundo > 30" class="resume-badge" title="Tienes progreso guardado">
                {{ formatSegundos(cap.ultimo_segundo) }}
              </span>
            </td>
            <td class="date-cell">{{ formatDate(cap.fecha_publicacion) }}</td>
            <td>
              <button
                class="btn btn-sm"
                :class="botonClase(cap)"
                :disabled="botonDeshabilitado(cap)"
                @click="handleClick(cap)"
              >
                {{ textoBoton(cap) }}
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
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSerieDetail, getCapitulos, descargarCapitulo, descargarTodos as apiDescargarTodos, verificarCapitulo, repararCapitulo as apiReparar, refrescarPortada as apiRefrescarPortada } from '../api'
import { useDownloadStore } from '../stores/downloads'
import { useFavoritesStore } from '../stores/favorites'
import VideoPlayerModal from '../components/VideoPlayerModal.vue'

const route = useRoute()
const router = useRouter()
const store = useDownloadStore()
const favStore = useFavoritesStore()

const serieId = computed(() => route.params.id)

const serie = ref(null)
const capitulos = ref([])
const totalJk = ref(0)
const nuevosEncontrados = ref(0)
const loading = ref(true)
const mensaje = ref('')
const mensajeTipo = ref('ok')
const descargandoTodos = ref(false)
const descargandoPortada = ref(false)
const playerCapituloId = ref(null)

// Estado de validacion de archivos (cap.id -> { verificando, corrupto, mensaje })
const validandoArchivos = reactive(new Map())
const corruptos = reactive(new Map())
const reparando = reactive(new Map())

const isFav = computed(() => serie.value ? favStore.isFavorito(serie.value.id) : false)
const todosDescargados = computed(() =>
  capitulos.value.length > 0 && capitulos.value.every(c => c.archivo_existe)
)

// --- Logica de boton por capitulo ---

function downloadInfo(cap) {
  return store.downloads.find(d => d.capituloId === cap.id)
}

function descargando(cap) {
  const dl = downloadInfo(cap)
  return dl && (dl.state === 'PROGRESS' || dl.state === 'PENDING')
}

function textoBoton(cap) {
  if (reparando.get(cap.id)) return 'Reparando...'
  if (corruptos.get(cap.id)?.corrupto) return 'Reparar'
  if (validandoArchivos.get(cap.id)) return 'Verificando...'
  if (cap.archivo_existe) return 'Reproducir'
  const dl = downloadInfo(cap)
  if (dl && dl.porcentaje != null && dl.state === 'PROGRESS') {
    return `Descargando ${dl.porcentaje}%`
  }
  if (dl && dl.state === 'PENDING') return 'Iniciando...'
  return 'Reproducir'
}

function botonClase(cap) {
  if (corruptos.get(cap.id)?.corrupto) return 'btn-danger'
  if (reparando.get(cap.id)) return 'btn-warning btn-downloading'
  if (cap.archivo_existe) return 'btn-success'
  if (descargando(cap)) return 'btn-primary btn-downloading'
  return 'btn-primary'
}

function botonDeshabilitado(cap) {
  if (reparando.get(cap.id)) return true
  if (validandoArchivos.get(cap.id)) return true
  const dl = downloadInfo(cap)
  return !cap.archivo_existe && dl && dl.state === 'PENDING'
}

async function handleClick(cap) {
  if (cap.archivo_existe) {
    // Si ya sabemos que esta corrupto, reparar directo
    if (corruptos.get(cap.id)?.corrupto) {
      await reparar(cap)
      return
    }
    // Validar el archivo antes de reproducir
    await verificarYReproducir(cap)
    return
  }
  const dl = downloadInfo(cap)
  if (dl && (dl.state === 'PROGRESS' || dl.state === 'PENDING')) return
  iniciarDescarga(cap)
}

async function verificarYReproducir(cap) {
  if (validandoArchivos.get(cap.id)) return
  validandoArchivos.set(cap.id, true)

  try {
    const { data } = await verificarCapitulo(cap.id)
    if (data.valido) {
      corruptos.delete(cap.id)
      reproducir(cap.id)
    } else {
      corruptos.set(cap.id, { corrupto: true, mensaje: data.mensaje || 'El archivo esta corrupto' })
      mensaje.value = `"${cap.nombre_archivo}" esta corrupto: ${data.mensaje}. Reparando...`
      mensajeTipo.value = 'error'
      // Reparar automaticamente
      await reparar(cap)
    }
  } catch (e) {
    mensaje.value = 'Error al verificar el archivo: ' + (e.response?.data?.error || e.message)
    mensajeTipo.value = 'error'
    // Si falla la verificacion, igual intentamos reproducir (puede funcionar)
    reproducir(cap.id)
  } finally {
    validandoArchivos.set(cap.id, false)
  }
}

async function reparar(cap) {
  if (reparando.get(cap.id)) return
  reparando.set(cap.id, true)

  try {
    const { data } = await apiReparar(cap.id)
    if (data.skip) {
      // El archivo era valido, reproducir
      corruptos.delete(cap.id)
      mensaje.value = ''
      mensajeTipo.value = 'ok'
      reproducir(cap.id)
      return
    }
    if (data.task_id) {
      mensaje.value = data.mensaje || `Re-descargando ${cap.nombre_archivo}...`
      mensajeTipo.value = 'ok'
      store.addDownload(data.task_id, cap.id, serie.value?.nombre || '', cap.numero, () => {
        cap.archivo_existe = true
        corruptos.delete(cap.id)
        reparando.delete(cap.id)
        mensaje.value = `${cap.nombre_archivo} reparado — reproduciendo`
        mensajeTipo.value = 'ok'
        setTimeout(() => { mensaje.value = '' }, 3000)
        reproducir(cap.id)
      })
    }
  } catch (e) {
    mensaje.value = 'Error al reparar: ' + (e.response?.data?.error || e.message)
    mensajeTipo.value = 'error'
    reparando.delete(cap.id)
  }
}

// --- Video ---

function reproducir(id) {
  playerCapituloId.value = id
}

// --- Navegacion ---

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

function formatSegundos(seg) {
  const m = Math.floor(seg / 60)
  const s = seg % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// --- Favoritos ---

async function toggleFav() {
  if (!serie.value) return
  const result = await favStore.toggle(serie.value.id)
  if (result !== null) {
    serie.value.favorito = result
  }
}

// --- Init ---

async function refrescarPortada() {
  if (!serie.value || descargandoPortada.value) return
  descargandoPortada.value = true
  try {
    const { data } = await apiRefrescarPortada(serie.value.id)
    if (data.portada_url) {
      serie.value.portada_url = data.portada_url
    }
  } catch (e) {
    // Silencioso — no mostrar error al usuario, ya se loguea en backend
    console.warn('No se pudo descargar la portada:', e.message)
  } finally {
    descargandoPortada.value = false
  }
}

async function cargarSerie() {
  const id = serieId.value
  if (!id) return
  loading.value = true
  serie.value = null
  capitulos.value = []
  mensaje.value = ''
  try {
    const [serieRes, capsRes] = await Promise.all([
      getSerieDetail(id),
      getCapitulos(id),
    ])
    serie.value = serieRes.data
    capitulos.value = capsRes.data.capitulos.sort((a, b) => b.numero - a.numero)
    totalJk.value = capsRes.data.total_fuente || capsRes.data.total_jk || 0
    nuevosEncontrados.value = capsRes.data.nuevos_encontrados

    // Si no tiene portada, intentar descargarla desde la fuente
    if (!serie.value.portada_url) {
      refrescarPortada()
    }
  } catch (e) {
    mensaje.value = 'Error: ' + e.message
    mensajeTipo.value = 'error'
  } finally {
    loading.value = false
  }
}

onMounted(cargarSerie)
watch(serieId, cargarSerie)

// --- Descargas ---

async function iniciarDescarga(cap, esReparacion = false) {
  try {
    const { data } = await descargarCapitulo(cap.id)
    if (data.task_id) {
      if (data.corrupto_reparado && !esReparacion) {
        mensaje.value = `"${cap.nombre_archivo}" estaba corrupto — descargando de nuevo...`
        mensajeTipo.value = 'error'
      }
      store.addDownload(data.task_id, cap.id, serie.value.nombre, cap.numero, () => {
        cap.archivo_existe = true
        corruptos.delete(cap.id)
        // Apenas termina, reproduce
        reproducir(cap.id)
      })
    } else if (data.skip) {
      cap.archivo_existe = true
      corruptos.delete(cap.id)
      reproducir(cap.id)
    }
  } catch (e) {
    mensaje.value = 'Error: ' + (e.response?.data?.error || e.message)
    mensajeTipo.value = 'error'
  }
}

async function descargarTodos() {
  descargandoTodos.value = true
  mensaje.value = ''
  try {
    const { data } = await apiDescargarTodos(serieId.value)
    if (data.tasks && data.tasks.length) {
      for (const t of data.tasks) {
        const cap = capitulos.value.find(c => c.id === t.capitulo_id)
        store.addDownload(t.task_id, t.capitulo_id, serie.value.nombre, t.numero, () => {
          if (cap) cap.archivo_existe = true
        })
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

.btn-downloading {
  animation: pulse-progress 1.5s infinite;
}

:deep(.btn-danger) {
  background: #e94560;
  color: #fff;
  border-color: #e94560;
}

:deep(.btn-warning) {
  background: #f39c12;
  color: #fff;
  border-color: #f39c12;
}

@keyframes pulse-progress {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.resume-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 10px;
  background: #1a3a1a;
  color: #27ae60;
  font-size: 0.7rem;
  font-weight: 600;
  vertical-align: middle;
}
</style>
