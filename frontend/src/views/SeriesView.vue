<template>
  <div>
    <div class="header-actions">
      <h2>Series Disponibles</h2>
      <div class="header-right">
        <span v-if="verificando" class="auto-refresh">
          <span class="spinner-sm"></span> Buscando actualizaciones...
          <span v-if="verificarDetalle" class="verificar-detail">{{ verificarDetalle }}</span>
        </span>
      </div>
    </div>

    <div v-if="mensaje" :class="['alert', mensajeTipo === 'ok' ? 'alert-success' : 'alert-error']">
      {{ mensaje }}
    </div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Cargando series...
    </div>

    <template v-else-if="series.length">
      <div v-for="grupo in gruposPorDia" :key="grupo.dia" class="dia-group">
        <div class="dia-group-header">
          <span class="dia-group-name">{{ grupo.dia === 'sin_dia' ? 'Sin dia definido' : capitalize(grupo.dia) }}</span>
          <span class="dia-group-count">{{ grupo.series.length }}</span>
        </div>
        <table>
          <thead>
            <tr>
              <th style="width:50px"></th>
              <th style="width:80px">Portada</th>
          <th>Nombre</th>
          <th style="width:100px">Estado</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="serie in grupo.series"
              :key="serie.id"
              class="serie-row"
              @click="router.push({ name: 'chapters', params: { id: serie.id } })"
            >
              <td>
                <button
                  class="fav-btn"
                  :class="{ active: favStore.isFavorito(serie.id) }"
                  @click.stop="toggleFav(serie)"
                  :title="favStore.isFavorito(serie.id) ? 'Quitar de favoritos' : 'Agregar a favoritos'"
                >
                  &#9829;
                </button>
              </td>
              <td>
                <img
                  v-if="serie.portada_url"
                  :src="serie.portada_url"
                  :alt="serie.nombre"
                  class="cover-img"
                />
                <div v-else class="cover-placeholder">Sin portada</div>
              </td>
              <td><strong>{{ serie.nombre }}</strong></td>
          <td>
            <span :class="['estado-badge', 'estado-' + serie.estado]">
              {{ serie.estado === 'en_emision' ? 'En emisión' : serie.estado === 'concluido' ? 'Concluido' : 'Desconocido' }}
            </span>
          </td>
        </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-else class="loading" style="color:#666;">
      {{ searchQuery ? 'No se encontraron series para "' + searchQuery + '"' : 'No hay series registradas.' }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getSeries, verificarSeries, getVerificarStatus } from '../api'
import { useFavoritesStore } from '../stores/favorites'

const router = useRouter()
const route = useRoute()
const favStore = useFavoritesStore()

const series = ref([])
const loading = ref(true)
const verificando = ref(false)
const verificarDetalle = ref('')
const verificarNuevas = ref(0)
const verificarActualizadas = ref(0)
const mensaje = ref('')
const mensajeTipo = ref('ok')
const searchQuery = ref('')

const DIA_ORDEN = ['domingo', 'sabado', 'viernes', 'jueves', 'miercoles', 'martes', 'lunes', 'sin_dia']
const DOS_SEMANAS = 14 * 24 * 60 * 60 * 1000

const seriesVisibles = computed(() => {
  const ahora = Date.now()
  return series.value.filter(s => {
    if (s.estado === 'concluido') return false
    if (s.latest_fecha && (ahora - new Date(s.latest_fecha).getTime()) > DOS_SEMANAS) return false
    return true
  })
})

const gruposPorDia = computed(() => {
  const map = {}
  for (const s of seriesVisibles.value) {
    const dia = s.dia_emision || 'sin_dia'
    if (!map[dia]) map[dia] = []
    map[dia].push(s)
  }

  const grupos = []
  for (const dia of DIA_ORDEN) {
    if (map[dia] && map[dia].length) {
      map[dia].sort((a, b) => {
        if (!a.latest_fecha) return 1
        if (!b.latest_fecha) return -1
        return new Date(b.latest_fecha) - new Date(a.latest_fecha)
      })
      grupos.push({ dia, series: map[dia] })
    }
  }
  return grupos
})

async function cargarSeries(search = '') {
  loading.value = true
  try {
    const { data } = await getSeries(search)
    series.value = data
    favStore.loadFromSeries(data)
  } catch (e) {
    mensaje.value = 'Error cargando series: ' + e.message
    mensajeTipo.value = 'error'
  } finally {
    loading.value = false
  }
}

let verificarTimer = null

async function iniciarVerificacion() {
  try {
    const { data } = await verificarSeries()
    if (data.status === 'started' || data.status === 'already_running') {
      verificando.value = true
      verificarDetalle.value = data.mensaje || 'Iniciando...'
      pollVerificacion(data.task_id)
    }
  } catch {
    // silently fail
  }
}

function pollVerificacion(taskId) {
  if (verificarTimer) clearInterval(verificarTimer)
  verificarTimer = setInterval(async () => {
    try {
      const { data } = await getVerificarStatus()
      if (data.state === 'PROGRESS') {
        verificarDetalle.value = data.mensaje || ''
        verificarNuevas.value = data.nuevas || 0
        verificarActualizadas.value = data.actualizadas || 0
      } else if (data.state === 'SUCCESS') {
        verificando.value = false
        clearInterval(verificarTimer)
        verificarTimer = null
        verificarNuevas.value = data.nuevas || 0
        verificarActualizadas.value = data.actualizadas || 0
        if (data.nuevas > 0 || data.actualizadas > 0) {
          const { data: updated } = await getSeries(searchQuery.value)
          series.value = updated
          favStore.loadFromSeries(updated)
        }
      } else if (data.state === 'FAILURE' || data.state === 'NONE') {
        verificando.value = false
        clearInterval(verificarTimer)
        verificarTimer = null
      }
    } catch {
      verificando.value = false
      clearInterval(verificarTimer)
      verificarTimer = null
    }
  }, 2000)
}

onMounted(async () => {
  searchQuery.value = route.query.search || ''
  await cargarSeries(searchQuery.value)

  // Check if a verification task is already running
  try {
    const { data } = await getVerificarStatus()
    if (data.state === 'PENDING' || data.state === 'PROGRESS') {
      verificando.value = true
      verificarDetalle.value = data.mensaje || 'En cola...'
      pollVerificacion(data.task_id)
    } else {
      iniciarVerificacion()
    }
  } catch {
    iniciarVerificacion()
  }
})

watch(() => route.query.search, (val) => {
  searchQuery.value = val || ''
  cargarSeries(searchQuery.value)
})

async function toggleFav(serie) {
  const result = await favStore.toggle(serie.id)
  if (result !== null) {
    serie.favorito = result
  }
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1)
}
</script>

<style scoped>
.dia-group {
  margin-bottom: 28px;
}

.dia-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 2px solid #e94560;
}

.dia-group-name {
  font-size: 1.1rem;
  font-weight: 700;
  color: #e94560;
  text-transform: capitalize;
}

.dia-group-count {
  background: #1a1a2e;
  color: #888;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

.serie-row { cursor: pointer; }
.cover-img { width: 80px; height: 60px; object-fit: cover; border-radius: 4px; }
.cover-placeholder {
  width: 80px; height: 60px; background: #2a2a2a;
  display: flex; align-items: center; justify-content: center;
  border-radius: 4px; color: #555; font-size: 0.7rem;
}
.alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 0.9rem; }
.alert-success { background: #1a3a1a; border: 1px solid #27ae60; color: #27ae60; }
.alert-error { background: #3a1a1a; border: 1px solid #e94560; color: #e94560; }

.fav-btn {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: #444;
  transition: all 0.2s;
  padding: 4px;
  line-height: 1;
}

.fav-btn:hover {
  color: #e94560;
  transform: scale(1.2);
}

.fav-btn.active {
  color: #e94560;
}

.estado-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

.estado-en_emision {
  background: #1a2a3a;
  color: #3498db;
}

.estado-concluido {
  background: #1a3a1a;
  color: #27ae60;
}

.estado-desconocido {
  background: #2a2a2a;
  color: #888;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.auto-refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #888;
  font-size: 0.8rem;
}

.verificar-detail {
  color: #aaa;
  font-size: 0.75rem;
  margin-left: 4px;
  opacity: 0.8;
}

.spinner-sm {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #333;
  border-top-color: #e94560;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
