<template>
  <div>
    <header class="tv-page-header"><div><h1>Configuración</h1><p>Servidor AnimeWing</p></div></header>
    <form class="tv-form" @submit.prevent="save">
      <div class="tv-field">
        <label for="tv-host">Dirección IP del computador</label>
        <input id="tv-host" ref="hostInput" v-model="host" :class="['tv-input', { 'tv-input--editing': editingField === 'host' }]" data-tv-focus :data-tv-editing="editingField === 'host'" :readonly="editingField !== 'host'" inputmode="decimal" enterkeyhint="next" placeholder="10.0.2.2" @click="activateField('host')" @keydown.enter.stop.prevent="activateField('host')">
      </div>
      <div class="tv-field">
        <label for="tv-port">Puerto</label>
        <input id="tv-port" ref="portInput" v-model="port" :class="['tv-input', { 'tv-input--editing': editingField === 'port' }]" data-tv-focus :data-tv-editing="editingField === 'port'" :readonly="editingField !== 'port'" inputmode="numeric" enterkeyhint="done" placeholder="8000" @click="activateField('port')" @keydown.enter.stop.prevent="activateField('port')">
      </div>
      <div v-if="message" :class="['tv-status', { 'tv-status--error': isError }]">{{ message }}</div>
      <div class="tv-actions">
        <button class="tv-button" data-tv-focus :disabled="saving" type="submit">{{ saving ? 'Probando…' : 'Guardar y probar' }}</button>
        <button class="tv-button tv-button--secondary" data-tv-focus type="button" @click="router.push('/')">Volver</button>
      </div>
    </form>
    <aside class="tv-server-preview"><span>La TV se conectará a</span><strong>{{ preview || 'Configura una IP y puerto' }}</strong><small>Emulador: 10.0.2.2 · TV física: IP local del computador. Puerto: 8000.</small></aside>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '../../src/stores/config'
import { useSpatialNavigation } from '../composables/useSpatialNavigation'
import { editTvValue } from '../plugins/tvKeyboard'
const router = useRouter(); const config = useConfigStore()
const host = ref(config.host || ''); const port = ref(config.port || '8000'); const saving = ref(false); const message = ref(''); const isError = ref(false)
const hostInput = ref(null); const portInput = ref(null); const editingField = ref('')
const preview = computed(() => host.value && port.value ? `http://${host.value}:${port.value}` : '')
async function activateField(field) {
  if (editingField.value === field) return
  editingField.value = field
  const result = await editTvValue({
    value: field === 'host' ? host.value : port.value,
    kind: field === 'port' ? 'number' : 'text',
    title: field === 'host' ? 'Dirección IP del computador' : 'Puerto',
  })
  if (!result.cancelled) {
    if (field === 'host') host.value = result.value
    else port.value = result.value
  }
  editingField.value = ''
  await nextTick()
  const input = field === 'host' ? hostInput.value : portInput.value
  input?.focus({ preventScroll: true })
}
async function save() {
  editingField.value = ''
  const cleanHost = host.value.trim().replace(/^https?:\/\//, '').replace(/\/$/, '')
  const cleanPort = port.value.trim()
  if (!cleanHost || !/^\d{1,5}$/.test(cleanPort) || Number(cleanPort) > 65535) { message.value = 'Ingresa una IP o host y un puerto válido.'; isError.value = true; return }
  saving.value = true; message.value = ''; isError.value = false
  try {
    await config.saveConfig(cleanHost, cleanPort)
    const response = await fetch(`http://${cleanHost}:${cleanPort}/api/series/`, { signal: AbortSignal.timeout(8000) })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    message.value = 'Conexión correcta. Configuración guardada.'
  } catch (e) { message.value = `No se pudo conectar: ${e.message}`; isError.value = true }
  finally { saving.value = false }
}
useSpatialNavigation({ onBack: () => router.push('/') })
</script>

<style scoped>
.tv-server-preview { max-width: 760px; display: grid; gap: 8px; margin-top: 38px; padding: 22px; border-radius: 15px; background: var(--tv-panel); }
.tv-server-preview span, .tv-server-preview small { color: var(--tv-muted); }
.tv-server-preview strong { color: var(--tv-yellow); font-size: 23px; }
</style>
