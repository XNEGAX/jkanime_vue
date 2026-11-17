import { createRouter, createWebHistory } from 'vue-router'
import FavoritesView from '../views/FavoritesView.vue'
import ChaptersView from '../views/ChaptersView.vue'

// Las tres pestañas del home son rutas distintas que comparten FavoritesView.
// `meta.tab` es la fuente de verdad del tab activo; la vista lo lee desde la
// ruta en vez de sessionStorage, así que back/forward y links directos funcionan.
const routes = [
  { path: '/', name: 'favorites', component: FavoritesView, meta: { tab: 'ultimos' } },
  { path: '/en-emision', name: 'en-emision', component: FavoritesView, meta: { tab: 'en_emision' } },
  { path: '/concluidos', name: 'concluidos', component: FavoritesView, meta: { tab: 'concluido' } },
  { path: '/serie/:id', name: 'chapters', component: ChaptersView },
  { path: '/series', name: 'series', component: () => import('../views/SeriesView.vue') },
  { path: '/admin', name: 'admin', component: () => import('../views/AdminView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to) {
    const saved = sessionStorage.getItem('animewing-nav-scroll')
    if (saved) {
      try {
        const { top, left, path } = JSON.parse(saved)
        if (path === to.path) {
          return { top: top || 0, left: left || 0 }
        }
      } catch {
        // ignore invalid JSON
      }
    }
    return { top: 0 }
  },
})

export default router
