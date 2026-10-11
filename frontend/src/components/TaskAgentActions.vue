<script setup lang="ts">
import { computed, ref } from 'vue'
import { agentsApi, errorMessage } from '../api'
import type { DayPlan } from '../types'

const plan = ref<DayPlan | null>(null)
const busy = ref<'plan' | null>(null)
const error = ref<string | null>(null)

function duration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? (m ? `${h} h ${m} min` : `${h} h`) : `${m} min`
}

const totalMinutes = computed(() => plan.value?.items.reduce((sum, i) => sum + (i.estimate_minutes ?? 0), 0) ?? 0)

async function planDay() {
  busy.value = 'plan'
  error.value = null
  try {
    plan.value = await agentsApi.planDay()
  } catch (e) {
    error.value = errorMessage(e)
  }
  busy.value = null
}
</script>

<template>
  <div class="agent">
    <div class="agent__buttons">
      <button :disabled="busy !== null" @click="planDay">{{ busy === 'plan' ? 'Planning…' : 'Plan my day' }}</button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section v-if="plan" aria-label="Day plan">
      <h3>Plan for {{ plan.date }}</h3>
      <p v-if="!plan.items.length">Nothing to plan.</p>
      <ol v-else>
        <li v-for="item in plan.items" :key="item.task_id">
          {{ item.title }}
          <strong v-if="item.estimate_minutes" class="estimate">~{{ duration(item.estimate_minutes) }}</strong>
          <small v-if="item.reason"> — {{ item.reason }}</small>
        </li>
      </ol>
      <p v-if="totalMinutes" class="total">Estimated total: {{ duration(totalMinutes) }}</p>
      <button @click="plan = null">Dismiss</button>
    </section>
  </div>
</template>

<style scoped>
.agent__buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.agent__buttons button {
  flex: 1;
}
section {
  margin-bottom: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
}
section h3 {
  font-size: var(--text-base);
}
ol {
  padding-left: var(--space-5);
}
li {
  margin-bottom: var(--space-2);
}
.estimate {
  margin-left: var(--space-2);
  font-size: var(--text-sm);
}
.total {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
}
</style>
