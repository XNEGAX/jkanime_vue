<template>
  <div>
    <div class="header-actions">
      <h2><span class="fav-icon">&#9829;</span> Mis Favoritos</h2>
      <!--
        El chequeo automatico corre cada hora solo si la pestana esta abierta
        (el reloj es el navegador). Este boton es el que permite preguntar
        "hay algo nuevo?" sin esperar.
      -->
      <div v-if="activeTab === 'ultimos'" class="header-right">
        <button
          class="btn btn-secondary btn-sm"
          :disabled="trendingCargando"
          @click="iniciarVerificacionTrending(true)"
        >
          <span v-if="trendingCargando" class="spinner-sm"></span>
          {{ trendingCargando ? 'Buscando...' : 'Buscar episodios nuevos' }}
        </button>
      </div>
    </div>

    <div v-if="mensaje" :class="['alert', mensajeTipo === 'ok' ? 'alert-success' : 'alert-error']">
      {{ mensaje }}
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
              fav-title="Eliminar serie y archivos"
              @click="router.push({ name: 'chapters', params: { id: serie.id } })"
              @toggle-fav="quitarFavorito(serie, 'en_emision')"
            />
          </TrendingGrid>
        </div>
        <div
          v-if="enEmisionSinDia.length"
          class="day-group"
        >
          <div class="day-header">
            <span class="day-name">Sin día definido</span>
            <span class="day-count">{{ enEmisionSinDia.length }}</span>
          </div>
          <TrendingGrid>
            <TrendingCard
              v-for="serie in enEmisionSinDia"
              :key="serie.id"
              :image="serie.portada_url"
              :title="serie.nombre"
              :subtitle="serie.capitulos_count + ' capítulos'"
              show-fav
              :is-favorite="true"
              fav-title="Eliminar serie y archivos"
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
              fav-title="Eliminar serie y archivos"
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

    <AdminConfirmModal
      v-if="confirmModal"
      tipo="serie"
      :item="confirmModal.serie"
      :loading="eliminando"
      @confirm="confirmarEliminar"
      @cancel="confirmModal = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'
import { getUltimosEpisodios, getFavoritosByEstado, verificarCapitulo, descargarCapitulo, eliminarSerieAdmin, verificarEstados, getVerificarEstadosStatus, verificarTrending, getVerificarTrendingStatus } from '../api'
import { useFavoritesStore } from '../stores/favorites'
import { useDownloadStore } from '../stores/downloads'
import VideoPlayerModal from '../components/VideoPlayerModal.vue'
import TrendingCard from '../components/TrendingCard.vue'
import TrendingGrid from '../components/TrendingGrid.vue'
import AdminConfirmModal from '../components/admin/AdminConfirmModal.vue'

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
const route = useRoute()
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

const confirmModal = ref(null)
const eliminando = ref(false)

// Mensajes
const mensaje = ref('')
const mensajeTipo = ref('ok')
let mensajeTimer = null

function setMensaje(tipo, texto) {
  mensaje.value = texto
  mensajeTipo.value = tipo
  clearTimeout(mensajeTimer)
  mensajeTimer = setTimeout(() => { mensaje.value = '' }, 4000)
}

const ultimosEpisodios = ref([])
const enEmisionCache = ref({})
const concluidoCache = ref({})
const seriesEnEmision = computed(() => Object.values(enEmisionCache.value).flat())
const seriesConcluidas = computed(() => Object.values(concluidoCache.value).flat())

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

const enEmisionPorDia = computed(() => {
  const map = {}
  for (const dia of DIAS_ORDER) map[dia] = []
  for (const s of enEmisionFiltradas.value) {
    const dia = s.dia_emision
    if (dia && map[dia]) map[dia].push(s)
  }
  return map
})

const enEmisionSinDia = computed(() => {
  return enEmisionFiltradas.value.filter(s => !s.dia_emision)
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

// Una sola request: el agrupado por dia lo hace `enEmisionPorDia` y
// `enEmisionSinDia` en cliente, asi que filtrar por dia en el server es
// redundante (y multiplicaba la request por 8).
async function loadEnEmision() {
  loadingEnEmision.value = true
  try {
    const { data } = await getFavoritosByEstado('en_emision')
    enEmisionCache.value = { todas: data }
    favStore.loadFromSeries(seriesEnEmision.value)
  } catch (e) {
    console.error('Error loading en emisión:', e)
  } finally {
    loadingEnEmision.value = false
    loadedTabs.value['en_emision'] = true
  }
}

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

// Una sola request: el agrupado por letra inicial lo hace
// `concluidasPorLetra` en cliente, asi que el param `letras` es redundante
// (y multiplicaba la request por 6).
async function loadConcluidos() {
  loadingConcluidos.value = true
  try {
    const { data } = await getFavoritosByEstado('concluido')
    concluidoCache.value = { todas: data }
    favStore.loadFromSeries(seriesConcluidas.value)
  } catch (e) {
    console.error('Error loading concluidos:', e)
  } finally {
    loadingConcluidos.value = false
    loadedTabs.value['concluido'] = true
  }
}

// --- Revalidacion de estados en background ---
//
// El endpoint de favoritos es una lectura pura de BD; quien revalida
// estado/dia_emision contra la fuente es la tarea `verificar-estados`, que solo
// toca series en `en_emision`. Se dispara sin bloquear el render: la pantalla
// pinta desde la BD de inmediato y, si la tarea actualiza algo, se recarga.

let estadosTimer = null
let estadosIniciados = false

function detenerVerificacionEstados() {
  if (estadosTimer) {
    clearInterval(estadosTimer)
    estadosTimer = null
  }
  estadosIniciados = false
}

async function iniciarVerificacionEstados() {
  if (estadosIniciados) return
  estadosIniciados = true
  try {
    const { data } = await verificarEstados()
    if (data.status === 'started' || data.status === 'already_running') {
      pollVerificacionEstados()
    }
  } catch (e) {
    console.error('Error iniciando verificación de estados:', e)
  }
}

function pollVerificacionEstados() {
  detenerVerificacionEstados()
  estadosTimer = setInterval(async () => {
    try {
      const { data } = await getVerificarEstadosStatus()
      if (data.state === 'SUCCESS') {
        detenerVerificacionEstados()
        if ((data.reverificadas || 0) > 0 && activeTab.value === 'en_emision') {
          await loadEnEmision()
        }
      } else if (['FAILURE', 'CANCELLED', 'NONE'].includes(data.state)) {
        detenerVerificacionEstados()
      }
    } catch (e) {
      console.error('Error consultando verificación de estados:', e)
      detenerVerificacionEstados()
    }
  }, 2000)
}

// El componente puede desmontarse con un poll en vuelo: sin esto el timer
// escribiria sobre refs de un componente muerto.
onUnmounted(detenerVerificacionEstados)

// --- Chequeo horario de episodios nuevos ---
//
// `/api/ultimos-episodios/` se apoya en una cache de 30 min del trending, asi
// que "mirar la pantalla" no es una forma de enterarse de que salio algo. La
// tarea `verificar-trending` existe para eso: corre la misma sincronizacion que
// el endpoint pero con scrape forzado, y el frontend la dispara cada hora mas un
// boton manual. Solo recarga la lista si la corrida trajo capitulos nuevos: en el
// caso normal (0 nuevos) recargar seria tirar la respuesta del endpoint al piso.

const TRENDING_INTERVALO_MS = 3600000

// Dos timers y no uno: el de la hora vive mientras el componente este montado y
// `detenerVerificacionTrending` debe poder apagar SOLO el poll. Con un unico
// timer, terminar una corrida cancelaria el horario y quedaria sin refresco.
let trendingTimer = null          // poll de una corrida
let trendingIntervalTimer = null  // reloj horario, solo se apaga al desmontar
let trendingIniciados = false
const trendingCargando = ref(false)

function detenerVerificacionTrending() {
  if (trendingTimer) {
    clearInterval(trendingTimer)
    trendingTimer = null
  }
  trendingIniciados = false
  trendingCargando.value = false
}

// `forzar` distingue el disparo del boton del disparo del timer. Los dos hacen
// exactamente lo mismo: la diferencia es de donde viene la peticion, y eso solo
// se usa para el mensaje.
async function iniciarVerificacionTrending(forzar = false) {
  if (trendingIniciados) return
  trendingIniciados = true
  trendingCargando.value = true
  try {
    const { data } = await verificarTrending()
    if (data.status === 'started' || data.status === 'already_running') {
      pollVerificacionTrending()
    } else {
      detenerVerificacionTrending()
    }
  } catch (e) {
    // Sin esto el boton quedaria disabled para siempre si la request falla.
    console.error('Error iniciando verificación de trending:', e)
    setMensaje('error', 'No se pudo iniciar la verificación de episodios nuevos')
    detenerVerificacionTrending()
  }
}

function pollVerificacionTrending() {
  detenerVerificacionTrending()
  // El guard es el mismo flag del arranque: el poll reemplaza el estado pero no
  // lo pisa, asi que sigue habiendo un solo ciclo en vuelo a la vez.
  trendingIniciados = true
  trendingCargando.value = true
  trendingTimer = setInterval(async () => {
    try {
      const { data } = await getVerificarTrendingStatus()
      if (data.state === 'SUCCESS') {
        const nuevos = data.nuevos || 0
        detenerVerificacionTrending()
        if (nuevos > 0) {
          // `loadedTabs` se limpia antes de recargar: `switchTab` respeta ese
          // flag y sin limpiarlo el reload no volveria a pedir los datos.
          loadedTabs.value.ultimos = false
          await loadTabData('ultimos')
          setMensaje('ok', `${nuevos} episodio${nuevos === 1 ? '' : 's'} nuevo${nuevos === 1 ? '' : 's'}`)
        } else if (!ultimosEpisodios.value.length) {
          // "0 nuevos" con la lista vacia no es un estado valido: 0 nuevos
          // significa que el scrape funciono y la BD ya tenia todo. Si la lista
          // esta vacia es una carga que fallo, y el chequeo horario es la unica
          // cosa que corre sola: sin este reintento el home quedaba vacio hasta
          // que el usuario apretara F5.
          loadedTabs.value.ultimos = false
          await loadTabData('ultimos')
          setMensaje('ok', 'Lista de episodios recargada')
        } else {
          setMensaje('ok', 'Sin episodios nuevos')
        }
      } else if (['FAILURE', 'CANCELLED', 'NONE'].includes(data.state)) {
        detenerVerificacionTrending()
        if (data.state === 'FAILURE' && data.mensaje) {
          setMensaje('error', data.mensaje)
        }
      }
    } catch (e) {
      console.error('Error consultando verificación de trending:', e)
      detenerVerificacionTrending()
    }
  }, 2000)
}

// El reloj horario se apaga solo aqui: a diferencia del poll, no se reinicia en
// cada corrida y por eso no puede colgarse de `detenerVerificacionTrending`.
onUnmounted(() => {
  detenerVerificacionTrending()
  if (trendingIntervalTimer) {
    clearInterval(trendingIntervalTimer)
    trendingIntervalTimer = null
  }
})

function switchTab(tab) {
  activeTab.value = tab
  searchQuery.value = ''
  if (!loadedTabs.value[tab]) {
    loadTabData(tab)
  }
  if (tab === 'en_emision') {
    iniciarVerificacionEstados()
  }
}

onMounted(() => {
  const savedTab = sessionStorage.getItem(TAB_KEY)
  if (savedTab && VALID_TABS.includes(savedTab)) {
    activeTab.value = savedTab
  }
  loadTabData(activeTab.value)

  if (activeTab.value === 'en_emision') {
    iniciarVerificacionEstados()
  }

  // Cada hora. Es el unico reloj del sistema: no hay cron, ni celery beat, ni un
  // timer en el backend, asi que el navegador es el que pregunta. Por eso el
  // chequeo es best-effort: si no hay pestana abierta, no hay chequeo (el boton
  // manual cubre el caso).
  trendingIntervalTimer = setInterval(() => iniciarVerificacionTrending(), TRENDING_INTERVALO_MS)

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
      // Solo se marca cargada si la request salio bien. Marcarla en el `finally`
      // convertia un unico fallo (por ejemplo el server recargando codigo justo
      // cuando se abrio la pestana) en un home vacio PERMANENTE: `switchTab` no
      // vuelve a pedir una pestana que figura en `loadedTabs`, asi que ni
      // cambiar de pestana ni volver la recuperaba.
      loadedTabs.value[tab] = true
    } catch (e) {
      console.error('Error loading últimos episodios:', e)
    } finally {
      loadingUltimos.value = false
    }
  } else if (tab === 'en_emision') {
    await loadEnEmision()
  } else if (tab === 'concluido') {
    await loadConcluidos()
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

function quitarFavorito(serie, tabKey) {
  confirmModal.value = { serie, tabKey }
}

// Tras quitar de favoritos, el usuario queda en la url raiz con el tab
// "En emisión" activo. El tab se persiste en sessionStorage, asi que se
// escribe antes de navegar para que un remount no lo revierta.
async function irAEnEmision() {
  sessionStorage.setItem(TAB_KEY, 'en_emision')
  activeTab.value = 'en_emision'
  searchQuery.value = ''
  if (!loadedTabs.value.en_emision) {
    await loadTabData('en_emision')
  }
  if (route.path !== '/') {
    router.push({ name: 'favorites' })
  }
}

async function confirmarEliminar() {
  if (eliminando.value || !confirmModal.value) return
  const { serie, tabKey } = confirmModal.value
  eliminando.value = true
  try {
    await eliminarSerieAdmin(serie.id)
    if (tabKey === 'en_emision') {
      for (const dia of Object.keys(enEmisionCache.value)) {
        enEmisionCache.value[dia] = (enEmisionCache.value[dia] || []).filter(s => s.id !== serie.id)
      }
    } else if (tabKey === 'concluido') {
      for (const grupo of Object.keys(concluidoCache.value)) {
        concluidoCache.value[grupo] = (concluidoCache.value[grupo] || []).filter(s => s.id !== serie.id)
      }
    }
    favStore.setFavorito(serie.id, false)
    confirmModal.value = null
    setMensaje('ok', `"${serie.nombre}" eliminada correctamente`)
    await irAEnEmision()
  } catch (e) {
    setMensaje('error', 'Error al eliminar: ' + (e.response?.data?.error || e.message))
  } finally {
    eliminando.value = false
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
.alert {
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 0.9rem;
}

.alert-success {
  background: rgba(39, 174, 96, 0.12);
  border: 1px solid #27ae60;
  color: #27ae60;
}

.alert-error {
  background: rgba(0, 83, 156, 0.1);
  border: 1px solid var(--primary);
  color: var(--primary);
}

.fav-icon {
  color: var(--primary);
}

.header-actions {
  margin-bottom: 16px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Copia de AdminView.vue: los estilos son scoped, asi que no se heredan entre
   componentes y el boton se veria sin spinner. */
.spinner-sm {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-light);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin-sm 0.8s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin-sm {
  to { transform: rotate(360deg); }
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

.tab-btn:focus-visible {
  outline: 2px solid var(--accent-cta);
  outline-offset: 2px;
}

.tab-btn:hover {
  color: var(--text-main);
}

.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

/* --- Day groups (Tab 2 y 3) --- */

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
