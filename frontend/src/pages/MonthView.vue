<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import TaskModal from '../components/TaskModal.vue'
import { errorMessage, tasksApi } from '../api'
import { useTasks } from '../composables/useTasks'
import type { Task } from '../types'
import { dayOfMonth, localToday, monthGrid, monthLabel, parseISO, shiftMonth, weekdayShort } from '../utils/dates'

const { tasks, load, upsert, dropLocal } = useTasks()
const todayStr = localToday()
const anchor = ref(shiftMonth(todayStr, 0)) // first day of the month on screen
const loadFailed = ref(false)
const moveError = ref<string | null>(null)
const modalTask = ref<Task | undefined>(undefined)
const dragging = ref<Task | null>(null)
const dropTarget = ref<string | null>(null)

const weeks = computed(() => monthGrid(anchor.value))
const headings = computed(() => weeks.value[0]!.map(weekdayShort))
const month = computed(() => parseISO(anchor.value).getMonth())

const tasksByDate = computed(() => {
  const map = new Map<string, Task[]>()
  for (const t of tasks.value) map.set(t.due_date, [...(map.get(t.due_date) ?? []), t])
  return map
})

const state = (task: Task) => (task.completed ? 'done' : task.due_date < todayStr ? 'overdue' : 'open')

function onDragStart(e: DragEvent, task: Task) {
  dragging.value = task
  moveError.value = null
  e.dataTransfer?.setData('text/plain', task.id) // Firefox needs data set to start a drag
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function onDragEnd() {
  dragging.value = null
  dropTarget.value = null
}

async function onDrop(date: string) {
  const task = dragging.value
  onDragEnd()
  if (!task || task.due_date === date) return
  upsert({ ...task, due_date: date }) // optimistic; rolled back below if the server refuses
  try {
    upsert(await tasksApi.update(task.id, { due_date: date }))
  } catch (e) {
    upsert(task)
    moveError.value = `Could not move "${task.title}": ${errorMessage(e)}`
  }
}

onMounted(() => load().catch(() => (loadFailed.value = true)))
</script>

<template>
  <main class="month">
    <header class="page-bar">
      <RouterLink to="/" class="nav-link">← Home</RouterLink>
      <h1>{{ monthLabel(anchor) }}</h1>
      <div class="page-bar__end btn-group">
        <button class="btn--icon" aria-label="Previous month" @click="anchor = shiftMonth(anchor, -1)">‹</button>
        <button @click="anchor = shiftMonth(todayStr, 0)">Today</button>
        <button class="btn--icon" aria-label="Next month" @click="anchor = shiftMonth(anchor, 1)">›</button>
      </div>
    </header>

    <p v-if="loadFailed" class="error" role="alert">Could not load tasks.</p>
    <p v-if="moveError" class="error" role="alert">{{ moveError }}</p>
    <p class="muted month__hint">Drag a task onto another day to reschedule it. Click a task to edit it.</p>

    <div class="grid" role="grid">
      <div class="grid__head" role="row">
        <span v-for="h in headings" :key="h" role="columnheader">{{ h }}</span>
      </div>
      <div v-for="week in weeks" :key="week[0]" class="grid__week" role="row">
        <div
          v-for="date in week"
          :key="date"
          class="cell"
          :class="{
            'cell--today': date === todayStr,
            'cell--outside': parseISO(date).getMonth() !== month,
            'cell--drop': dropTarget === date,
          }"
          :data-date="date"
          role="gridcell"
          @dragover.prevent="dropTarget = date"
          @dragleave="dropTarget === date && (dropTarget = null)"
          @drop.prevent="onDrop(date)"
        >
          <span class="cell__dom">{{ dayOfMonth(date) }}</span>
          <ul>
            <li v-for="task in tasksByDate.get(date) ?? []" :key="task.id">
              <button
                class="chip"
                :class="`chip--${state(task)}`"
                :title="task.title"
                draggable="true"
                @dragstart="onDragStart($event, task)"
                @dragend="onDragEnd"
                @click="modalTask = task"
              >
                <span class="dot" :class="`dot--${task.type.toLowerCase()}`" />
                <span class="chip__title">{{ task.title }}</span>
              </button>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <TaskModal
      v-if="modalTask"
      :task="modalTask"
      :default-date="todayStr"
      @close="modalTask = undefined"
      @saved="upsert"
      @deleted="dropLocal"
    />
  </main>
</template>

<style scoped>
.month {
  max-width: 1680px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-5);
}
.month__hint {
  font-size: var(--text-sm);
}
.grid {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.grid__head,
.grid__week {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
}
.grid__head span {
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--card-color);
}
.cell {
  min-height: 112px;
  padding: var(--space-1) var(--space-2);
  border-top: 1px solid var(--border-color);
  border-left: 1px solid var(--border-color);
}
.cell:first-child {
  border-left: none;
}
.cell--outside {
  background: var(--card-color);
}
.cell--outside .cell__dom {
  color: var(--text-muted);
}
.cell--today {
  background: var(--accent-soft);
  box-shadow: inset 0 2px 0 var(--accent-color);
}
.cell--today .cell__dom {
  color: var(--accent-color);
}
.cell--drop {
  outline: 2px dashed var(--accent-color);
  outline-offset: -2px;
}
.cell__dom {
  font-weight: 600;
  font-size: var(--text-sm);
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.chip {
  cursor: grab;
}
@media (max-width: 700px) {
  .month {
    padding: var(--space-3);
  }
  .cell {
    min-height: 72px;
    padding: var(--space-1);
  }
}
</style>
