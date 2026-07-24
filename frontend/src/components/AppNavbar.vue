<template>
  <nav class="navbar">
    <router-link to="/" class="navbar-brand">
      <h1>JKanime Gestor</h1>
    </router-link>
    <div class="navbar-center">
      <div class="search-box">
        <span class="search-icon">&#128269;</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar series..."
          class="search-input"
          @input="onSearch"
          @keydown.escape="clearSearch"
        />
        <button v-if="searchQuery" class="search-clear" @click="clearSearch">&#10005;</button>
      </div>
    </div>
    <div class="navbar-right">
      <button class="nav-btn" @click="showUrlModal = true" title="Agregar serie por URL">
        + Agregar URL
      </button>
      <button class="download-badge" v-if="store.hasActive" @click="store.toggleDrawer">
        <span class="badge-icon">&#9660;</span>
        {{ store.activeCount }} descarga{{ store.activeCount > 1 ? 's' : '' }}
      </button>
    </div>

    <!-- Modal Agregar URL -->
    <Teleport to="body">
      <div class="modal-overlay" v-if="showUrlModal" @click.self="closeModal">
        <div class="modal-box">
          <h3>Agregar serie por URL</h3>
          <p class="modal-desc">Pegá la URL de la serie (jkanime.net o latanime.org)</p>
          <input
            v-model="urlInput"
            type="text"
            class="modal-input"
            placeholder="https://jkanime.net/shingeki-no-kyojin/ o https://latanime.org/anime/..."
            @keydown.enter="agregarUrl"
            ref="urlInputEl"
            autofocus
          />
          <div v-if="urlError" class="modal-error">{{ urlError }}</div>
          <div class="modal-actions">
            <button class="btn btn-secondary btn-sm" @click="closeModal">Cancelar</button>
            <button class="btn btn-primary btn-sm" @click="agregarUrl" :disabled="agregando || !urlInput.trim()">
              {{ agregando ? 'Agregando...' : 'Agregar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </nav>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDownloadStore } from '../stores/downloads'
import { agregarSerieUrl } from '../api'

const store = useDownloadStore()
const router = useRouter()
const searchQuery = ref('')
const showUrlModal = ref(false)
const urlInput = ref('')
const urlError = ref('')
const agregando = ref(false)
const urlInputEl = ref(null)

let debounceTimer = null

function onSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    const query = searchQuery.value.trim()
    if (router.currentRoute.value.name !== 'series') {
      router.push({ name: 'series', query: query ? { search: query } : {} })
    } else {
      router.replace({ query: query ? { search: query } : {} })
    }
  }, 300)
}

function clearSearch() {
  searchQuery.value = ''
  if (router.currentRoute.value.name === 'series') {
    router.replace({ query: {} })
  }
}

function setSearchValue(val) {
  searchQuery.value = val
}

watch(showUrlModal, async (val) => {
  if (val) {
    urlError.value = ''
    urlInput.value = ''
    await nextTick()
    urlInputEl.value?.focus()
  }
})

function closeModal() {
  showUrlModal.value = false
  urlError.value = ''
  urlInput.value = ''
}

async function agregarUrl() {
  const url = urlInput.value.trim()
  if (!url) return
  agregando.value = true
  urlError.value = ''
  try {
    const { data } = await agregarSerieUrl(url)
    if (data.serie_id) {
      closeModal()
      await router.push({ name: 'chapters', params: { id: data.serie_id } })
    } else {
      urlError.value = data.message || 'Error al agregar la serie'
    }
  } catch (e) {
    urlError.value = e.response?.data?.error || e.message || 'Error de conexion'
  } finally {
    agregando.value = false
  }
}

defineExpose({ searchQuery, setSearchValue })
</script>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #1a1a2e;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid #e94560;
  gap: 16px;
}

.navbar-brand h1 {
  color: #e94560;
  font-size: 1.4rem;
  white-space: nowrap;
}

.navbar-center {
  flex: 1;
  max-width: 420px;
}

.search-box {
  display: flex;
  align-items: center;
  background: #16213e;
  border: 1px solid #333;
  border-radius: 20px;
  padding: 0 12px;
  transition: border-color 0.2s;
}

.search-box:focus-within {
  border-color: #e94560;
}

.search-icon {
  font-size: 0.9rem;
  color: #888;
  margin-right: 8px;
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: #e0e0e0;
  font-size: 0.85rem;
  padding: 8px 0;
  width: 100%;
}

.search-input::placeholder {
  color: #666;
}

.search-clear {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 4px;
}

.search-clear:hover {
  color: #e94560;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-btn {
  background: transparent;
  color: #e94560;
  border: 1px solid #e94560;
  border-radius: 20px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: #e94560;
  color: #fff;
}

.download-badge {
  background: #e94560;
  color: white;
  border: none;
  border-radius: 20px;
  padding: 6px 16px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: background 0.2s;
  animation: pulse 2s infinite;
  white-space: nowrap;
}

.download-badge:hover {
  background: #c73e54;
}

.badge-icon {
  margin-right: 4px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-box {
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 12px;
  padding: 28px 32px;
  width: 420px;
  max-width: 90vw;
}

.modal-box h3 {
  color: #e94560;
  margin-bottom: 8px;
  font-size: 1.1rem;
}

.modal-desc {
  color: #888;
  font-size: 0.85rem;
  margin-bottom: 16px;
}

.modal-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #333;
  border-radius: 8px;
  background: #16213e;
  color: #e0e0e0;
  font-size: 0.85rem;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.modal-input:focus {
  border-color: #e94560;
}

.modal-error {
  color: #e94560;
  font-size: 0.8rem;
  margin-top: 8px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>
