import { createRouter, createWebHistory } from 'vue-router'
import SeriesView from '../views/SeriesView.vue'
import ChaptersView from '../views/ChaptersView.vue'

import FavoritesView from '../views/FavoritesView.vue'

const routes = [
  { path: '/', name: 'series', component: SeriesView },
  { path: '/serie/:id', name: 'chapters', component: ChaptersView },
  { path: '/reproducir/:id', redirect: '/' },
  { path: '/favoritos', name: 'favorites', component: FavoritesView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
