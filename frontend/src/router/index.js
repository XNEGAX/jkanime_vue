import { createRouter, createWebHistory } from 'vue-router'
import FavoritesView from '../views/FavoritesView.vue'
import ChaptersView from '../views/ChaptersView.vue'

const routes = [
  { path: '/', name: 'favorites', component: FavoritesView },
  { path: '/serie/:id', name: 'chapters', component: ChaptersView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to) {
    if (to.path === '/') {
      const saved = sessionStorage.getItem('animewing-nav-scroll')
      if (saved) {
        try {
          const { top, left } = JSON.parse(saved)
          return { top: top || 0, left: left || 0 }
        } catch {
          return { top: 0 }
        }
      }
    }
    return { top: 0 }
  },
})

export default router
