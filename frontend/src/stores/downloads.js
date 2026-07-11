import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getTaskState, getActiveTasks, cancelarTarea } from '../api'

export const useDownloadStore = defineStore('downloads', () => {
  const downloads = ref([])
  const drawerOpen = ref(false)
  const pollingIntervals = {}
  const callbacks = {}
  const restored = ref(false)

  const activeCount = computed(() =>
    downloads.value.filter(d => d.state === 'PROGRESS' || d.state === 'PENDING').length
  )

  const hasActive = computed(() => activeCount.value > 0)

  function addDownload(taskId, capituloId, serieNombre, numero, onComplete) {
    if (downloads.value.find(d => d.taskId === taskId)) return

    if (onComplete) {
      callbacks[taskId] = onComplete
    }

    downloads.value.push({
      taskId,
      capituloId,
      serie: serieNombre,
      numero,
      state: 'PENDING',
      fase: '',
      descargado: 0,
      total: 0,
      descargado_str: '0 B',
      total_str: '0 B',
      porcentaje: 0,
      servidor: '',
      message: '',
    })

    startPolling(taskId)
  }

  async function restoreFromServer() {
    if (restored.value) return
    restored.value = true

    try {
      const { data } = await getActiveTasks()
      if (!data || !data.length) return

      for (const t of data) {
        if (downloads.value.find(d => d.taskId === t.task_id)) continue

        downloads.value.push({
          taskId: t.task_id,
          capituloId: null,
          serie: t.serie,
          numero: t.numero,
          state: t.state,
          fase: t.fase,
          descargado: t.descargado,
          total: t.total,
          descargado_str: t.descargado_str,
          total_str: t.total_str,
          porcentaje: t.porcentaje,
          servidor: t.servidor,
          message: '',
        })

        startPolling(t.task_id)
      }

      if (downloads.value.length > 0) {
        drawerOpen.value = true
      }
    } catch {
      // silently fail
    }
  }

  function startPolling(taskId) {
    if (pollingIntervals[taskId]) return

    pollingIntervals[taskId] = setInterval(async () => {
      try {
        const { data } = await getTaskState(taskId)
        const item = downloads.value.find(d => d.taskId === taskId)
        if (!item) {
          stopPolling(taskId)
          return
        }

        Object.assign(item, data)

        if (data.state === 'SUCCESS') {
          if (callbacks[taskId]) {
            callbacks[taskId](data)
            delete callbacks[taskId]
          }
          stopPolling(taskId)
          setTimeout(() => removeDownload(taskId), 4000)
        } else if (data.state === 'FAILURE') {
          stopPolling(taskId)
          setTimeout(() => removeDownload(taskId), 4000)
        }
      } catch {
        // keep polling on error
      }
    }, 1500)
  }

  function stopPolling(taskId) {
    if (pollingIntervals[taskId]) {
      clearInterval(pollingIntervals[taskId])
      delete pollingIntervals[taskId]
    }
  }

  function removeDownload(taskId) {
    stopPolling(taskId)
    delete callbacks[taskId]
    downloads.value = downloads.value.filter(d => d.taskId !== taskId)
  }

  function toggleDrawer() {
    drawerOpen.value = !drawerOpen.value
  }

  async function cancelDownload(taskId) {
    try {
      await cancelarTarea(taskId)
    } catch {
      // proceed even if revoke fails
    }
    stopPolling(taskId)
    delete callbacks[taskId]
    downloads.value = downloads.value.filter(d => d.taskId !== taskId)
  }

  return {
    downloads,
    drawerOpen,
    activeCount,
    hasActive,
    addDownload,
    removeDownload,
    cancelDownload,
    toggleDrawer,
    restoreFromServer,
  }
})
