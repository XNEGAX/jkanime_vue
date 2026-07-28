<template>
  <article class="tv-card" data-tv-focus tabindex="0" @click="$emit('select')">
    <div class="tv-card-image">
      <img v-if="resolvedImage" :src="resolvedImage" :alt="title">
      <div v-else class="tv-card-placeholder">AW</div>
      <span v-if="badge" :class="['tv-card-badge', { 'tv-card-badge--yellow': badgeTone === 'yellow' }]">{{ badge }}</span>
      <div v-if="progress != null" class="tv-card-progress"><span :style="{ width: progress + '%' }"></span></div>
    </div>
    <h3>{{ title }}</h3>
    <p v-if="subtitle">{{ subtitle }}</p>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { getMediaUrl } from '../../src/api'

const props = defineProps({
  image: String,
  title: { type: String, required: true },
  subtitle: String,
  badge: String,
  badgeTone: String,
  progress: Number,
})
const resolvedImage = computed(() => getMediaUrl(props.image))
defineEmits(['select'])
</script>
