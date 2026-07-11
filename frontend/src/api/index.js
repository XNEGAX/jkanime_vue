import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

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

export function getVideoUrl(capituloId) {
  return `/api/video/${capituloId}/`
}
