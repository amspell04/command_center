<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { goalsApi, weakPointsApi } from '../api'
import { useTasks } from '../composables/useTasks'
import type { Goal, WeakPoint } from '../types'

const { tasks, load } = useTasks()
const goals = ref<Goal[]>([])
const weakPoints = ref<WeakPoint[]>([])
const failed = ref(false)
// Enough repeats that the track always outruns a wide screen; the loop shifts by exactly one copy.
const COPIES = 8

const items = computed(() => {
  const done = tasks.value.filter((t) => t.completed).length
  const covered = weakPoints.value.filter((w) => w.resolved).length
  return [
    `Tasks completed: ${done} of ${tasks.value.length}`,
    goals.value.length ? `Current goals: ${goals.value.map((g) => g.title).join(' · ')}` : 'No goals set',
    `Weak points: ${weakPoints.value.length} identified, ${covered} covered`,
  ]
})

onMounted(async () => {
  const results = await Promise.allSettled([
    load(),
    goalsApi.list().then((g) => (goals.value = g)),
    weakPointsApi.list().then((w) => (weakPoints.value = w)),
  ])
  failed.value = results.some((r) => r.status === 'rejected')
})
</script>

<template>
  <section class="ticker" aria-label="Progress">
    <!-- Repeated copies keep the bar full while looping; only the first is exposed to assistive tech. -->
    <div class="ticker__track">
      <ul v-for="copy in COPIES" :key="copy" :aria-hidden="copy > 1 || undefined">
        <li v-for="item in items" :key="item">{{ item }}</li>
      </ul>
    </div>
    <span v-if="failed" class="ticker__error" role="alert">Some progress data could not load</span>
  </section>
</template>

<style scoped>
.ticker {
  position: relative;
  display: flex;
  align-items: center;
  height: 28px;
  overflow: hidden;
  background: var(--accent-color);
  color: #fff;
  font-size: var(--text-xs);
  letter-spacing: 0.02em;
}
.ticker__track {
  display: flex;
  width: max-content;
  animation: ticker-scroll 40s linear infinite;
}
.ticker:hover .ticker__track {
  animation-play-state: paused;
}
ul {
  display: flex;
  flex-shrink: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}
li {
  padding: 0 var(--space-5);
  white-space: nowrap;
}
li::after {
  content: '•';
  margin-left: var(--space-5);
  opacity: 0.6;
}
.ticker__error {
  position: absolute;
  right: var(--space-3);
  padding: 0 var(--space-2);
  background: var(--warn-soft);
  color: var(--warn-color);
  border-radius: var(--radius-sm);
}
@keyframes ticker-scroll {
  to {
    transform: translateX(calc(-100% / 8)); /* one of COPIES */
  }
}
@media (prefers-reduced-motion: reduce) {
  .ticker__track {
    animation: none;
  }
  .ticker {
    overflow-x: auto;
  }
  ul[aria-hidden='true'] {
    display: none;
  }
}
</style>
