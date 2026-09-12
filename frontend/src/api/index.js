import axios from 'axios'
import { useConfigStore } from '../stores/config'

const api = axios.create({
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const configStore = useConfigStore()
  if (configStore.baseUrl) {
    config.baseURL = `${configStore.baseUrl}/api`
  } else {
    config.baseURL = '/api'
  }
  return config
})

export function getApiBaseUrl() {
  const configStore = useConfigStore()
  return configStore.baseUrl ? `${configStore.baseUrl}/api` : '/api'
}

export function getSeries(search = '') {
  const params = search ? { search } : {}
  return api.get('/series/', { params })
}

export function getSerieDetail(id) {
  return api.get(`/series/${id}/`)
}

export function getFavoritos() {
  return api.get('/series/favoritos/')
}

export function toggleFavorito(serieId) {
  return api.post(`/series/${serieId}/favorito/`)
}

export function getCapitulos(serieId) {
  return api.get(`/series/${serieId}/capitulos/`)
}

export function verificarSeries() {
  return api.post('/series/verificar/')
}

export function getVerificarStatus() {
  return api.get('/series/verificar/', {
    headers: { 'Cache-Control': 'no-cache' },
  })
}

export function agregarSerieUrl(url) {
  return api.post('/series/agregar-url/', { url })
}

export function getCapituloDetail(id) {
  return api.get(`/capitulos/${id}/`)
}

export function descargarCapitulo(id) {
  return api.post(`/capitulos/${id}/descargar/`)
}

export function descargarTodos(serieId) {
  return api.post(`/series/${serieId}/descargar-todos/`)
}

export function getTaskState(taskId) {
  return api.get(`/tareas/${taskId}/`, {
    headers: { 'Cache-Control': 'no-cache' },
  })
}

export function getActiveTasks() {
  return api.get('/tareas/activas/', {
    headers: { 'Cache-Control': 'no-cache' },
  })
}

export function cancelarTarea(taskId) {
  return api.post(`/tareas/${taskId}/cancelar/`)
}

export function eliminarSerie(serieId) {
  return api.delete(`/series/${serieId}/eliminar/`)
}

export function refrescarPortada(serieId) {
  return api.post(`/series/${serieId}/refrescar-portada/`)
}

export function getVideoUrl(capituloId) {
  const configStore = useConfigStore()
  if (configStore.baseUrl) {
    return `${configStore.baseUrl}/api/video/${capituloId}/`
  }
  return `/api/video/${capituloId}/`
}

export function getVideoBeaconUrl(capituloId) {
  const configStore = useConfigStore()
  if (configStore.baseUrl) {
    return `${configStore.baseUrl}/api/video/${capituloId}/`
  }
  return `/api/video/${capituloId}/`
}

export function guardarProgreso(capituloId, segundo) {
  return api.post(`/capitulos/${capituloId}/progreso/`, { segundo })
}

export function getGuardarProgresoUrl(capituloId) {
  const configStore = useConfigStore()
  if (configStore.baseUrl) {
    return `${configStore.baseUrl}/api/capitulos/${capituloId}/progreso/`
  }
  return `/api/capitulos/${capituloId}/progreso/`
}

export function verificarCapitulo(capituloId) {
  return api.get(`/capitulos/${capituloId}/verificar/`, {
    headers: { 'Cache-Control': 'no-cache' },
  })
}

export function repararCapitulo(capituloId) {
  return api.post(`/capitulos/${capituloId}/reparar/`)
}

export function getUltimosEpisodios() {
  return api.get('/ultimos-episodios/')
}

export function getFavoritosByEstado(estado, dia, letras) {
  const params = { estado }
  if (dia) params.dia = dia
  if (letras) params.letras = letras
  return api.get('/series/favoritos/', { params })
}

// --- Admin CRUD ---

function esMultipart(data) {
  if (data instanceof FormData) return true
  if (!data || typeof data !== 'object') return false
  return Object.values(data).some((v) => v instanceof File || v instanceof Blob)
}

function toRequestBody(data) {
  if (!esMultipart(data)) return data
  if (data instanceof FormData) return data
  const fd = new FormData()
  for (const [key, value] of Object.entries(data)) {
    if (value === null || value === undefined) continue
    if (value && typeof value === 'object' && !(value instanceof File) && !(value instanceof Blob)) {
      fd.append(key, JSON.stringify(value))
    } else {
      fd.append(key, value)
    }
  }
  return fd
}

export function getAdminSeries(params = {}) {
  return api.get('/series/', { params })
}

export function crearSerie(data) {
  return api.post('/series/', toRequestBody(data))
}

export function actualizarSerie(id, data) {
  return api.patch(`/series/${id}/`, toRequestBody(data))
}

export function eliminarSerieAdmin(id) {
  return api.delete(`/series/${id}/`)
}

export function getAdminCapitulos(params = {}) {
  return api.get('/capitulos/', { params })
}

export function crearCapitulo(data) {
  return api.post('/capitulos/', toRequestBody(data))
}

export function actualizarCapitulo(id, data) {
  return api.patch(`/capitulos/${id}/`, toRequestBody(data))
}

export function eliminarCapitulo(id) {
  return api.delete(`/capitulos/${id}/`)
}
