<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import ProgramEditor from '../components/ProgramEditor.vue'
import TrainingMaxes from '../components/TrainingMaxes.vue'
import TrainingProgress from '../components/TrainingProgress.vue'
import WeekBalance from '../components/WeekBalance.vue'
import WorkoutLog from '../components/WorkoutLog.vue'

// Bumped when a training max changes so the program's computed weights are fetched again.
const maxesVersion = ref(0)
// Bumped when a workout is saved or deleted so the progress charts are fetched again.
const logVersion = ref(0)
</script>

<template>
  <main class="training">
    <header class="page-bar">
      <RouterLink to="/" class="nav-link">← Home</RouterLink>
      <h1>Training</h1>
    </header>
    <TrainingProgress :refresh-key="logVersion" />
    <div class="training__row">
      <WorkoutLog @saved="logVersion++" @deleted="logVersion++" />
      <div class="training__side">
        <WeekBalance />
        <TrainingMaxes @saved="maxesVersion++" />
      </div>
    </div>
    <ProgramEditor :refresh-key="maxesVersion" />
  </main>
</template>

<style scoped>
.training {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.training__row {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: var(--space-6);
  align-items: start;
}
.training__side {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
@media (max-width: 1000px) {
  .training__row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
