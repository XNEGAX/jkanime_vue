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
      </div>
    </div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Cargando favoritos...
    </div>

    <template v-else-if="series.length">
      <div v-if="!seriesVisibles.length" class="loading" style="color:#666;">
        No se encontraron favoritos para "{{ searchQuery }}"
      </div>

      <template v-else>
        <div v-for="grupo in gruposLetras" :key="grupo.letra" class="letra-group">
          <div class="letra-group-header">
            <span class="letra-name">{{ grupo.letra }}</span>
            <span class="letra-count">{{ grupo.series.length }}</span>
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

        <!-- Sentinel para infinite scroll -->
        <div
          v-if="tieneMas"
          ref="sentinelEl"
          class="sentinel"
        >
          <span class="spinner"></span> Cargando...
        </div>
        <div v-else-if="seriesVisibles.length < filtradas.length" class="sentinel-done">
          Mostrando {{ seriesVisibles.length }} de {{ filtradas.length }} favoritos
        </div>
        <div v-else-if="seriesVisibles.length" class="sentinel-done">
          Mostrando todos los {{ seriesVisibles.length }} favoritos
        </div>
      </template>
    </template>

    <div v-else class="loading" style="color:#666;">
      No tienes series favoritas. Haz clic en el corazon de cualquier serie para agregarla.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { getFavoritos } from '../api'
import { useFavoritesStore } from '../stores/favorites'

const ITEMS_POR_LOTE = 20

const router = useRouter()
const favStore = useFavoritesStore()
const series = ref([])
const loading = ref(true)
const searchQuery = ref('')
const totalVisibles = ref(ITEMS_POR_LOTE)
const sentinelEl = ref(null)

let observer = null

// Filtradas por busqueda
const filtradas = computed(() => {
  let lista = series.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    lista = lista.filter(s => s.nombre.toLowerCase().includes(q))
  }
  return [...lista].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
})

// Solo las visibles hasta ahora
const seriesVisibles = computed(() => filtradas.value.slice(0, totalVisibles.value))

// Agrupadas por primera letra
const gruposLetras = computed(() => {
  const map = {}
  for (const s of seriesVisibles.value) {
    const letra = s.nombre.charAt(0).toUpperCase()
    if (!map[letra]) map[letra] = []
    map[letra].push(s)
  }
  const letras = Object.keys(map).sort()
  return letras.map(l => ({ letra: l, series: map[l] }))
})

const tieneMas = computed(() => totalVisibles.value < filtradas.value.length)

// --- Infinite scroll con IntersectionObserver ---

function conectarObserver() {
  desconectarObserver()
  if (!sentinelEl.value) return

  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && tieneMas.value) {
      totalVisibles.value += ITEMS_POR_LOTE
    }
  }, { rootMargin: '200px' })

  observer.observe(sentinelEl.value)
}

function desconectarObserver() {
  if (observer) {
    observer.disconnect()
    observer = null
  }
}

// Reconectar cuando cambien las visibles o el filtro
watch([seriesVisibles, tieneMas], async () => {
  await nextTick()
  if (tieneMas.value) {
    conectarObserver()
  } else {
    desconectarObserver()
  }
}, { flush: 'post' })

// --- Datos ---

async function cargarFavoritos() {
  loading.value = true
  totalVisibles.value = ITEMS_POR_LOTE
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

onBeforeUnmount(() => {
  desconectarObserver()
})

// --- Acciones ---

async function quitarFavorito(serie) {
  const result = await favStore.toggle(serie.id)
  if (result === false) {
    series.value = series.value.filter(s => s.id !== serie.id)
  }
}

// Reset al buscar
watch(searchQuery, () => {
  totalVisibles.value = ITEMS_POR_LOTE
})
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

/* --- Grupo por letra --- */

.letra-group {
  margin-bottom: 28px;
}

.letra-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 2px solid #e94560;
}

.letra-name {
  font-size: 1.3rem;
  font-weight: 700;
  color: #e94560;
}

.letra-count {
  background: #1a1a2e;
  color: #888;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

/* --- Tabla --- */

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

/* --- Infinite scroll --- */

.sentinel {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 0;
  color: #888;
  font-size: 0.85rem;
}

.sentinel-done {
  text-align: center;
  padding: 16px 0;
  color: #555;
  font-size: 0.8rem;
}
</style>
