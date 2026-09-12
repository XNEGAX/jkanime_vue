<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="cancelar">
      <div class="modal-box modal-confirm">
        <h3>Confirmar eliminación</h3>
        <p class="confirm-text">
          <template v-if="tipo === 'serie'">
            Se eliminará la serie <strong>"{{ item.nombre }}"</strong>. También se borrarán sus capítulos y los archivos en disco.
          </template>
          <template v-else>
            Se eliminará el capítulo <strong>Nº {{ item.numero }}</strong> de <strong>"{{ item.serie_nombre }}"</strong>. También se borrará el archivo en disco si existe.
          </template>
        </p>
        <p class="confirm-warn">Esta acción no se puede deshacer.</p>
        <div class="modal-actions">
          <button class="btn btn-secondary btn-sm" @click="cancelar" :disabled="loading">Cancelar</button>
          <button class="btn btn-danger btn-sm" @click="$emit('confirm')" :disabled="loading">
            {{ loading ? 'Eliminando...' : 'Eliminar' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  tipo: { type: String, required: true },
  item: { type: Object, required: true },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])

function cancelar() {
  if (props.loading) return
  emit('cancel')
}
</script>

<style scoped>
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
  width: 460px;
  max-width: 90vw;
}

.modal-box h3 {
  color: var(--primary);
  margin-bottom: 12px;
  font-size: 1.1rem;
}

.confirm-text {
  color: var(--text-main);
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 10px;
}

.confirm-warn {
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-bottom: 8px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.btn-danger {
  background: var(--primary);
  color: white;
}
</style>