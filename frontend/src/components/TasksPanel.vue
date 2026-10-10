<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorMessage, tasksApi } from '../api'
import type { Task } from '../types'
import TaskAgentActions from './TaskAgentActions.vue'
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
const todayTasks = computed(() => open.value.filter((t) => t.due_date <= todayStr))
const upcomingTasks = computed(() => open.value.filter((t) => t.due_date > todayStr))
const doneTasks = computed(() => tasks.value.filter((t) => t.completed))

const groups = computed(() => [
  { name: 'Today', items: todayTasks.value, empty: 'Nothing due today.' },
  { name: 'Upcoming', items: upcomingTasks.value, empty: 'Nothing upcoming.' },
  { name: 'Completed', items: doneTasks.value, empty: '' },
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
    <div class="head">
      <h2>Tasks</h2>
      <button @click="modalTask = null">New task</button>
    </div>

    <TaskAgentActions @updated="onSaved" />

    <p v-if="loading">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>

    <template v-for="group in groups" :key="group.name">
      <template v-if="group.items.length || group.empty">
        <h3>{{ group.name }}</h3>
        <ul>
          <li v-for="task in group.items" :key="task.id" class="row">
            <input type="checkbox" :checked="task.completed" :aria-label="`Complete ${task.title}`" @change="toggleComplete(task)" />
            <button class="title" :class="{ done: task.completed }" @click="modalTask = task">{{ task.title }}</button>
            <span class="badge">{{ task.type }}</span>
            <small v-if="task.due_date < todayStr && !task.completed">overdue ({{ task.due_date }})</small>
            <small v-else-if="group.name === 'Upcoming'">{{ task.due_date }}</small>
            <button :aria-label="`Delete ${task.title}`" @click="deleteTask(task)">Delete</button>
          </li>
        </ul>
        <p v-if="!group.items.length && !loading">{{ group.empty }}</p>
      </template>
    </template>

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
.panel {
  border: 1px solid #8884;
  border-radius: 8px;
  padding: 1rem;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.title {
  flex: 1;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  color: inherit;
}
.done {
  text-decoration: line-through;
  opacity: 0.6;
}
.badge {
  font-size: 0.7rem;
  border: 1px solid #8886;
  border-radius: 4px;
  padding: 0 0.3rem;
}
.error {
  color: #c33;
}
ul {
  padding-left: 0;
  list-style: none;
}
</style>
