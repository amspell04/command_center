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
const logging = ref(false)
</script>

<template>
  <main class="training">
    <header class="page-bar">
      <RouterLink to="/" class="nav-link">← Home</RouterLink>
      <h1>Training</h1>
      <div class="page-bar__end">
        <button type="button" class="btn--primary" @click="logging = true">Log a workout</button>
      </div>
    </header>
    <TrainingMaxes @saved="maxesVersion++" />
    <TrainingProgress :refresh-key="logVersion" />
    <WeekBalance />
    <ProgramEditor :refresh-key="maxesVersion" />
    <WorkoutLog v-if="logging" @close="logging = false" @saved="logVersion++" @deleted="logVersion++" />
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
</style>
