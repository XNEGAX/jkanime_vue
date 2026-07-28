import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { Preferences } from '@capacitor/preferences'

const CONFIG_KEY = 'server_config'

export const useConfigStore = defineStore('config', () => {
  const host = ref('')
  const port = ref('')
  const loaded = ref(false)
  const isCapacitor = ref(false)

  const baseUrl = computed(() => {
    if (!host.value || !port.value) return ''
    return `http://${host.value}:${port.value}`
  })

  const isConfigured = computed(() => !!host.value && !!port.value)

  async function loadConfig() {
    if (loaded.value) return

    try {
      const result = await Preferences.get({ key: CONFIG_KEY })
      if (result.value) {
        const config = JSON.parse(result.value)
        host.value = config.host || ''
        port.value = config.port || ''
        loaded.value = true
        return
      }
    } catch {
      // Preferences not available — fall through to localStorage
    }

    try {
      const raw = localStorage.getItem(CONFIG_KEY)
      if (raw) {
        const config = JSON.parse(raw)
        host.value = config.host || ''
        port.value = config.port || ''
      }
    } catch {
      // ignore
    }

    loaded.value = true
  }

  async function saveConfig(newHost, newPort) {
    host.value = newHost
    port.value = newPort

    const payload = JSON.stringify({ host: newHost, port: newPort })

    try {
      await Preferences.set({ key: CONFIG_KEY, value: payload })
      return
    } catch {
      // Preferences not available — fall through to localStorage
    }

    try {
      localStorage.setItem(CONFIG_KEY, payload)
    } catch {
      // ignore
    }
  }

  async function clearConfig() {
    host.value = ''
    port.value = ''

    try {
      await Preferences.remove({ key: CONFIG_KEY })
    } catch {
      // ignore
    }
  }

  return {
    host,
    port,
    loaded,
    isCapacitor,
    baseUrl,
    isConfigured,
    loadConfig,
    saveConfig,
    clearConfig,
  }
})
