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
      <button class="download-badge" v-if="store.hasActive" @click="store.toggleDrawer">
        <span class="badge-icon">&#9660;</span>
        {{ store.activeCount }} descarga{{ store.activeCount > 1 ? 's' : '' }}
      </button>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDownloadStore } from '../stores/downloads'

const store = useDownloadStore()
const router = useRouter()
const searchQuery = ref('')

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

defineExpose({ searchQuery, setSearchValue })
</script>

<style scoped>
.navbar {
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
  gap: 16px;
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
</style>
