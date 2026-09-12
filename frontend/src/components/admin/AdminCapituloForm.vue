<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="$emit('cancel')">
      <div class="modal-box">
        <h3>{{ esEdicion ? 'Editar capítulo' : 'Nuevo capítulo' }}</h3>

        <form @submit.prevent="guardar" novalidate>
          <div class="field">
            <label>Serie *</label>
            <select v-model="form.serie" :disabled="guardando">
              <option value="" disabled>Seleccioná una serie</option>
              <option v-for="s in series" :key="s.id" :value="s.id">{{ s.nombre }}</option>
            </select>
            <span v-if="errores.serie" class="field-error">{{ errores.serie }}</span>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Número *</label>
              <input v-model="form.numero" type="number" min="1" placeholder="1" :disabled="guardando" />
              <span v-if="errores.numero" class="field-error">{{ errores.numero }}</span>
            </div>
            <div class="field">
              <label>Último segundo</label>
              <input v-model="form.ultimo_segundo" type="number" min="0" step="1" placeholder="Opcional" :disabled="guardando" />
            </div>
          </div>

          <div class="field">
            <label>Fecha de publicación</label>
            <input v-model="form.fecha_publicacion" type="datetime-local" :disabled="guardando" />
            <p class="field-hint">Opcional. Si se deja vacío se guarda como nula.</p>
          </div>

          <div class="field">
            <label>URL fuente *</label>
            <input v-model="form.url_fuente" type="text" placeholder="https://jkanime.net/..." :disabled="guardando" />
            <span v-if="errores.url_fuente" class="field-error">{{ errores.url_fuente }}</span>
          </div>

          <div class="field">
            <label>Ruta archivo</label>
            <input v-model="form.ruta_archivo" type="text" placeholder="descargas/slug/ep-01.mp4 (opcional)" :disabled="guardando" />
          </div>

          <div v-if="errorBackend" class="alert alert-error">{{ errorBackend }}</div>

          <div class="modal-actions">
            <button type="button" class="btn btn-secondary btn-sm" @click="$emit('cancel')" :disabled="guardando">Cancelar</button>
            <button type="submit" class="btn btn-primary btn-sm" :disabled="guardando">
              {{ guardando ? 'Guardando...' : 'Guardar' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { crearCapitulo, actualizarCapitulo } from '../../api'

const props = defineProps({
  series: { type: Array, default: () => [] },
  capitulo: { type: Object, default: null },
  serieId: { type: [Number, String], default: '' },
})

const emit = defineEmits(['saved', 'cancel'])

const esEdicion = computed(() => !!props.capitulo)

const form = reactive({
  serie: '',
  numero: '',
  fecha_publicacion: '',
  url_fuente: '',
  ruta_archivo: '',
  ultimo_segundo: '',
})

if (props.capitulo) {
  form.serie = props.capitulo.serie
  form.numero = props.capitulo.numero
  form.fecha_publicacion = toDatetimeLocal(props.capitulo.fecha_publicacion)
  form.url_fuente = props.capitulo.url_fuente || ''
  form.ruta_archivo = props.capitulo.ruta_archivo || ''
  form.ultimo_segundo = props.capitulo.ultimo_segundo ?? ''
} else {
  form.serie = props.serieId
}

function toDatetimeLocal(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const errores = reactive({})
const errorBackend = ref('')
const guardando = ref(false)

function validar() {
  errores.serie = ''
  errores.numero = ''
  errores.url_fuente = ''
  if (!form.serie) errores.serie = 'Seleccioná una serie'
  const num = parseInt(form.numero, 10)
  if (!form.numero || isNaN(num) || num < 1) errores.numero = 'El número es obligatorio'
  if (!form.url_fuente.trim()) errores.url_fuente = 'La URL fuente es obligatoria'
  return !errores.serie && !errores.numero && !errores.url_fuente
}

async function guardar() {
  if (!validar()) return
  guardando.value = true
  errorBackend.value = ''
  const data = {
    serie: form.serie,
    numero: parseInt(form.numero, 10),
    url_fuente: form.url_fuente.trim(),
  }
  if (form.fecha_publicacion) {
    data.fecha_publicacion = new Date(form.fecha_publicacion).toISOString()
  } else if (esEdicion.value) {
    data.fecha_publicacion = null
  }
  if (form.ruta_archivo.trim()) {
    data.ruta_archivo = form.ruta_archivo.trim()
  }
  if (form.ultimo_segundo !== '') {
    data.ultimo_segundo = parseInt(form.ultimo_segundo, 10)
  }
  try {
    if (esEdicion.value) {
      await actualizarCapitulo(props.capitulo.id, data)
    } else {
      await crearCapitulo(data)
    }
    emit('saved')
  } catch (e) {
    errorBackend.value = e.response?.data?.error || e.message || 'Error al guardar el capítulo'
  } finally {
    guardando.value = false
  }
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
  padding: 20px;
}

.modal-box {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 28px 32px;
  width: 480px;
  max-width: 90vw;
}

.modal-box h3 {
  color: var(--primary);
  margin-bottom: 18px;
  font-size: 1.1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.field {
  margin-bottom: 14px;
}

.field label {
  display: block;
  color: var(--text-main);
  font-size: 0.8rem;
  margin-bottom: 6px;
  font-weight: 600;
}

.field input[type='text'],
.field input[type='number'],
.field input[type='datetime-local'],
.field select {
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

.field input:focus,
.field select:focus {
  border-color: var(--primary);
}

.field-hint {
  color: var(--text-muted);
  font-size: 0.75rem;
  margin-top: 6px;
  line-height: 1.4;
}

.field-error {
  color: var(--primary);
  font-size: 0.75rem;
  margin-top: 4px;
  display: block;
}

.alert {
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 0.9rem;
}

.alert-error {
  background: rgba(0, 83, 156, 0.1);
  border: 1px solid var(--primary);
  color: var(--primary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>