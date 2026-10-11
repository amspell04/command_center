<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorMessage } from '../api'
import { useTasks } from '../composables/useTasks'
import type { Task } from '../types'
import { localToday } from '../utils/dates'
import TaskModal from './TaskModal.vue'

const { tasks, loading, load: loadTasks, upsert, dropLocal, toggleComplete, remove } = useTasks()
const error = ref<string | null>(null)

const todayStr = localToday()

// undefined = closed, null = create, Task = edit
const modalTask = ref<Task | null | undefined>(undefined)

const open = computed(() => tasks.value.filter((t) => !t.completed))
const overdueTasks = computed(() => open.value.filter((t) => t.due_date < todayStr))
const todayTasks = computed(() => open.value.filter((t) => t.due_date === todayStr))
const upcomingTasks = computed(() => open.value.filter((t) => t.due_date > todayStr))
// Upcoming and Completed are capped behind a "See more" toggle; Overdue and Today always show in full.
const LIMITS: Record<string, number> = { Upcoming: 5, Completed: 3 }
const expanded = ref<Record<string, boolean>>({})
// Tasks have no completion timestamp, so "latest" = most recent due date.
const doneTasks = computed(() => [...tasks.value.filter((t) => t.completed)].reverse())

const completedCount = computed(() => doneTasks.value.length)
const remainingCount = computed(() => open.value.length)

const groups = computed(() =>
  [
    { name: 'Overdue', all: overdueTasks.value, empty: '' },
    { name: 'Today', all: todayTasks.value, empty: 'Nothing due today.' },
    { name: 'Upcoming', all: upcomingTasks.value, empty: 'Nothing upcoming.' },
    { name: 'Completed', all: doneTasks.value, empty: '' },
  ].map((g) => {
    const limit = LIMITS[g.name]
    const hidden = limit ? Math.max(0, g.all.length - limit) : 0
    return { ...g, hidden, items: limit && !expanded.value[g.name] ? g.all.slice(0, limit) : g.all }
  }),
)

async function run(fn: () => Promise<void>) {
  error.value = null
  try {
    await fn()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

const load = () => run(loadTasks)

// Tasks delete immediately, no confirmation.
const deleteTask = (task: Task) => run(() => remove(task))

onMounted(load)
</script>

<template>
  <section class="panel">
    <div class="panel__header">
      <h2>Tasks</h2>
      <button class="btn--primary btn--sm" @click="modalTask = null">New task</button>
    </div>

    <div class="panel__body">
    <p class="scoreboard" aria-label="Task scoreboard">
      <span class="score"><strong data-testid="score-done">{{ completedCount }}</strong> Completed</span>
      <span class="score"><strong data-testid="score-open">{{ remainingCount }}</strong> Not completed</span>
    </p>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>

    <template v-for="group in groups" :key="group.name">
      <template v-if="group.items.length || group.empty">
        <h3 class="group" :class="{ 'group--overdue': group.name === 'Overdue' }">{{ group.name }}</h3>
        <ul :class="{ 'list--overdue': group.name === 'Overdue' }">
          <li v-for="task in group.items" :key="task.id" class="row">
            <input type="checkbox" :checked="task.completed" :aria-label="`Complete ${task.title}`" @change="run(() => toggleComplete(task))" />
            <button class="title" :class="{ done: task.completed }" @click="modalTask = task">{{ task.title }}</button>
            <span class="badge">{{ task.type }}</span>
            <small v-if="group.name === 'Overdue' || group.name === 'Upcoming'">{{ task.due_date }}</small>
            <button class="btn--ghost btn--danger btn--sm" :aria-label="`Delete ${task.title}`" @click="deleteTask(task)">Delete</button>
          </li>
        </ul>
        <p v-if="!group.items.length && !loading" class="muted">{{ group.empty }}</p>
        <button
          v-if="group.hidden"
          class="btn--ghost btn--sm"
          @click="expanded[group.name] = !expanded[group.name]"
        >{{ expanded[group.name] ? 'See less' : `See more (${group.hidden})` }}</button>
      </template>
    </template>
    </div>

    <TaskModal
      v-if="modalTask !== undefined"
      :task="modalTask ?? undefined"
      :default-date="todayStr"
      @close="modalTask = undefined"
      @saved="upsert"
      @deleted="dropLocal"
    />
  </section>
</template>

<style scoped>
.scoreboard {
  display: flex;
  gap: var(--space-4);
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
}
.score strong {
  color: var(--text-color);
  font-size: var(--text-base);
}
.group {
  margin: var(--space-4) 0 var(--space-1);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-2);
  margin: 0 calc(-1 * var(--space-2));
  border-radius: var(--radius-md);
  transition: background-color var(--transition);
}
.row:hover {
  background: var(--card-color);
}
.title {
  flex: 1;
  min-width: 0;
  min-height: 30px;
  padding: 0;
  text-align: left;
  background: none;
  border: none;
  font-size: var(--text-base);
  font-weight: 400;
  overflow-wrap: anywhere;
}
.row > :not(.title) {
  flex-shrink: 0;
  white-space: nowrap;
}
.title:hover:not(:disabled) {
  background: none;
  color: var(--accent-color);
}
.done {
  text-decoration: line-through;
  color: var(--text-muted);
}
.group--overdue,
.list--overdue,
.list--overdue .title {
  color: var(--overdue-color);
}
ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}
</style>
