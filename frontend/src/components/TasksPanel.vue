<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorMessage, tasksApi } from '../api'
import type { Task } from '../types'
import TaskModal from './TaskModal.vue'

const tasks = ref<Task[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

function localToday() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const todayStr = localToday()

// undefined = closed, null = create, Task = edit
const modalTask = ref<Task | null | undefined>(undefined)

const byDue = (list: Task[]) => [...list].sort((a, b) => a.due_date.localeCompare(b.due_date))
const open = computed(() => tasks.value.filter((t) => !t.completed))
const overdueTasks = computed(() => open.value.filter((t) => t.due_date < todayStr))
const todayTasks = computed(() => open.value.filter((t) => t.due_date === todayStr))
const upcomingTasks = computed(() => open.value.filter((t) => t.due_date > todayStr))
// Tasks have no completion timestamp, so "latest" = most recent due date.
const RECENT_DONE = 3
const showAllDone = ref(false)
const doneTasks = computed(() => [...tasks.value.filter((t) => t.completed)].reverse())
const hiddenDoneCount = computed(() => Math.max(0, doneTasks.value.length - RECENT_DONE))
const visibleDone = computed(() =>
  showAllDone.value ? doneTasks.value : doneTasks.value.slice(0, RECENT_DONE),
)

const completedCount = computed(() => doneTasks.value.length)
const remainingCount = computed(() => open.value.length)

const groups = computed(() => [
  { name: 'Overdue', items: overdueTasks.value, empty: '' },
  { name: 'Today', items: todayTasks.value, empty: 'Nothing due today.' },
  { name: 'Upcoming', items: upcomingTasks.value, empty: 'Nothing upcoming.' },
  { name: 'Completed', items: visibleDone.value, empty: '' },
])

async function run(fn: () => Promise<void>) {
  error.value = null
  try {
    await fn()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function load() {
  loading.value = true
  await run(async () => {
    tasks.value = byDue(await tasksApi.list())
  })
  loading.value = false
}

function onSaved(saved: Task) {
  tasks.value = byDue(tasks.value.some((t) => t.id === saved.id)
    ? tasks.value.map((t) => (t.id === saved.id ? saved : t))
    : [...tasks.value, saved])
}

function onDeleted(id: string) {
  tasks.value = tasks.value.filter((t) => t.id !== id)
}

function toggleComplete(task: Task) {
  return run(async () => {
    onSaved(task.completed ? await tasksApi.update(task.id, { completed: false }) : await tasksApi.complete(task.id))
  })
}

// Tasks delete immediately, no confirmation.
function deleteTask(task: Task) {
  return run(async () => {
    await tasksApi.remove(task.id)
    onDeleted(task.id)
  })
}

onMounted(load)
</script>

<template>
  <section class="panel">
    <div class="panel__header">
      <h2>Tasks</h2>
      <button class="btn--primary" @click="modalTask = null">New task</button>
    </div>

    <div class="panel__body">
    <div class="scoreboard" aria-label="Task scoreboard">
      <div class="score"><strong data-testid="score-done">{{ completedCount }}</strong><span>Completed</span></div>
      <div class="score"><strong data-testid="score-open">{{ remainingCount }}</strong><span>Not completed</span></div>
    </div>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>

    <template v-for="group in groups" :key="group.name">
      <template v-if="group.items.length || group.empty">
        <h3 class="group" :class="{ 'group--overdue': group.name === 'Overdue' }">{{ group.name }}</h3>
        <ul :class="{ 'list--overdue': group.name === 'Overdue' }">
          <li v-for="task in group.items" :key="task.id" class="row">
            <input type="checkbox" :checked="task.completed" :aria-label="`Complete ${task.title}`" @change="toggleComplete(task)" />
            <button class="title" :class="{ done: task.completed }" @click="modalTask = task">{{ task.title }}</button>
            <span class="badge">{{ task.type }}</span>
            <small v-if="group.name === 'Overdue' || group.name === 'Upcoming'">{{ task.due_date }}</small>
            <button class="btn--ghost btn--danger" :aria-label="`Delete ${task.title}`" @click="deleteTask(task)">Delete</button>
          </li>
        </ul>
        <p v-if="!group.items.length && !loading" class="muted">{{ group.empty }}</p>
        <button
          v-if="group.name === 'Completed' && hiddenDoneCount"
          class="btn--ghost"
          @click="showAllDone = !showAllDone"
        >{{ showAllDone ? 'See less' : `See more (${hiddenDoneCount})` }}</button>
      </template>
    </template>
    </div>

    <TaskModal
      v-if="modalTask !== undefined"
      :task="modalTask ?? undefined"
      :default-date="todayStr"
      @close="modalTask = undefined"
      @saved="onSaved"
      @deleted="onDeleted"
    />
  </section>
</template>

<style scoped>
.scoreboard {
  display: flex;
  gap: var(--space-3);
  margin: var(--space-3) 0;
}
.score {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-3);
  background: var(--card-color);
  border-radius: var(--radius-md);
}
.score strong {
  font-size: var(--text-xl, 1.5rem);
}
.score span {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.panel__body {
  min-height: 480px;
  padding: var(--space-4);
}
.group {
  margin: var(--space-5) 0 var(--space-2);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  transition: background-color var(--transition);
}
.row:hover {
  background: var(--card-color);
}
.title {
  flex: 1;
  min-width: 0;
  min-height: 32px;
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
