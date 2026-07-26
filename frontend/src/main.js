import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { useConfigStore } from './stores/config'

const app = createApp(App)
app.use(createPinia())
app.use(router)

const configStore = useConfigStore()

async function bootstrap() {
  const { Capacitor } = await import('@capacitor/core')
  configStore.isCapacitor = Capacitor.isNativePlatform()

  await configStore.loadConfig()

  app.mount('#app')
}

bootstrap()
