import { defineStore } from 'pinia'
import { ref } from 'vue'
import { toggleFavorito } from '../api'

export const useFavoritesStore = defineStore('favorites', () => {
  const favoritos = ref(new Set())

  function isFavorito(id) {
    return favoritos.value.has(id)
  }

  function setFavorito(id, value) {
    if (value) {
      favoritos.value.add(id)
    } else {
      favoritos.value.delete(id)
    }
  }

  async function toggle(id) {
    try {
      const { data } = await toggleFavorito(id)
      setFavorito(id, data.favorito)
      return data.favorito
    } catch {
      return null
    }
  }

  function loadFromSeries(seriesList) {
    for (const s of seriesList) {
      if (s.favorito) {
        favoritos.value.add(s.id)
      }
    }
  }

  return {
    favoritos,
    isFavorito,
    setFavorito,
    toggle,
    loadFromSeries,
  }
})
