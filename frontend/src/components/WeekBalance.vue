<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { agentsApi, errorMessage } from '../api'
import type { BalanceStatus, WeekBalance } from '../types'
import { localToday, longDate } from '../utils/dates'

// Asks the training agent how this week's tasks line up with the gym sessions. The server counts everything; the
// model only judges and suggests, so the table always shows the real numbers.
const result = ref<WeekBalance | null>(null)
const running = ref(false)
const error = ref<string | null>(null)

const STATUS_LABEL: Record<BalanceStatus, string> = { BALANCED: 'Balanced', TIGHT: 'Tight', OVERLOADED: 'Overloaded' }

async function run() {
  running.value = true
  error.value = null
  try {
    result.value = await agentsApi.balanceWeek(localToday(), result.value !== null)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    running.value = false
  }
}

onMounted(() => {
  // This week's earlier run, if any.
  agentsApi.storedBalance(localToday()).then((r) => (result.value ??= r)).catch(() => {})
})
</script>

<template>
  <section class="section balance">
    <header class="section__head">
      <h2>Week balance</h2>
      <button v-if="result" type="button" class="btn--ghost btn--sm" @click="(result = null), (error = null)">Dismiss</button>
      <button type="button" class="btn--primary btn--sm" :disabled="running" @click="run">
        {{ running ? 'Balancing…' : result ? 'Re-balance' : 'Balance my week' }}
      </button>
    </header>
    <p v-if="!result && !error" class="balance__hint">Checks this week’s tasks against your gym days and recommends food, sleep, water and caffeine for each gym day.</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <template v-if="result">
      <p v-if="result.meet || result.program" class="muted" data-testid="context">
        <template v-if="result.program">{{ result.program }}</template>
        <template v-if="result.program && result.meet"> · </template>
        <template v-if="result.meet">{{ result.meet.title }} in {{ result.meet.days_left }} {{ result.meet.days_left === 1 ? 'day' : 'days' }}</template>
      </p>

      <p v-if="result.status" class="balance__status">
        <span class="pill" :class="`pill--${result.status.toLowerCase()}`" data-testid="status">{{ STATUS_LABEL[result.status] }}</span>
        <span>{{ result.summary }}</span>
      </p>
      <p v-else class="muted" data-testid="no-gym">No gym sessions this week, so there is nothing to balance.</p>

      <ul v-if="result.suggestions.length" class="balance__suggestions" aria-label="Suggestions">
        <li v-for="s in result.suggestions" :key="s.date + s.action">
          <strong>{{ longDate(s.date) }}</strong> {{ s.action }}
        </li>
      </ul>

      <table class="data-table balance__days">
        <thead>
          <tr>
            <th>Day</th>
            <th>Tasks</th>
            <th>Gym</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in result.days" :key="d.date" data-testid="day">
            <td>{{ d.weekday }}</td>
            <td :title="d.task_titles.join(', ')">{{ d.tasks_done }} of {{ d.tasks_due }} done</td>
            <td>
              <template v-if="d.gym">{{ d.gym.lifts.join(' · ') }} <span class="muted">({{ d.gym.logged ? 'logged' : 'planned' }})</span></template>
              <span v-else class="muted">Rest</span>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<style scoped>
.balance__status {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}
.pill {
  flex-shrink: 0;
  padding: 1px var(--space-2);
  border-radius: var(--radius-pill);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.pill--balanced {
  background: var(--ok-soft);
  color: var(--ok-color);
}
.pill--tight {
  background: var(--warn-soft);
  color: var(--warn-color);
}
.pill--overloaded {
  background: var(--danger-soft, var(--warn-soft));
  color: var(--danger-color);
}
.balance__hint {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--card-color);
  color: var(--text-muted);
  font-size: var(--text-sm);
}
</style>
