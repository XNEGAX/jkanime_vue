import { createApp } from 'vue'
import { createPinia } from 'pinia'
import TvApp from './TvApp.vue'
import router from './router'
import './styles/tv.css'
import { useConfigStore } from '../src/stores/config'

const app = createApp(TvApp)
const pinia = createPinia()
app.use(pinia)
app.use(router)

async function bootstrap() {
  const config = useConfigStore()
  const { Capacitor } = await import('@capacitor/core')
  config.isCapacitor = Capacitor.isNativePlatform()
  await config.loadConfig()
  app.mount('#app')
}

bootstrap()
