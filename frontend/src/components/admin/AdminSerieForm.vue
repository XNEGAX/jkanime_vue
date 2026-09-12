<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="$emit('cancel')">
      <div class="modal-box modal-wide">
        <h3>{{ serie ? 'Editar serie' : 'Nueva serie' }}</h3>

        <form @submit.prevent="guardar" novalidate>
          <div class="form-grid">
            <div class="field">
              <label>Nombre *</label>
              <input v-model="form.nombre" type="text" placeholder="Nombre de la serie" :disabled="guardando" />
              <span v-if="errores.nombre" class="field-error">{{ errores.nombre }}</span>
            </div>
            <div class="field">
              <label>Año *</label>
              <input v-model="form.anio" type="number" min="1900" max="2100" placeholder="2026" :disabled="guardando" />
              <span v-if="errores.anio" class="field-error">{{ errores.anio }}</span>
            </div>
          </div>

          <div class="field">
            <label>URL *</label>
            <input v-model="form.url" type="text" placeholder="https://jkanime.net/..." :disabled="guardando" />
            <p class="field-hint">El slug se genera automáticamente a partir de la URL.</p>
            <span v-if="errores.url" class="field-error">{{ errores.url }}</span>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Estado</label>
              <select v-model="form.estado" :disabled="guardando">
                <option value="en_emision">En emisión</option>
                <option value="concluido">Concluido</option>
                <option value="desconocido">Desconocido</option>
              </select>
            </div>
            <div class="field">
              <label>Día de emisión</label>
              <select v-model="form.dia_emision" :disabled="guardando">
                <option value="">Sin definir</option>
                <option value="lunes">Lunes</option>
                <option value="martes">Martes</option>
                <option value="miercoles">Miércoles</option>
                <option value="jueves">Jueves</option>
                <option value="viernes">Viernes</option>
                <option value="sabado">Sábado</option>
                <option value="domingo">Domingo</option>
              </select>
            </div>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Fuente</label>
              <select v-model="form.fuente" :disabled="guardando">
                <option value="jkanime">jkanime</option>
                <option value="latanime">latanime</option>
              </select>
            </div>
            <div class="field field-checkbox">
              <label class="checkbox-label">
                <input v-model="form.favorito" type="checkbox" :disabled="guardando" />
                Favorito
              </label>
            </div>
          </div>

          <div class="field">
            <label>Portada</label>
            <div class="portada-row">
              <div class="portada-preview">
                <img v-if="previewUrl" :src="previewUrl" alt="Portada" class="portada-img" />
                <div v-else class="portada-placeholder">Sin portada</div>
              </div>
              <div class="portada-actions">
                <input type="file" accept="image/*" @change="onFileChange" />
                <span class="field-hint">{{ form.portada ? form.portada.name : 'Se envía solo si elegís un archivo.' }}</span>
              </div>
            </div>
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
import { reactive, ref, onBeforeUnmount } from 'vue'
import { crearSerie, actualizarSerie } from '../../api'

const props = defineProps({
  serie: { type: Object, default: null },
})

const emit = defineEmits(['saved', 'cancel'])

const form = reactive({
  nombre: '',
  anio: '',
  url: '',
  estado: 'en_emision',
  dia_emision: '',
  fuente: 'jkanime',
  favorito: false,
  portada: null,
})

const errores = reactive({})
const errorBackend = ref('')
const guardando = ref(false)
const previewUrl = ref('')
let previewIsObject = false

if (props.serie) {
  form.nombre = props.serie.nombre || ''
  form.anio = props.serie.anio || ''
  form.url = props.serie.url || ''
  form.estado = props.serie.estado || 'en_emision'
  form.dia_emision = props.serie.dia_emision || ''
  form.fuente = props.serie.fuente || 'jkanime'
  form.favorito = !!props.serie.favorito
  previewUrl.value = props.serie.portada_url || ''
}

function onFileChange(e) {
  const file = e.target.files && e.target.files[0]
  if (previewIsObject && previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewIsObject = false
  }
  form.portada = file || null
  if (file) {
    previewUrl.value = URL.createObjectURL(file)
    previewIsObject = true
  }
}

function validar() {
  errores.nombre = ''
  errores.anio = ''
  errores.url = ''
  if (!form.nombre.trim()) errores.nombre = 'El nombre es obligatorio'
  const anio = parseInt(form.anio, 10)
  if (!form.anio || isNaN(anio) || anio < 1900 || anio > 2100) {
    errores.anio = 'Ingresá un año válido'
  }
  if (!form.url.trim()) errores.url = 'La URL es obligatoria'
  return !errores.nombre && !errores.anio && !errores.url
}

async function guardar() {
  if (!validar()) return
  guardando.value = true
  errorBackend.value = ''
  const data = {
    nombre: form.nombre.trim(),
    anio: parseInt(form.anio, 10),
    url: form.url.trim(),
    estado: form.estado,
    dia_emision: form.dia_emision,
    fuente: form.fuente,
    favorito: form.favorito,
  }
  if (form.portada) data.portada = form.portada
  try {
    if (props.serie) {
      await actualizarSerie(props.serie.id, data)
    } else {
      await crearSerie(data)
    }
    emit('saved')
  } catch (e) {
    errorBackend.value = e.response?.data?.error || e.message || 'Error al guardar la serie'
  } finally {
    guardando.value = false
  }
}

onBeforeUnmount(() => {
  if (previewIsObject && previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
})
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
  width: 420px;
  max-width: 90vw;
}

.modal-wide {
  width: 560px;
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

.field-checkbox {
  display: flex;
  align-items: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 600;
}

.checkbox-label input {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
}

.portada-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.portada-preview {
  flex-shrink: 0;
}

.portada-img {
  width: 90px;
  height: 64px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--border-light);
}

.portada-placeholder {
  width: 90px;
  height: 64px;
  background: var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.7rem;
}

.portada-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.portada-actions input[type='file'] {
  font-size: 0.78rem;
  color: var(--text-muted);
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