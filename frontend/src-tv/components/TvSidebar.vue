<template>
  <aside class="tv-sidebar">
    <div class="tv-brand">AWTV</div>
    <nav>
      <router-link v-for="item in items" :key="item.to" :to="item.to" data-tv-focus class="tv-nav-item">
        <span class="tv-nav-icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script setup>
const items = [
  { to: '/', icon: '⌂', label: 'Inicio' },
  { to: '/series', icon: '▦', label: 'Series' },
  { to: '/agregar', icon: '+', label: 'Agregar' },
  { to: '/configuracion', icon: '⚙', label: 'Ajustes' },
]
</script>
