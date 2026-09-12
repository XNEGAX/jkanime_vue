<template>
  <ConfigScreen v-if="showConfigScreen" />
  <ConfigScreen :show="showSettings" @close="showSettings = false" v-else />
  <div v-if="!showConfigScreen" id="app">
    <AppSidebar />
    <div class="app-main">
      <AppNavbar @toggle-settings="showSettings = !showSettings" />
      <div class="container">
        <keep-alive include="FavoritesView">
          <router-view />
        </keep-alive>
      </div>
    </div>
    <DownloadDrawer />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useConfigStore } from './stores/config'
import AppNavbar from './components/AppNavbar.vue'
import AppSidebar from './components/AppSidebar.vue'
import DownloadDrawer from './components/DownloadDrawer.vue'
import ConfigScreen from './components/ConfigScreen.vue'
import { useDownloadStore } from './stores/downloads'

const configStore = useConfigStore()
const store = useDownloadStore()
const showSettings = ref(false)

const showConfigScreen = computed(() => {
  return configStore.isCapacitor.value && !configStore.isConfigured.value
})

if (!showConfigScreen.value) {
  store.restoreFromServer()
}
</script>

<style>
.app-main {
  margin-left: 60px;
  min-height: 100vh;
}
</style>
