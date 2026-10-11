<script setup lang="ts">
import TodayPanel from '@/components/TodayPanel.vue'
import NotesPanel from '@/components/NotesPanel.vue'
import TasksPanel from '@/components/TasksPanel.vue'
</script>

<template>
  <main class="home">
    <TasksPanel class="home__tasks" />
    <TodayPanel class="home__today" />
    <NotesPanel class="home__notes" />
  </main>
</template>

<style scoped>
.home {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  grid-template-areas:
    'tasks today'
    'tasks notes';
  gap: var(--space-5) var(--space-6);
  align-items: start;
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-5) var(--space-6);
}
.home__tasks {
  grid-area: tasks;
}
.home__today {
  grid-area: today;
}
.home__notes {
  grid-area: notes;
}
@media (max-width: 1000px) {
  .home {
    grid-template-columns: 1fr;
    grid-template-areas: 'today' 'tasks' 'notes';
    padding: var(--space-4);
  }
}
</style>
