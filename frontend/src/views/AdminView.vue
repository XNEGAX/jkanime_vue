<template>
  <div>
    <div class="header-actions">
      <h2>Administración</h2>
      <button class="btn btn-secondary btn-sm" @click="refrescarTodo" :disabled="refrescando">
        <span v-if="refrescando" class="spinner-sm"></span>
        {{ refrescando ? 'Actualizando...' : 'Refrescar' }}
      </button>
    </div>

    <div v-if="mensaje" :class="['alert', mensajeTipo === 'ok' ? 'alert-success' : 'alert-error']">
      {{ mensaje }}
    </div>

    <nav class="tabs-nav">
      <button :class="['tab-btn', { active: activeTab === 'series' }]" @click="cambiarTab('series')">Series</button>
      <button :class="['tab-btn', { active: activeTab === 'capitulos' }]" @click="cambiarTab('capitulos')">Capítulos</button>
    </nav>

    <!-- TAB SERIES -->
    <template v-if="activeTab === 'series'">
      <div class="filtros">
        <div class="filtro-buscar">
          <span class="search-icon">&#128269;</span>
          <input v-model="busqueda" type="text" placeholder="Buscar por nombre..." class="search-input" @input="onBuscar" />
          <button v-if="busqueda" class="search-clear" @click="clearBusqueda" title="Limpiar">&#10005;</button>
        </div>
        <select v-model="filtroEstado" class="filtro-select" @change="cargarSeries">
          <option value="">Estado: todos</option>
          <option value="en_emision">En emisión</option>
          <option value="concluido">Concluido</option>
          <option value="desconocido">Desconocido</option>
        </select>
        <select v-model="filtroDia" class="filtro-select" @change="cargarSeries">
          <option value="">Día: todos</option>
          <option value="lunes">Lunes</option>
          <option value="martes">Martes</option>
          <option value="miercoles">Miércoles</option>
          <option value="jueves">Jueves</option>
          <option value="viernes">Viernes</option>
          <option value="sabado">Sábado</option>
          <option value="domingo">Domingo</option>
        </select>
        <select v-model="filtroFuente" class="filtro-select" @change="cargarSeries">
          <option value="">Fuente: todas</option>
          <option value="jkanime">jkanime</option>
          <option value="latanime">latanime</option>
          <option value="animeflv">animeflv</option>
          <option value="youtube">youtube</option>
        </select>
        <select v-model="filtroFavorito" class="filtro-select" @change="cargarSeries">
          <option value="">Favorito: todos</option>
          <option value="true">Sí</option>
          <option value="false">No</option>
        </select>
        <select v-model="filtroOrden" class="filtro-select" @change="cargarSeries">
          <option value="nombre">Orden: Nombre</option>
          <option value="-nombre">Orden: Nombre (Z-A)</option>
          <option value="anio">Orden: Año</option>
          <option value="-anio">Orden: Año (desc)</option>
          <option value="-created_at">Orden: Recientes</option>
        </select>
        <button class="btn btn-primary btn-sm" @click="abrirModalUrl">+ Agregar por URL</button>
      </div>

      <div v-if="loadingSeries && !series.length" class="loading">
        <span class="spinner"></span> Cargando series...
      </div>
      <template v-else>
        <div :class="{ 'tabla-opacity': loadingSeries }">
          <table>
            <thead>
              <tr>
                <th style="width:90px">Portada</th>
                <th>Nombre</th>
                <th style="width:70px">Año</th>
                <th style="width:120px">Estado</th>
                <th style="width:110px">Día</th>
                <th style="width:90px">Fuente</th>
                <th style="width:60px">Fav</th>
                <th style="width:80px">Capítulos</th>
                <th style="width:90px">Descarg.</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in series" :key="s.id">
                <td>
                  <img v-if="s.portada_url" :src="s.portada_url" :alt="s.nombre" class="cover-img" />
                  <div v-else class="cover-placeholder">Sin portada</div>
                </td>
                <td><strong>{{ s.nombre }}</strong></td>
                <td>{{ s.anio }}</td>
                <td><span :class="['estado-badge', 'estado-' + s.estado]">{{ estadoLabel(s.estado) }}</span></td>
                <td>{{ diaLabel(s.dia_emision) }}</td>
                <td>{{ s.fuente }}</td>
                <td>{{ s.favorito ? '\u2665' : '\u2013' }}</td>
                <td>{{ s.capitulos_count }}</td>
                <td>{{ s.descargados_count }}</td>
                <td>
                  <div class="acciones">
                    <button class="btn btn-secondary btn-sm" @click="editarSerie(s)">Editar</button>
                    <button class="btn btn-secondary btn-sm" @click="verCapitulos(s)">Capítulos</button>
                    <button class="btn btn-danger btn-sm" @click="pedirEliminarSerie(s)">Eliminar</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!series.length" class="empty-state">
          {{
            busqueda || filtroEstado || filtroDia || filtroFuente || filtroFavorito || filtroOrden !== 'nombre'
              ? 'No se encontraron series con esos filtros'
              : 'No hay series registradas.'
          }}
        </div>
      </template>
    </template>

    <!-- TAB CAPÍTULOS -->
    <template v-if="activeTab === 'capitulos'">
      <div class="filtros">
        <select v-model="filtroSerieId" class="filtro-select" @change="cargarCapitulos">
          <option value="">Serie: todas</option>
          <option v-for="s in allSeries" :key="s.id" :value="s.id">{{ s.nombre }}</option>
        </select>
        <button class="btn btn-primary btn-sm" @click="abrirNuevoCapitulo">+ Nuevo capítulo</button>
      </div>

      <div v-if="loadingCapitulos && !capitulos.length" class="loading">
        <span class="spinner"></span> Cargando capítulos...
      </div>
      <template v-else>
        <div :class="{ 'tabla-opacity': loadingCapitulos }">
          <table>
            <thead>
              <tr>
                <th>Serie</th>
                <th style="width:70px">Nº</th>
                <th style="width:130px">Publicado</th>
                <th>URL fuente</th>
                <th>Ruta archivo</th>
                <th style="width:90px">Archivo</th>
                <th style="width:90px">Últ. seg.</th>
                <th style="width:150px">Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in capitulos" :key="c.id">
                <td><strong>{{ c.serie_nombre }}</strong></td>
                <td>{{ c.numero }}</td>
                <td class="date-cell">{{ formatFecha(c.fecha_publicacion) }}</td>
                <td class="cell-ellipsis" :title="c.url_fuente || ''">{{ c.url_fuente }}</td>
                <td class="cell-ellipsis" :title="c.ruta_archivo || ''">{{ c.ruta_archivo || '\u2014' }}</td>
                <td>
                  <span :class="c.archivo_existe ? 'badge-ok' : 'badge-pending'">
                    {{ c.archivo_existe ? 'Ok' : 'Pendiente' }}
                  </span>
                </td>
                <td>{{ c.ultimo_segundo ? formatSegundos(c.ultimo_segundo) : '\u2014' }}</td>
                <td>
                  <div class="acciones">
                    <button class="btn btn-secondary btn-sm" @click="editarCapitulo(c)">Editar</button>
                    <button class="btn btn-danger btn-sm" @click="pedirEliminarCapitulo(c)">Eliminar</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!capitulos.length" class="empty-state">
          No hay capítulos{{ filtroSerieId ? ' para esta serie' : '' }}.
        </div>
      </template>
    </template>

    <AdminSerieForm
      v-if="serieModal"
      :serie="serieModal.mode === 'edit' ? serieModal.serie : null"
      @saved="onSerieGuardada"
      @cancel="serieModal = null"
    />

    <AdminCapituloForm
      v-if="capituloModal"
      :series="allSeries"
      :capitulo="capituloModal.mode === 'edit' ? capituloModal.capitulo : null"
      :serie-id="capituloModal.mode === 'create' ? capituloModal.serieId : ''"
      @saved="onCapituloGuardado"
      @cancel="capituloModal = null"
    />

    <AdminConfirmModal
      v-if="confirmModal"
      :tipo="confirmModal.tipo"
      :item="confirmModal.item"
      :loading="eliminando"
      @confirm="confirmarEliminar"
      @cancel="confirmModal = null"
    />

    <!-- Modal Agregar por URL -->
    <Teleport to="body">
      <div class="modal-overlay" v-if="showUrlModal" @click.self="cerrarModalUrl">
        <div class="modal-box">
          <h3>Agregar serie por URL</h3>
          <p class="modal-desc">Pegá la URL de la serie (jkanime.net, latanime.org, animeflv o YouTube). Se crean capítulos y portada automáticamente.</p>
          <input
            v-model="urlInput"
            type="text"
            class="modal-input"
            placeholder="https://jkanime.net/..."
            @keydown.enter="agregarUrl"
            ref="urlInputEl"
          />
          <div v-if="urlError" class="modal-error">{{ urlError }}</div>
          <div class="modal-actions">
            <button class="btn btn-secondary btn-sm" @click="cerrarModalUrl">Cancelar</button>
            <button class="btn btn-primary btn-sm" @click="agregarUrl" :disabled="agregandoUrl || !urlInput.trim()">
              {{ agregandoUrl ? 'Agregando...' : 'Agregar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import {
  getAdminSeries,
  getAdminCapitulos,
  eliminarSerieAdmin,
  eliminarCapitulo,
  agregarSerieUrl,
} from '../api'
import AdminSerieForm from '../components/admin/AdminSerieForm.vue'
import AdminCapituloForm from '../components/admin/AdminCapituloForm.vue'
import AdminConfirmModal from '../components/admin/AdminConfirmModal.vue'

const ESTADO_LABELS = { en_emision: 'En emisión', concluido: 'Concluido', desconocido: 'Desconocido' }
const DIA_LABELS = {
  lunes: 'Lunes',
  martes: 'Martes',
  miercoles: 'Miércoles',
  jueves: 'Jueves',
  viernes: 'Viernes',
  sabado: 'Sábado',
  domingo: 'Domingo',
}

function estadoLabel(estado) {
  return ESTADO_LABELS[estado] || estado || 'Desconocido'
}

function diaLabel(dia) {
  return dia ? DIA_LABELS[dia] || dia : 'Sin definir'
}

function toList(data) {
  return Array.isArray(data) ? data : (data?.results || [])
}

function formatFecha(iso) {
  if (!iso) return '\u2014'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '\u2014'
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function formatSegundos(seg) {
  const s = Number(seg) || 0
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, '0')}`
}

const activeTab = ref('series')

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

// --- Series ---
const series = ref([])
const loadingSeries = ref(true)
const seriesCargadas = ref(false)
const busqueda = ref('')
const filtroEstado = ref('')
const filtroDia = ref('')
const filtroFuente = ref('')
const filtroFavorito = ref('')
const filtroOrden = ref('nombre')

let debounceTimer = null

function onBuscar() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(cargarSeries, 300)
}

function clearBusqueda() {
  busqueda.value = ''
  cargarSeries()
}

async function cargarSeries() {
  loadingSeries.value = true
  try {
    const params = {}
    const q = busqueda.value.trim()
    if (q) params.search = q
    if (filtroEstado.value) params.estado = filtroEstado.value
    if (filtroDia.value) params.dia = filtroDia.value
    if (filtroFuente.value) params.fuente = filtroFuente.value
    if (filtroFavorito.value) params.favorito = filtroFavorito.value
    if (filtroOrden.value) params.orden = filtroOrden.value
    const { data } = await getAdminSeries(params)
    series.value = toList(data)
  } catch (e) {
    setMensaje('error', 'Error cargando series: ' + (e.response?.data?.error || e.message))
  } finally {
    loadingSeries.value = false
    seriesCargadas.value = true
  }
}

// --- Todas las series (para el select de capítulos) ---
const allSeries = ref([])

async function cargarAllSeries() {
  try {
    const { data } = await getAdminSeries()
    allSeries.value = toList(data)
  } catch {
    // Silencioso: los filtros de capítulos siguen funcionando igual
  }
}

// --- Capítulos ---
const capitulos = ref([])
const loadingCapitulos = ref(true)
const capitulosCargados = ref(false)
const filtroSerieId = ref('')

async function cargarCapitulos() {
  loadingCapitulos.value = true
  try {
    const params = {}
    if (filtroSerieId.value) params.serie = filtroSerieId.value
    const { data } = await getAdminCapitulos(params)
    capitulos.value = toList(data)
  } catch (e) {
    setMensaje('error', 'Error cargando capítulos: ' + (e.response?.data?.error || e.message))
  } finally {
    loadingCapitulos.value = false
    capitulosCargados.value = true
  }
}

function cambiarTab(tab) {
  activeTab.value = tab
  if (tab === 'capitulos' && !capitulosCargados.value) {
    cargarCapitulos()
  }
}

const refrescando = ref(false)

async function refrescarTodo() {
  refrescando.value = true
  await Promise.all([cargarSeries(), cargarAllSeries()])
  if (capitulosCargados.value) await cargarCapitulos()
  refrescando.value = false
}

// --- Modales ---
const serieModal = ref(null)
const capituloModal = ref(null)

// --- Agregar por URL ---
const showUrlModal = ref(false)
const urlInput = ref('')
const urlError = ref('')
const agregandoUrl = ref(false)
const urlInputEl = ref(null)

function abrirModalUrl() {
  urlError.value = ''
  urlInput.value = ''
  showUrlModal.value = true
  nextTick(() => urlInputEl.value?.focus())
}

function cerrarModalUrl() {
  showUrlModal.value = false
  urlError.value = ''
  urlInput.value = ''
}

async function agregarUrl() {
  const url = urlInput.value.trim()
  if (!url || agregandoUrl.value) return
  agregandoUrl.value = true
  urlError.value = ''
  try {
    const { data } = await agregarSerieUrl(url)
    if (data.serie_id) {
      const nuevaId = data.serie_id
      cerrarModalUrl()
      setMensaje('ok', (data.nombre ? `"${data.nombre}" ` : 'Serie ') + 'agregada correctamente')
      await Promise.all([cargarSeries(), cargarAllSeries()])
      verCapitulos({ id: nuevaId })
    } else {
      urlError.value = data.message || 'Error al agregar la serie'
    }
  } catch (e) {
    urlError.value = e.response?.data?.error || e.message || 'Error de conexión'
  } finally {
    agregandoUrl.value = false
  }
}

function editarSerie(s) {
  serieModal.value = { mode: 'edit', serie: s }
}

function onSerieGuardada() {
  serieModal.value = null
  setMensaje('ok', 'Serie guardada correctamente')
  cargarSeries()
  cargarAllSeries()
}

function verCapitulos(s) {
  filtroSerieId.value = s.id
  activeTab.value = 'capitulos'
  cargarCapitulos()
}

function abrirNuevoCapitulo() {
  capituloModal.value = { mode: 'create', serieId: filtroSerieId.value }
}

function editarCapitulo(c) {
  capituloModal.value = { mode: 'edit', capitulo: c }
}

function onCapituloGuardado() {
  capituloModal.value = null
  setMensaje('ok', 'Capítulo guardado correctamente')
  cargarCapitulos()
}

// --- Eliminación ---
const confirmModal = ref(null)
const eliminando = ref(false)

function pedirEliminarSerie(s) {
  confirmModal.value = { tipo: 'serie', item: s }
}

function pedirEliminarCapitulo(c) {
  confirmModal.value = { tipo: 'capitulo', item: c }
}

async function confirmarEliminar() {
  if (!confirmModal.value || eliminando.value) return
  const { tipo, item } = confirmModal.value
  eliminando.value = true
  try {
    if (tipo === 'serie') {
      await eliminarSerieAdmin(item.id)
      series.value = series.value.filter((s) => s.id !== item.id)
      allSeries.value = allSeries.value.filter((s) => s.id !== item.id)
      if (String(filtroSerieId.value) === String(item.id)) {
        filtroSerieId.value = ''
        await cargarCapitulos()
      }
      setMensaje('ok', `"${item.nombre}" eliminada correctamente`)
    } else {
      await eliminarCapitulo(item.id)
      capitulos.value = capitulos.value.filter((c) => c.id !== item.id)
      setMensaje('ok', `Capítulo ${item.numero} de "${item.serie_nombre}" eliminado correctamente`)
    }
    confirmModal.value = null
  } catch (e) {
    setMensaje('error', 'Error al eliminar: ' + (e.response?.data?.error || e.message))
  } finally {
    eliminando.value = false
  }
}

onMounted(() => {
  cargarSeries()
  cargarAllSeries()
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
  border: 1px solid rgb(39, 174, 96);
  color: rgb(39, 174, 96);
}

.alert-error {
  background: rgba(0, 83, 156, 0.1);
  border: 1px solid var(--primary);
  color: var(--primary);
}

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

/* Tabs */
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

/* Filtros */
.filtros {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.filtro-buscar {
  display: flex;
  align-items: center;
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 20px;
  padding: 0 12px;
  transition: border-color 0.2s;
  flex: 1;
  min-width: 200px;
  max-width: 320px;
}

.filtro-buscar:focus-within {
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
  width: 100%;
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

.filtro-select {
  padding: 8px 12px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: white;
  color: var(--text-main);
  font-size: 0.8rem;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s;
}

.filtro-select:focus {
  border-color: var(--primary);
}

/* Tabla */
.tabla-opacity {
  opacity: 0.55;
  transition: opacity 0.2s;
}

.cover-img {
  width: 60px;
  height: 44px;
  object-fit: cover;
  border-radius: 4px;
  display: block;
}

.cover-placeholder {
  width: 60px;
  height: 44px;
  background: var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  font-size: 0.65rem;
}

.estado-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

.estado-en_emision {
  background: rgba(0, 83, 156, 0.1);
  color: var(--primary);
}

.estado-concluido {
  background: rgba(39, 174, 96, 0.12);
  color: rgb(39, 174, 96);
}

.estado-desconocido {
  background: var(--border-light);
  color: var(--text-muted);
}

.date-cell {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.cell-ellipsis {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.acciones {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.btn-danger {
  background: var(--primary);
  color: white;
}

/* Modal URL */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-box {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 28px 32px;
  width: 420px;
  max-width: 90vw;
}

.modal-box h3 {
  color: var(--primary);
  margin-bottom: 8px;
  font-size: 1.1rem;
}

.modal-desc {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-bottom: 16px;
}

.modal-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-main);
  font-size: 0.85rem;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.modal-input:focus {
  border-color: var(--primary);
}

.modal-error {
  color: var(--primary);
  font-size: 0.8rem;
  margin-top: 8px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>