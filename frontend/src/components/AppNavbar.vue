<template>
  <nav class="navbar">
    <router-link to="/" class="navbar-brand">
      <h1>AnimeWing</h1>
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
      <div class="user-menu" ref="userMenuRef">
        <button class="nav-btn nav-btn-icon" @click="menuAbierto = !menuAbierto" title="Menú">
          &#9881;
        </button>
        <div v-if="menuAbierto" class="dropdown">
          <button class="dropdown-item" @click="abrirConfiguracion">
            <span>&#9881;</span> Configuración
          </button>
          <button class="dropdown-item" @click="abrirAdmin">
            <span>&#128736;</span> Administración
          </button>
        </div>
      </div>
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
          <p class="modal-desc">Pegá la URL de la serie (jkanime.net, latanime.org o animeflv)</p>
          <input
            v-model="urlInput"
            type="text"
            class="modal-input"
            placeholder="https://jkanime.net/shingeki-no-kyojin/ o https://animeflv.one/anime/..."
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
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useDownloadStore } from '../stores/downloads'
import { agregarSerieUrl } from '../api'

const store = useDownloadStore()
const router = useRouter()
const emit = defineEmits(['toggle-settings'])
const searchQuery = ref('')
const showUrlModal = ref(false)
const urlInput = ref('')
const urlError = ref('')
const agregando = ref(false)
const urlInputEl = ref(null)

const menuAbierto = ref(false)
const userMenuRef = ref(null)

function cerrarMenuFuera(event) {
  if (userMenuRef.value && !userMenuRef.value.contains(event.target)) {
    menuAbierto.value = false
  }
}

onMounted(() => document.addEventListener('click', cerrarMenuFuera))
onBeforeUnmount(() => document.removeEventListener('click', cerrarMenuFuera))

function abrirConfiguracion() {
  menuAbierto.value = false
  emit('toggle-settings')
}

function abrirAdmin() {
  menuAbierto.value = false
  router.push({ name: 'admin' })
}

let debounceTimer = null

function onSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    const query = searchQuery.value.trim()
    router.replace({ query: query ? { search: query } : {} })
  }, 300)
}

function clearSearch() {
  searchQuery.value = ''
  router.replace({ query: {} })
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
  background: var(--primary);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid var(--accent-cta);
  gap: 16px;
}

.navbar-brand h1 {
  color: white;
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
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: 20px;
  padding: 0 12px;
  transition: border-color 0.2s;
}

.search-box:focus-within {
  border-color: var(--accent-cta);
}

.search-icon {
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-right: 8px;
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-main);
  font-size: 0.85rem;
  padding: 8px 0;
  width: 100%;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-clear {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 4px;
}

.search-clear:hover {
  color: var(--accent-cta);
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-btn {
  background: transparent;
  color: white;
  border: 1px solid white;
  border-radius: 20px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: white;
  color: var(--primary);
}

.nav-btn-icon {
  font-size: 1.2rem;
  padding: 6px 10px;
  line-height: 1;
}

.user-menu {
  position: relative;
}

.dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  min-width: 210px;
  z-index: 999;
  overflow: hidden;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text-main);
  text-align: left;
  transition: background 0.15s;
}

.dropdown-item:hover {
  background: rgba(0, 83, 156, 0.06);
  color: var(--primary);
}

.download-badge {
  background: var(--accent-cta);
  color: var(--text-main);
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
  background: #e0b32a;
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
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 28px 32px;
  width: 420px;
  max-width: 90vw;
}

.modal-box h3 {
  color: var(--primary);
  margin-bottom: 8px;
  font-size: 1.1rem;
}

.modal-desc {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-bottom: 16px;
}

.modal-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-main);
  font-size: 0.85rem;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.modal-input:focus {
  border-color: var(--primary);
}

.modal-error {
  color: var(--primary);
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
