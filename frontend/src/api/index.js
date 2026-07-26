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

export function getFavoritosByEstado(estado) {
  return api.get('/series/favoritos/', { params: { estado } })
}
