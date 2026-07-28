<template>
  <section class="tv-section">
    <div class="tv-section-heading">
      <h2>{{ title }}</h2>
      <span v-if="count != null">{{ count }}</span>
    </div>
    <div class="tv-row"><slot /></div>
  </section>
</template>

<script setup>
defineProps({ title: String, count: Number })
</script>
