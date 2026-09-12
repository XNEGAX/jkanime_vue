<template>
  <aside class="sidebar">
    <router-link to="/" class="sidebar-link" :class="{ active: isActive('favorites') }">
      <span class="sidebar-icon">&#9829;</span>
      <span class="sidebar-label">Favoritos</span>
    </router-link>
    <router-link to="/series" class="sidebar-link" :class="{ active: isActive('series') }">
      <span class="sidebar-icon">&#127968;</span>
      <span class="sidebar-label">Series</span>
    </router-link>
    <router-link to="/admin" class="sidebar-link" :class="{ active: isActive('admin') }">
      <span class="sidebar-icon">&#9881;</span>
      <span class="sidebar-label">Admin</span>
    </router-link>
  </aside>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

function isActive(name) {
  return route.name === name
}
</script>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 60px;
  height: 100vh;
  background: var(--primary);
  border-right: 2px solid var(--accent-cta);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 16px;
  gap: 4px;
  z-index: 100;
}

.sidebar-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.5);
  transition: all 0.2s;
  text-decoration: none;
}

.sidebar-link:hover {
  color: var(--accent-cta);
  background: rgba(244, 196, 48, 0.15);
}

.sidebar-link.active {
  color: var(--accent-cta);
  background: rgba(244, 196, 48, 0.2);
}

.sidebar-icon {
  font-size: 1.3rem;
  line-height: 1;
}

.sidebar-label {
  font-size: 0.55rem;
  font-weight: 600;
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
</style>
