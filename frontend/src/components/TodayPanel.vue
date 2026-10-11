<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { agentsApi, errorMessage } from '../api'
import { useTasks } from '../composables/useTasks'
import type { DayPlan, Task, WeekStatus } from '../types'
import { duration, localToday, longDate } from '../utils/dates'

const { tasks, loading, load, toggleComplete } = useTasks()

const todayStr = localToday()
const plan = ref<DayPlan | null>(null)
const planning = ref(false)
const error = ref<string | null>(null)

const TOP = 3
const STATUS_LABEL: Record<WeekStatus, string> = {
  ON_TRACK: 'On track',
  AT_RISK: 'At risk',
  OFF_TRACK: 'Off track',
}

interface Entry {
  id: string
  task: Task | undefined
  title: string
  dueDate: string
  reason: string
  minutes: number | null
}

const fromTask = (t: Task): Entry => ({ id: t.id, task: t, title: t.title, dueDate: t.due_date, reason: '', minutes: null })

// The agent's order once a plan exists, otherwise everything due so far, oldest first.
const agenda = computed<Entry[]>(() => {
  if (plan.value) {
    return plan.value.items.map((i) => ({
      id: i.task_id,
      task: tasks.value.find((t) => t.id === i.task_id),
      title: i.title,
      dueDate: i.due_date,
      reason: i.reason,
      minutes: i.estimate_minutes,
    }))
  }
  return tasks.value.filter((t) => !t.completed && t.due_date <= todayStr).map(fromTask)
})
const priorities = computed(() => agenda.value.slice(0, TOP))
const alsoToday = computed(() => agenda.value.slice(TOP))
const comingUp = computed(() => {
  const end = plan.value?.week.end
  return tasks.value.filter((t) => !t.completed && t.due_date > todayStr && (!end || t.due_date <= end)).slice(0, 5)
})
const totalMinutes = computed(() => agenda.value.reduce((sum, e) => sum + (e.minutes ?? 0), 0))
const weekLine = computed(() => {
  const w = plan.value?.week
  if (!w) return ''
  return `${w.completed_so_far} of ${w.due_so_far} due so far done · ${w.overdue_open} overdue · ${w.due_remaining} later this week`
})

async function planDay() {
  planning.value = true
  error.value = null
  try {
    plan.value = await agentsApi.planDay()
  } catch (e) {
    error.value = errorMessage(e)
  }
  planning.value = false
}

async function toggle(task: Task) {
  error.value = null
  try {
    await toggleComplete(task)
  } catch (e) {
    error.value = errorMessage(e)
  }
}

onMounted(() => load().catch((e) => (error.value = errorMessage(e))))
</script>

<template>
  <section class="panel today" aria-label="Today">
    <header class="panel__header">
      <h2>Today · {{ longDate(todayStr) }}</h2>
      <div class="panel__actions">
        <button v-if="plan" class="btn--ghost btn--sm" @click="plan = null">Dismiss</button>
        <button class="btn--primary btn--sm" :disabled="planning" @click="planDay">
          {{ planning ? 'Planning…' : 'Plan my day' }}
        </button>
      </div>
    </header>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section v-if="plan" class="status" aria-label="Week status">
      <p v-if="plan.status" class="status__line">
        <span class="pill" :class="`pill--${plan.status.toLowerCase()}`">{{ STATUS_LABEL[plan.status] }}</span>
        <span>{{ plan.summary }}</span>
      </p>
      <p class="muted">{{ weekLine }}</p>
      <ul v-if="plan.goals.length" class="goals" aria-label="Goal check">
        <li v-for="g in plan.goals" :key="g.goal_id" :class="g.on_track ? 'goal--ok' : 'goal--off'">
          <span class="mark" aria-hidden="true">{{ g.on_track ? '✓' : '!' }}</span>
          <span><strong>{{ g.title }}</strong> <small>{{ g.note }}</small></span>
        </li>
      </ul>
    </section>

    <section aria-label="Day plan">
      <p v-if="loading && !agenda.length" class="muted">Loading…</p>
      <p v-else-if="!agenda.length" class="muted">{{ plan ? 'Nothing to plan.' : 'Nothing due. Enjoy the clear day.' }}</p>

      <template v-if="agenda.length">
        <h3 class="eyebrow">Top priorities</h3>
        <ol class="agenda">
          <li v-for="(e, i) in priorities" :key="e.id" class="slot slot--top">
            <span class="rank">{{ i + 1 }}</span>
            <input
              type="checkbox"
              :checked="e.task?.completed"
              :disabled="!e.task"
              :aria-label="`Complete ${e.title}`"
              @change="e.task && toggle(e.task)"
            />
            <div class="slot__main" :class="{ done: e.task?.completed }">
              <span class="slot__title">{{ e.title }}</span>
              <small v-if="e.reason">{{ e.reason }}</small>
              <small v-else-if="e.dueDate < todayStr" class="overdue">Overdue · {{ e.dueDate }}</small>
            </div>
            <strong v-if="e.minutes" class="est">~{{ duration(e.minutes) }}</strong>
          </li>
        </ol>

        <template v-if="alsoToday.length">
          <h3 class="eyebrow">Also today</h3>
          <ol class="agenda" start="4">
            <li v-for="(e, i) in alsoToday" :key="e.id" class="slot">
              <span class="rank">{{ i + TOP + 1 }}</span>
              <input
                type="checkbox"
                :checked="e.task?.completed"
                :disabled="!e.task"
                :aria-label="`Complete ${e.title}`"
                @change="e.task && toggle(e.task)"
              />
              <div class="slot__main" :class="{ done: e.task?.completed }">
                <span class="slot__title">{{ e.title }}</span>
                <small v-if="e.reason">{{ e.reason }}</small>
              </div>
              <strong v-if="e.minutes" class="est">~{{ duration(e.minutes) }}</strong>
            </li>
          </ol>
        </template>
        <p v-if="totalMinutes" class="muted total">Estimated total: {{ duration(totalMinutes) }}</p>
      </template>
    </section>

    <template v-if="comingUp.length">
      <h3 class="eyebrow">Coming up</h3>
      <ul class="upcoming">
        <li v-for="t in comingUp" :key="t.id">
          <small class="when">{{ t.due_date }}</small>
          <span>{{ t.title }}</span>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.status {
  margin-bottom: var(--space-2);
  padding-left: var(--space-3);
  border-left: 2px solid var(--accent-color);
}
.status__line {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin: 0 0 var(--space-1);
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
.pill--on_track {
  background: var(--ok-soft);
  color: var(--ok-color);
}
.pill--at_risk {
  background: var(--warn-soft);
  color: var(--warn-color);
}
.pill--off_track {
  background: var(--danger-soft);
  color: var(--danger-color);
}
.muted {
  margin: 0 0 var(--space-1);
}
.goals,
.agenda,
.upcoming {
  margin: 0;
  padding: 0;
  list-style: none;
}
.goals li {
  display: flex;
  gap: var(--space-2);
  align-items: baseline;
}
.mark {
  width: 1em;
  font-weight: 700;
}
.goal--ok .mark {
  color: var(--ok-color);
}
.goal--off .mark {
  color: var(--warn-color);
}
.eyebrow {
  margin-top: var(--space-4);
}
.slot {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-color);
}
.slot--top .slot__title {
  font-size: var(--text-lg);
  font-weight: 600;
}
.rank {
  flex-shrink: 0;
  width: 1.25rem;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--accent-color);
}
.slot input {
  flex-shrink: 0;
  margin-top: 3px;
}
.slot__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.done {
  text-decoration: line-through;
  color: var(--text-muted);
}
.overdue {
  color: var(--overdue-color);
}
.est {
  flex-shrink: 0;
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
}
.total {
  margin-top: var(--space-2);
}
.upcoming li {
  display: flex;
  gap: var(--space-3);
  padding: 2px 0;
}
.when {
  flex-shrink: 0;
  width: 5.5rem;
  font-variant-numeric: tabular-nums;
}
</style>
