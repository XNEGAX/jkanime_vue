<template>
  <div>
    <div class="header-actions">
      <h2><span class="fav-icon">&#9829;</span> Mis Favoritos</h2>
    </div>

    <nav class="tabs-nav">
      <button
        :class="['tab-btn', { active: activeTab === 'ultimos' }]"
        @click="switchTab('ultimos')"
      >
        Últimos episodios
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'en_emision' }]"
        @click="switchTab('en_emision')"
      >
        En emisión
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'concluido' }]"
        @click="switchTab('concluido')"
      >
        Concluidos
      </button>
    </nav>

    <!-- Tab 1: Últimos episodios -->
    <template v-if="activeTab === 'ultimos'">
      <div v-if="loadingUltimos" class="loading">
        <span class="spinner"></span> Cargando episodios...
      </div>
      <div v-else-if="!ultimosEpisodios.length" class="empty-state">
        No hay episodios trending
      </div>
      <template v-else>
        <div v-for="tab in tabsDisponibles" :key="tab" class="day-group">
          <div class="day-header">
            <span class="day-name">{{ tab }}</span>
            <span class="day-count">{{ ultimosPorTab[tab].length }}</span>
          </div>
          <TrendingGrid>
            <TrendingCard
              v-for="(ep, idx) in ultimosPorTab[tab]"
              :key="idx"
              :image="ep.imagen"
              :title="ep.nombre"
              :subtitle="'Episodio ' + ep.episodio"
              :download-state="downloadStatus(ep.capitulo_id)"
              @click="handleEpisodio(ep)"
            />
          </TrendingGrid>
        </div>
      </template>
    </template>

    <!-- Tab 2: En emisión -->
    <template v-if="activeTab === 'en_emision'">
      <div class="tab-search">
        <span class="search-icon">&#128269;</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar en emisión..."
          class="search-input"
        />
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">&#10005;</button>
      </div>
      <div v-if="loadingEnEmision" class="loading">
        <span class="spinner"></span> Cargando series en emisión...
      </div>
      <div v-else-if="!seriesEnEmision.length" class="empty-state">
        No tienes favoritos en emisión
      </div>
      <template v-else>
        <div v-if="!enEmisionFiltradas.length" class="empty-state">
          No se encontraron series para "{{ searchQuery }}"
        </div>
        <div
          v-for="dia in diasDesdeHoy"
          :key="dia"
          v-show="enEmisionPorDia[dia] && enEmisionPorDia[dia].length"
          class="day-group"
        >
          <div class="day-header">
            <span class="day-name">{{ DIAS[dia] }}</span>
            <span class="day-count">{{ enEmisionPorDia[dia].length }}</span>
          </div>
          <TrendingGrid>
            <TrendingCard
              v-for="serie in enEmisionPorDia[dia]"
              :key="serie.id"
              :image="serie.portada_url"
              :title="serie.nombre"
              :subtitle="serie.capitulos_count + ' capítulos'"
              show-fav
              :is-favorite="true"
              @click="router.push({ name: 'chapters', params: { id: serie.id } })"
              @toggle-fav="quitarFavorito(serie, 'en_emision')"
            />
          </TrendingGrid>
        </div>
      </template>
    </template>

    <!-- Tab 3: Concluidos -->
    <template v-if="activeTab === 'concluido'">
      <div class="tab-search">
        <span class="search-icon">&#128269;</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar concluidos..."
          class="search-input"
        />
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">&#10005;</button>
      </div>
      <div v-if="loadingConcluidos" class="loading">
        <span class="spinner"></span> Cargando series concluidas...
      </div>
      <div v-else-if="!seriesConcluidas.length" class="empty-state">
        No tienes series concluidas
      </div>
      <template v-else>
        <div v-if="!concluidasFiltradas.length" class="empty-state">
          No se encontraron series para "{{ searchQuery }}"
        </div>
        <div v-for="grupo in concluidasPorLetra" :key="grupo.letra" class="day-group">
          <div class="day-header">
            <span class="day-name">{{ grupo.letra }}</span>
            <span class="day-count">{{ grupo.series.length }}</span>
          </div>
          <TrendingGrid>
            <TrendingCard
              v-for="serie in grupo.series"
              :key="serie.id"
              :image="serie.portada_url"
              :title="serie.nombre"
              :subtitle="serie.descargados_count + '/' + serie.capitulos_count + ' descargados'"
              show-fav
              :is-favorite="true"
              @click="router.push({ name: 'chapters', params: { id: serie.id } })"
              @toggle-fav="quitarFavorito(serie, 'concluido')"
            />
          </TrendingGrid>
        </div>
      </template>
    </template>

    <VideoPlayerModal
      v-if="playerCapituloId"
      :capituloId="playerCapituloId"
      @close="playerCapituloId = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { getUltimosEpisodios, getFavoritosByEstado, verificarCapitulo, descargarCapitulo } from '../api'
import { useFavoritesStore } from '../stores/favorites'
import { useDownloadStore } from '../stores/downloads'
import VideoPlayerModal from '../components/VideoPlayerModal.vue'
import TrendingCard from '../components/TrendingCard.vue'
import TrendingGrid from '../components/TrendingGrid.vue'

const DIAS = {
  lunes: 'Lunes',
  martes: 'Martes',
  miercoles: 'Miércoles',
  jueves: 'Jueves',
  viernes: 'Viernes',
  sabado: 'Sábado',
  domingo: 'Domingo',
}

const DIAS_ORDER = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']

const TAB_ORDER = ['Animes', 'Donghuas', 'Ovas']

const router = useRouter()
const favStore = useFavoritesStore()
const dlStore = useDownloadStore()

const activeTab = ref('ultimos')
const searchQuery = ref('')

const VALID_TABS = ['ultimos', 'en_emision', 'concluido']
const SCROLL_KEY = 'animewing-nav-scroll'
const TAB_KEY = 'animewing-fav-tab'

onBeforeRouteLeave(() => {
  sessionStorage.setItem(TAB_KEY, activeTab.value)
  sessionStorage.setItem(SCROLL_KEY, JSON.stringify({
    top: window.scrollY,
    left: window.scrollX,
    path: '/',
  }))
})

const loadedTabs = ref({})

const loadingUltimos = ref(false)
const loadingEnEmision = ref(false)
const loadingConcluidos = ref(false)

const playerCapituloId = ref(null)

const ultimosEpisodios = ref([])
const seriesEnEmision = ref([])
const seriesConcluidas = ref([])

// --- Tab 1: agrupar por tab ---

const ultimosPorTab = computed(() => {
  const map = {}
  for (const t of TAB_ORDER) map[t] = []
  for (const ep of ultimosEpisodios.value) {
    const tab = ep.tab || 'Animes'
    if (map[tab]) map[tab].push(ep)
    else map[tab] = [ep]
  }
  return map
})

const tabsDisponibles = computed(() => {
  return TAB_ORDER.filter(t => ultimosPorTab.value[t] && ultimosPorTab.value[t].length)
})

// --- Tab 2: en emisión ---

const enEmisionFiltradas = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return seriesEnEmision.value
  return seriesEnEmision.value.filter(s => s.nombre.toLowerCase().includes(q))
})

const diasDesdeHoy = computed(() => {
  const jsDay = new Date().getDay()
  // Convertir JS day (0=domingo) a indice DIAS_ORDER (0=lunes)
  const todayIdx = (jsDay + 6) % 7
  const orden = []
  for (let i = 0; i < 7; i++) {
    orden.push(DIAS_ORDER[(todayIdx - i + 7) % 7])
  }
  return orden
})

const enEmisionPorDia = computed(() => {
  const map = {}
  for (const dia of DIAS_ORDER) map[dia] = []
  for (const s of enEmisionFiltradas.value) {
    const dia = s.dia_emision
    if (dia && map[dia]) map[dia].push(s)
  }
  return map
})

// --- Tab 3: concluidos ---

const concluidasFiltradas = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const lista = seriesConcluidas.value
  if (!q) return [...lista].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
  return lista
    .filter(s => s.nombre.toLowerCase().includes(q))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
})

const concluidasPorLetra = computed(() => {
  const map = {}
  for (const s of concluidasFiltradas.value) {
    const letra = s.nombre.charAt(0).toUpperCase()
    if (!map[letra]) map[letra] = []
    map[letra].push(s)
  }
  return Object.keys(map).sort().map(l => ({ letra: l, series: map[l] }))
})

function switchTab(tab) {
  activeTab.value = tab
  searchQuery.value = ''
  if (!loadedTabs.value[tab]) {
    loadTabData(tab)
  }
}

onMounted(() => {
  const savedTab = sessionStorage.getItem(TAB_KEY)
  if (savedTab && VALID_TABS.includes(savedTab)) {
    activeTab.value = savedTab
  }
  loadTabData(activeTab.value)

  const savedScroll = sessionStorage.getItem(SCROLL_KEY)
  if (savedScroll) {
    try {
      const { top } = JSON.parse(savedScroll)
      nextTick(() => {
        window.scrollTo({ top, behavior: 'auto' })
      })
    } catch {
      // ignore invalid JSON
    }
  }
})

async function loadTabData(tab) {
  if (tab === 'ultimos') {
    loadingUltimos.value = true
    try {
      const { data } = await getUltimosEpisodios()
      ultimosEpisodios.value = data.episodios || []
      favStore.loadFromSeries(data.episodios || [])
    } catch (e) {
      console.error('Error loading últimos episodios:', e)
    } finally {
      loadingUltimos.value = false
      loadedTabs.value[tab] = true
    }
  } else if (tab === 'en_emision') {
    loadingEnEmision.value = true
    try {
      const { data } = await getFavoritosByEstado('en_emision')
      seriesEnEmision.value = data
      favStore.loadFromSeries(data)
    } catch (e) {
      console.error('Error loading en emisión:', e)
    } finally {
      loadingEnEmision.value = false
      loadedTabs.value[tab] = true
    }
  } else if (tab === 'concluido') {
    loadingConcluidos.value = true
    try {
      const { data } = await getFavoritosByEstado('concluido')
      seriesConcluidas.value = data
      favStore.loadFromSeries(data)
    } catch (e) {
      console.error('Error loading concluidos:', e)
    } finally {
      loadingConcluidos.value = false
      loadedTabs.value[tab] = true
    }
  }
}

function handleEpisodio(ep) {
  // Si no hay capitulo en BD, ir a la vista de capitulos (que crea el cap y maneja download)
  if (!ep.capitulo_id) {
    if (ep.serie_id) {
      router.push({ name: 'chapters', params: { id: ep.serie_id } })
    } else {
      window.open(ep.url, '_blank')
    }
    return
  }

  // Tiene capitulo — verificar si el archivo existe localmente
  verificarCapitulo(ep.capitulo_id)
    .then(({ data }) => {
      if (data.valido) {
        // Archivo OK → abrir reproductor
        playerCapituloId.value = ep.capitulo_id
      } else {
        // Corrupto o no existe → descargar y luego reproducir
        iniciarDescargaTrending(ep.capitulo_id)
      }
    })
    .catch(() => {
      // Error de verificacion → intentar descargar
      iniciarDescargaTrending(ep.capitulo_id)
    })
}

function iniciarDescargaTrending(capituloId) {
  descargarCapitulo(capituloId)
    .then(({ data }) => {
      if (data.task_id) {
        dlStore.addDownload(data.task_id, capituloId, '', 0, () => {
          playerCapituloId.value = capituloId
        })
      } else if (data.skip) {
        playerCapituloId.value = capituloId
      }
    })
    .catch(() => {})
}

async function quitarFavorito(serie, tabKey) {
  const result = await favStore.toggle(serie.id)
  if (result === false) {
    if (tabKey === 'en_emision') {
      seriesEnEmision.value = seriesEnEmision.value.filter(s => s.id !== serie.id)
    } else if (tabKey === 'concluido') {
      seriesConcluidas.value = seriesConcluidas.value.filter(s => s.id !== serie.id)
    }
  }
}

// --- Estado de descarga por capitulo ---

function downloadStatus(capituloId) {
  if (!capituloId) return null
  return dlStore.downloads.find(d => d.capituloId === capituloId && (d.state === 'PROGRESS' || d.state === 'PENDING')) || null
}

watch(activeTab, () => {
  searchQuery.value = ''
})
</script>

<style scoped>
.fav-icon {
  color: var(--primary);
}

.header-actions {
  margin-bottom: 16px;
}

.header-right {
  display: flex;
  align-items: center;
}

.tab-search {
  display: flex;
  align-items: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: 20px;
  padding: 0 12px;
  margin-bottom: 20px;
  transition: border-color 0.2s;
  max-width: 320px;
}

.tab-search:focus-within {
  border-color: var(--primary);
}

.search-icon {
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-right: 8px;
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-main);
  font-size: 0.85rem;
  padding: 8px 0;
  width: 220px;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-clear {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 4px;
}

.search-clear:hover {
  color: var(--primary);
}

/* --- Tabs --- */

.tabs-nav {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-light);
  margin-bottom: 24px;
}

.tab-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  padding: 12px 24px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
  margin-bottom: -2px;
}

.tab-btn:hover {
  color: var(--text-main);
}

.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

/* --- Day groups (Tab 2) --- */

.day-group {
  margin-bottom: 24px;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--primary);
}

.day-name {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--primary);
  text-transform: capitalize;
}

.day-count {
  background: var(--primary);
  color: var(--text-muted);
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

/* --- Loading / Empty --- */

.empty-state {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-muted);
  font-size: 0.95rem;
}
</style>
