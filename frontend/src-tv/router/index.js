import { createRouter, createWebHashHistory } from 'vue-router'
import TvHomeView from '../views/TvHomeView.vue'
import TvSeriesView from '../views/TvSeriesView.vue'
import TvChaptersView from '../views/TvChaptersView.vue'
import TvDownloadsView from '../views/TvDownloadsView.vue'
import TvAddSeriesView from '../views/TvAddSeriesView.vue'
import TvSettingsView from '../views/TvSettingsView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'tv-home', component: TvHomeView },
    { path: '/series', name: 'tv-series', component: TvSeriesView },
    { path: '/serie/:id', name: 'tv-chapters', component: TvChaptersView },
    { path: '/descargas', name: 'tv-downloads', component: TvDownloadsView },
    { path: '/agregar', name: 'tv-add', component: TvAddSeriesView },
    { path: '/configuracion', name: 'tv-settings', component: TvSettingsView },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

export default router
