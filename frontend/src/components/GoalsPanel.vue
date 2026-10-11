<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { errorMessage, goalsApi } from '../api'
import type { Goal } from '../types'
import GoalModal from './GoalModal.vue'

const goals = ref<Goal[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// undefined = closed, null = create, Goal = edit
const modalGoal = ref<Goal | null | undefined>(undefined)

async function load() {
  loading.value = true
  error.value = null
  try {
    goals.value = await goalsApi.list()
  } catch (e) {
    error.value = errorMessage(e)
  }
  loading.value = false
}

function onSaved(saved: Goal) {
  goals.value = goals.value.some((g) => g.id === saved.id)
    ? goals.value.map((g) => (g.id === saved.id ? saved : g))
    : [...goals.value, saved]
}

onMounted(load)
</script>

<template>
  <section class="panel">
    <header class="panel__header">
      <h2>Goals</h2>
      <button class="btn--primary btn--sm" @click="modalGoal = null">New goal</button>
    </header>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>
    <p v-else-if="!goals.length && !loading" class="muted">No goals yet. Your day plan checks progress against them.</p>

    <ul>
      <li v-for="goal in goals" :key="goal.id">
        <button class="goal" :aria-label="`Edit ${goal.title}`" @click="modalGoal = goal">
          <span>{{ goal.title }}</span>
          <small v-if="goal.details">{{ goal.details }}</small>
        </button>
      </li>
    </ul>

    <GoalModal
      v-if="modalGoal !== undefined"
      :goal="modalGoal ?? undefined"
      @close="modalGoal = undefined"
      @saved="onSaved"
      @deleted="(id) => (goals = goals.filter((g) => g.id !== id))"
    />
  </section>
</template>

<style scoped>
ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}
.goal {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: calc(100% + var(--space-4));
  margin: 0 calc(-1 * var(--space-2));
  padding: var(--space-1) var(--space-2);
  min-height: 0;
  border: none;
  background: none;
  text-align: left;
  font-weight: 500;
}
.goal small {
  font-weight: 400;
}
.goal:hover:not(:disabled) {
  background: var(--card-color);
}
</style>
