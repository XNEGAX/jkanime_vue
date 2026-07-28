import { useConfigStore } from '../stores/config'

async function request(path, { method = 'GET', params, data, headers = {}, cache } = {}) {
  const configStore = useConfigStore()
  const base = configStore.baseUrl ? `${configStore.baseUrl}/api` : '/api'
  const url = new URL(`${base}${path}`, window.location.origin)

  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  }

  const response = await fetch(url.toString(), {
    method,
    cache,
    headers: { Accept: 'application/json', ...(data !== undefined ? { 'Content-Type': 'application/json' } : {}), ...headers },
    body: data !== undefined ? JSON.stringify(data) : undefined,
  })
  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const error = new Error(payload?.error || payload?.detail || `HTTP ${response.status}`)
    error.response = { status: response.status, data: payload }
    throw error
  }
  return { data: payload, status: response.status, headers: response.headers }
}

const api = {
  get: (path, config = {}) => request(path, config),
  post: (path, data, config = {}) => request(path, { ...config, method: 'POST', data }),
  delete: (path, config = {}) => request(path, { ...config, method: 'DELETE' }),
}

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
    cache: 'no-store',
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
    cache: 'no-store',
  })
}

export function getActiveTasks() {
  return api.get('/tareas/activas/', {
    cache: 'no-store',
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
    cache: 'no-store',
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
