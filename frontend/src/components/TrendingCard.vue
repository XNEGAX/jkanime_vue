<template>
  <div class="trending-card" tabindex="0" role="button" @click="$emit('click')" @keydown.enter="$emit('click')" @keydown.space.prevent="$emit('click')">
    <div class="trending-card-img-wrap">
      <img
        v-if="image"
        :src="image"
        :alt="title"
        loading="lazy"
      />
      <div v-else class="trending-card-placeholder">Sin portada</div>
      <div v-if="downloadState" class="dl-overlay">
        <div class="dl-overlay-spinner"></div>
        <div class="dl-overlay-fase">{{ downloadState.fase || 'Iniciando...' }}</div>
        <div class="dl-overlay-bar">
          <div class="dl-overlay-bar-fill" :style="{ width: (downloadState.porcentaje || 0) + '%' }"></div>
        </div>
        <div class="dl-overlay-pct">{{ downloadState.porcentaje || 0 }}%</div>
      </div>
      <slot name="overlay"></slot>
    </div>
    <div class="trending-card-info">
      <div class="trending-card-title">{{ title }}</div>
      <div v-if="subtitle" class="trending-card-ep">{{ subtitle }}</div>
    </div>
    <button
      v-if="showFav"
      class="trending-card-fav"
      :class="{ 'trending-card-fav-active': isFavorite }"
      @click.stop="$emit('toggle-fav')"
      :title="favTitle"
    >
      &#9829;
    </button>
  </div>
</template>

<script setup>
defineProps({
  image: { type: String, required: false },
  title: { type: String, required: true },
  subtitle: { type: String, required: false },
  showFav: { type: Boolean, default: false },
  isFavorite: { type: Boolean, default: false },
  favTitle: { type: String, default: 'Quitar de favoritos' },
  downloadState: { type: Object, required: false },
})

defineEmits(['click', 'toggle-fav'])
</script>

<style scoped>
.trending-card {
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
  outline: none;
}

.trending-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 83, 156, 0.15);
}

.trending-card:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 0 0 3px var(--bg-primary), 0 0 0 5px var(--accent-cta);
  border-radius: 10px;
}

.trending-card-img-wrap {
  position: relative;
  overflow: hidden;
}

.trending-card-img-wrap img {
  width: 100%;
  aspect-ratio: 3/4;
  object-fit: cover;
  display: block;
}

.trending-card-placeholder {
  width: 100%;
  aspect-ratio: 3/4;
  background: var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 0.7rem;
}

.dl-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
}

.dl-overlay-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(0, 83, 156, 0.2);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.dl-overlay-fase {
  font-size: 0.65rem;
  color: #ccc;
  text-align: center;
  max-width: 90%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dl-overlay-bar {
  width: 80%;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.dl-overlay-bar-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.dl-overlay-pct {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--accent-cta);
}

.trending-card-info {
  padding: 8px 10px;
}

.trending-card-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trending-card-ep {
  font-size: 0.7rem;
  color: var(--primary);
  margin-top: 2px;
}

.trending-card-fav {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(0, 0, 0, 0.7);
  border: none;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  font-size: 1rem;
  cursor: pointer;
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0;
}

.trending-card:hover .trending-card-fav {
  opacity: 1;
}

.trending-card-fav:hover {
  transform: scale(1.15);
  background: rgba(0, 83, 156, 0.3);
}

.trending-card-fav-active {
  color: var(--accent-cta);
  opacity: 1;
}
</style>
