<template>
  <div>
    <div class="header-actions">
      <h2><span class="fav-icon">&#9829;</span> Mis Favoritos</h2>
      <div class="header-right" v-if="!loading">
        <div class="search-box" v-if="series.length">
          <span class="search-icon">&#128269;</span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Buscar favorito..."
            class="search-input"
          />
          <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">&#10005;</button>
        </div>
        <button class="btn btn-secondary" @click="showUrlModal = true">
          + Agregar por URL
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Cargando favoritos...
    </div>

    <template v-else-if="series.length">
      <div v-if="!gruposPaginados.length" class="loading" style="color:#666;">
        No se encontraron favoritos para "{{ searchQuery }}"
      </div>

      <template v-else>
        <div v-for="grupo in gruposPaginados" :key="grupo.dia" class="dia-group">
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
                <th style="width:100px">Capitulos</th>
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
                    @click.stop="quitarFavorito(serie)"
                    title="Quitar de favoritos"
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
                <td>
                  <span class="badge-ok" v-if="serie.descargados_count">{{ serie.descargados_count }}/{{ serie.capitulos_count }}</span>
                  <span class="badge-pending" v-else>{{ serie.capitulos_count }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="pagination" v-if="totalPaginas > 1">
          <button class="page-btn" :disabled="pagina === 1" @click="pagina = 1">&laquo;</button>
          <button class="page-btn" :disabled="pagina === 1" @click="pagina--">&lsaquo;</button>
          <template v-for="p in paginasVisibles" :key="p.dia || p.num">
            <span v-if="p.dots" class="page-dots">...</span>
            <button
              v-else
              class="page-btn"
              :class="{ active: p.num === pagina, today: p.isToday }"
              @click="pagina = p.num"
            >{{ p.label }}</button>
          </template>
          <button class="page-btn" :disabled="pagina === totalPaginas" @click="pagina++">&rsaquo;</button>
          <button class="page-btn" :disabled="pagina === totalPaginas" @click="pagina = totalPaginas">&raquo;</button>
        </div>
      </template>
    </template>

    <div v-else class="loading" style="color:#666;">
      No tienes series favoritas. Haz clic en el corazon de cualquier serie para agregarla.
    </div>

    <!-- Modal Agregar por URL -->
    <Teleport to="body">
      <div class="modal-overlay" v-if="showUrlModal" @click.self="closeModal">
        <div class="modal">
          <h3>Agregar serie por URL</h3>
          <p class="modal-desc">Pega la URL de la serie en JKanime</p>
          <input
            v-model="urlInput"
            type="text"
            class="modal-input"
            placeholder="https://jkanime.net/nombre-de-la-serie/"
            @keyup.enter="agregarUrl"
          />
          <div v-if="urlError" class="modal-error">{{ urlError }}</div>
          <div class="modal-actions">
            <button class="btn btn-secondary btn-sm" @click="closeModal">Cancelar</button>
            <button class="btn btn-primary btn-sm" @click="agregarUrl" :disabled="agregando || !urlInput.trim()">
              {{ agregando ? 'Agregando...' : 'Agregar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getFavoritos, agregarSerieUrl, toggleFavorito } from '../api'
import { useFavoritesStore } from '../stores/favorites'

const router = useRouter()
const route = useRoute()
const favStore = useFavoritesStore()
const series = ref([])
const loading = ref(true)
const searchQuery = ref('')
const pagina = ref(parseInt(route.query.page) || 1)

const showUrlModal = ref(false)
const urlInput = ref('')
const urlError = ref('')
const agregando = ref(false)

const DIA_ORDEN = ['domingo', 'sabado', 'viernes', 'jueves', 'miercoles', 'martes', 'lunes', 'sin_dia']
const DIA_LABELS = { domingo: 'Dom', sabado: 'Sab', viernes: 'Vie', jueves: 'Jue', miercoles: 'Mie', martes: 'Mar', lunes: 'Lun', sin_dia: 'Sin dia' }

const hoy = ['domingo', 'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado'][new Date().getDay()]

const filtradas = computed(() => {
  if (!searchQuery.value.trim()) return series.value
  const q = searchQuery.value.trim().toLowerCase()
  return series.value.filter(s => s.nombre.toLowerCase().includes(q))
})

const todosLosGrupos = computed(() => {
  const map = {}
  for (const s of filtradas.value) {
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

const gruposRotados = computed(() => {
  const grupos = todosLosGrupos.value
  if (!grupos.length) return []

  const idxHoy = grupos.findIndex(g => g.dia === hoy)
  if (idxHoy <= 0) return grupos

  return [...grupos.slice(idxHoy), ...grupos.slice(0, idxHoy)]
})

const totalPaginas = computed(() => gruposRotados.value.length)

const gruposPaginados = computed(() => {
  if (!gruposRotados.value.length) return []
  return [gruposRotados.value[pagina.value - 1]]
})

const paginasVisibles = computed(() => {
  const total = totalPaginas.value
  const actual = pagina.value
  if (total <= 7) {
    return gruposRotados.value.map((g, i) => ({
      num: i + 1,
      label: DIA_LABELS[g.dia] || g.dia,
      isToday: g.dia === hoy,
    }))
  }

  const pages = []
  pages.push({ num: 1, label: DIA_LABELS[gruposRotados.value[0].dia], isToday: gruposRotados.value[0].dia === hoy })
  if (actual > 3) pages.push({ dots: true })
  for (let i = Math.max(2, actual - 1); i <= Math.min(total - 1, actual + 1); i++) {
    pages.push({ num: i, label: DIA_LABELS[gruposRotados.value[i - 1].dia], isToday: gruposRotados.value[i - 1].dia === hoy })
  }
  if (actual < total - 2) pages.push({ dots: true })
  pages.push({ num: total, label: DIA_LABELS[gruposRotados.value[total - 1].dia], isToday: gruposRotados.value[total - 1].dia === hoy })
  return pages
})

watch(searchQuery, () => { pagina.value = 1 })

watch(pagina, (val) => {
  router.replace({ query: { ...route.query, page: val > 1 ? val : undefined } })
})

async function cargarFavoritos() {
  loading.value = true
  try {
    const { data } = await getFavoritos()
    series.value = data
    favStore.loadFromSeries(data)
  } catch (e) {
    console.error('Error:', e)
  } finally {
    loading.value = false
  }
}

onMounted(cargarFavoritos)

async function quitarFavorito(serie) {
  const result = await favStore.toggle(serie.id)
  if (result === false) {
    series.value = series.value.filter(s => s.id !== serie.id)
  }
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

function closeModal() {
  showUrlModal.value = false
  urlInput.value = ''
  urlError.value = ''
}

async function agregarUrl() {
  const url = urlInput.value.trim()
  if (!url) return

  agregando.value = true
  urlError.value = ''
  try {
    const { data } = await agregarSerieUrl(url)
    const { data: favData } = await toggleFavorito(data.serie_id)
    if (!favData.favorito) {
      await toggleFavorito(data.serie_id)
    }
    if (data.existing) {
      cargarFavoritos()
    } else {
      router.push({ name: 'chapters', params: { id: data.serie_id } })
    }
  } catch (e) {
    urlError.value = e.response?.data?.error || e.message
  } finally {
    agregando.value = false
  }
}
</script>

<style scoped>
.fav-icon {
  color: #e94560;
}

.header-right {
  display: flex;
  align-items: center;
}

.search-box {
  display: flex;
  align-items: center;
  background: #16213e;
  border: 1px solid #333;
  border-radius: 20px;
  padding: 0 12px;
  transition: border-color 0.2s;
}

.search-box:focus-within {
  border-color: #e94560;
}

.search-icon {
  font-size: 0.9rem;
  color: #888;
  margin-right: 8px;
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: #e0e0e0;
  font-size: 0.85rem;
  padding: 8px 0;
  width: 220px;
}

.search-input::placeholder {
  color: #666;
}

.search-clear {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 4px;
}

.search-clear:hover {
  color: #e94560;
}

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

.fav-btn {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: #e94560;
  transition: all 0.2s;
  padding: 4px;
  line-height: 1;
}

.fav-btn:hover {
  transform: scale(1.2);
  opacity: 0.7;
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

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 24px;
  padding: 12px 0;
}

.page-btn {
  background: #1a1a2e;
  color: #888;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  color: #e94560;
  border-color: #e94560;
}

.page-btn.active {
  background: #e94560;
  color: white;
  border-color: #e94560;
}

.page-btn.today:not(.active) {
  border-color: #e94560;
  color: #e94560;
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-dots {
  color: #555;
  padding: 0 4px;
  font-size: 0.8rem;
}

.page-info {
  color: #555;
  font-size: 0.75rem;
  margin-left: 12px;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.modal {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 12px;
  padding: 24px;
  width: 420px;
  max-width: 90vw;
}

.modal h3 {
  margin: 0 0 4px;
  color: #e94560;
}

.modal-desc {
  color: #888;
  font-size: 0.85rem;
  margin: 0 0 16px;
}

.modal-input {
  width: 100%;
  padding: 10px 12px;
  background: #222;
  border: 1px solid #444;
  border-radius: 6px;
  color: #eee;
  font-size: 0.9rem;
  outline: none;
  box-sizing: border-box;
}

.modal-input:focus {
  border-color: #e94560;
}

.modal-error {
  color: #e94560;
  font-size: 0.8rem;
  margin-top: 8px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>
