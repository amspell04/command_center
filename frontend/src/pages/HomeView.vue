<script setup lang="ts">
import BriefingPanel from '@/components/BriefingPanel.vue'
import NotesPanel from '@/components/NotesPanel.vue'
import TasksPanel from '@/components/TasksPanel.vue'

const today = new Date().toLocaleDateString(undefined, {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
})
</script>

<template>
  <main class="home">
    <header class="home__header">
      <h1>Command Center</h1>
      <span>{{ today }}</span>
    </header>

    <div class="home__grid">
      <TasksPanel class="home__tasks" />
      <BriefingPanel class="home__briefing" />
      <NotesPanel class="home__notes" />
    </div>
  </main>
</template>

<style scoped>
.home {
  padding: 1rem 1.5rem;
}
.home__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.home__grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(3, 1fr);
  align-items: start;
}
@media (max-width: 1000px) {
  .home__grid {
    grid-template-columns: 1fr;
  }
}
</style>
