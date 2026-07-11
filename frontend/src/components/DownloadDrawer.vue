<template>
  <Teleport to="body">
    <div class="drawer-overlay" v-if="store.drawerOpen" @click="store.toggleDrawer"></div>
    <div class="drawer" :class="{ open: store.drawerOpen }">
      <div class="drawer-header">
        <h3>Descargas activas ({{ store.downloads.length }})</h3>
        <button class="drawer-close" @click="store.toggleDrawer">&times;</button>
      </div>
      <div class="drawer-body">
        <div v-if="store.downloads.length === 0" class="drawer-empty">
          No hay descargas activas
        </div>
        <DownloadItem
          v-for="item in downloadsOrdenados"
          :key="item.taskId"
          :download="item"
        />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useDownloadStore } from '../stores/downloads'
import DownloadItem from './DownloadItem.vue'

const store = useDownloadStore()

const downloadsOrdenados = computed(() => {
  const completadas = []
  const descargando = []
  const enCola = []
  for (const d of store.downloads) {
    if (d.state === 'SUCCESS' || d.state === 'FAILURE') {
      completadas.push(d)
    } else if (d.state === 'PROGRESS') {
      descargando.push(d)
    } else {
      enCola.push(d)
    }
  }
  return [...completadas, ...descargando, ...enCola]
})
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
}

.drawer {
  position: fixed;
  top: 0;
  right: -400px;
  width: 380px;
  height: 100vh;
  background: #1a1a1a;
  border-left: 2px solid #e94560;
  z-index: 1000;
  transition: right 0.3s ease;
  display: flex;
  flex-direction: column;
}

.drawer.open {
  right: 0;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #2a2a2a;
}

.drawer-header h3 {
  color: #e94560;
  font-size: 1rem;
}

.drawer-close {
  background: none;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0 4px;
}

.drawer-close:hover {
  color: #e94560;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.drawer-empty {
  text-align: center;
  color: #555;
  padding: 40px 20px;
}
</style>
