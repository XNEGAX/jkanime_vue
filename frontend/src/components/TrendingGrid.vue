<template>
  <div
    class="trending-grid"
    :style="{
      '--grid-min': minCardWidth + 'px',
      '--grid-gap': gap + 'px',
    }"
  >
    <slot></slot>
  </div>
</template>

<script setup>
defineProps({
  minCardWidth: { type: Number, default: 160 },
  gap: { type: Number, default: 16 },
})
</script>

<style scoped>
.trending-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--grid-min), 1fr));
  gap: var(--grid-gap);
}
</style>
