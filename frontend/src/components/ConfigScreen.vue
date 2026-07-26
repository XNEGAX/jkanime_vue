<template>
  <div v-if="show" class="config-overlay" @click.self="cancelar">
    <div class="config-box">
      <button class="config-close" @click="cancelar" title="Cerrar">&times;</button>

      <h2>AnimeWing</h2>
      <p class="config-desc">
        Configura la conexión al servidor backend.
        Ingresa el host y puerto donde corre el servidor Django.
      </p>

      <div class="config-field">
        <label for="host-input">Host</label>
        <input
          id="host-input"
          v-model="hostInput"
          type="text"
          placeholder="192.168.1.100 o 127.0.0.1"
          @input="clearError"
          @keydown.enter="guardar"
        />
      </div>

      <div class="config-field">
        <label for="port-input">Puerto</label>
        <input
          id="port-input"
          v-model="portInput"
          type="number"
          placeholder="8000"
          min="1"
          max="65535"
          @input="clearError"
          @keydown.enter="guardar"
        />
      </div>

      <div v-if="errorMessage" class="config-error">
        {{ errorMessage }}
      </div>

      <div class="config-actions">
        <button class="btn btn-secondary btn-sm" @click="cancelar">Cancelar</button>
        <button class="btn btn-primary btn-sm" @click="guardar" :disabled="guardando">
          {{ guardando ? 'Guardando...' : 'Guardar' }}
        </button>
      </div>

      <div v-if="testingConnection" class="config-testing">
        <span class="spinner"></span> Probando conexión...
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useConfigStore } from '../stores/config'

const props = defineProps({
  show: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const configStore = useConfigStore()

const hostInput = ref('')
const portInput = ref('8000')
const errorMessage = ref('')
const guardando = ref(false)
const testingConnection = ref(false)

watch(() => props.show, (val) => {
  if (val) {
    hostInput.value = configStore.host || ''
    portInput.value = configStore.port || '8000'
    errorMessage.value = ''
    nextTick(() => {
      const el = document.getElementById('host-input')
      if (el) el.focus()
    })
  }
})

function clearError() {
  errorMessage.value = ''
}

function cancelar() {
  emit('close')
}

async function guardar() {
  const host = hostInput.value.trim()
  const port = portInput.value.trim()

  if (!host) {
    errorMessage.value = 'El host es obligatorio'
    return
  }
  if (!port) {
    errorMessage.value = 'El puerto es obligatorio'
    return
  }
  const portNum = parseInt(port, 10)
  if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
    errorMessage.value = 'El puerto debe ser un número entre 1 y 65535'
    return
  }

  guardando.value = true
  testingConnection.value = true
  errorMessage.value = ''

  try {
    await configStore.saveConfig(host, port)

    const response = await fetch(`${configStore.baseUrl}/api/series/?search=`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(8000),
    })

    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`)
    }

    testingConnection.value = false
    emit('close')
  } catch (e) {
    testingConnection.value = false
    errorMessage.value = `No se pudo conectar al servidor: ${e.message}`
  } finally {
    guardando.value = false
  }
}
</script>

<style scoped>
.config-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
  padding: 20px;
}

.config-box {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 16px;
  padding: 36px 40px;
  width: 100%;
  max-width: 420px;
  text-align: center;
  position: relative;
}

.config-close {
  position: absolute;
  top: 12px;
  right: 16px;
  background: none;
  border: none;
  font-size: 1.6rem;
  color: var(--text-muted);
  cursor: pointer;
  line-height: 1;
  padding: 0;
}

.config-close:hover {
  color: var(--primary);
}

.config-box h2 {
  color: var(--primary);
  font-size: 1.6rem;
  margin-bottom: 8px;
}

.config-desc {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-bottom: 28px;
  line-height: 1.5;
}

.config-field {
  text-align: left;
  margin-bottom: 20px;
}

.config-field label {
  display: block;
  color: var(--text-main);
  font-size: 0.8rem;
  margin-bottom: 6px;
  font-weight: 600;
}

.config-field input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-main);
  font-size: 0.9rem;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.config-field input:focus {
  border-color: var(--primary);
}

.config-error {
  color: var(--primary);
  font-size: 0.8rem;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: rgba(0, 83, 156, 0.1);
  border-radius: 6px;
}

.config-actions {
  margin-top: 24px;
}

.config-testing {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
</style>
