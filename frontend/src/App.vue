<template>
  <div id="app">
    <AppSidebar />
    <div class="app-main">
      <AppNavbar />
      <div class="container">
        <router-view />
      </div>
    </div>
    <DownloadDrawer />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import AppNavbar from './components/AppNavbar.vue'
import DownloadDrawer from './components/DownloadDrawer.vue'
import { useDownloadStore } from './stores/downloads'

const store = useDownloadStore()

onMounted(() => {
  store.restoreFromServer()
})
</script>

<style>
.app-main {
  margin-left: 60px;
  min-height: 100vh;
}
</style>
