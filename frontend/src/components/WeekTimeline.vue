<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useGymWeek } from '../composables/useGymWeek'
import { useTasks } from '../composables/useTasks'
import type { Task } from '../types'
import { dayOfMonth, localToday, weekDates, weekdayShort } from '../utils/dates'
import TaskModal from './TaskModal.vue'

const { tasks, load, upsert, dropLocal } = useTasks()
const gym = useGymWeek()
const loadFailed = ref(false)
const todayStr = localToday()
const modalTask = ref<Task | undefined>(undefined)

const days = computed(() =>
  weekDates(todayStr).map((date) => ({
    date,
    isToday: date === todayStr,
    tasks: tasks.value.filter((t) => t.due_date === date),
    gym: gym.days.value.find((g) => g.date === date),
  })),
)

function state(task: Task, date: string) {
  if (task.completed) return 'done'
  return date < todayStr ? 'overdue' : 'open'
}

onMounted(() => {
  gym.load()
  load().catch(() => (loadFailed.value = true))
})
</script>

<template>
  <section class="week" aria-label="Week timeline">
    <div v-for="day in days" :key="day.date" class="day" :class="{ 'day--today': day.isToday }" :data-date="day.date">
      <header>
        <span class="dow">{{ weekdayShort(day.date) }}</span>
        <span class="dom">{{ dayOfMonth(day.date) }}</span>
        <small v-if="day.tasks.length">{{ day.tasks.length }}</small>
      </header>
      <p v-if="day.gym" class="gym" :class="{ 'gym--done': day.gym.logged }" :title="day.gym.details.join('; ')" data-testid="gym">
        {{ day.gym.logged ? '✓' : '' }} {{ day.gym.lifts.join(' · ') }}
      </p>
      <ul>
        <li v-for="task in day.tasks" :key="task.id">
          <button class="chip" :class="`chip--${state(task, day.date)}`" :title="task.title" @click="modalTask = task">
            <span class="dot" :class="`dot--${task.type.toLowerCase()}`" />
            <span class="chip__title">{{ task.title }}</span>
          </button>
        </li>
      </ul>
      <p v-if="!day.tasks.length && !day.gym" class="empty">—</p>
    </div>
    <p v-if="loadFailed" class="error" role="alert">Could not load the week.</p>

    <TaskModal
      v-if="modalTask"
      :task="modalTask"
      :default-date="todayStr"
      @close="modalTask = undefined"
      @saved="upsert"
      @deleted="dropLocal"
    />
  </section>
</template>

<style scoped>
.week {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
}
.day {
  min-height: 96px;
  padding: var(--space-2) var(--space-3);
  border-left: 1px solid var(--border-color);
}
.day:first-child {
  border-left: none;
  padding-left: 0;
}
.day--today {
  background: var(--accent-soft);
  box-shadow: inset 0 2px 0 var(--accent-color);
}
header {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}
.dow {
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.dom {
  font-weight: 600;
}
.day--today .dow,
.day--today .dom {
  color: var(--accent-color);
}
header small {
  margin-left: auto;
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.gym {
  margin: 0 0 var(--space-1);
  padding: 0 var(--space-1);
  border-left: 2px solid var(--accent-color);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--accent-color);
}
.gym--done {
  color: var(--text-muted);
  border-left-color: var(--text-muted);
}
.empty {
  margin: 0;
  color: var(--border-color);
}
@media (max-width: 700px) {
  .week {
    grid-template-columns: 1fr;
  }
  .day,
  .day:first-child {
    border-left: none;
    border-top: 1px solid var(--border-color);
    padding-left: 0;
  }
}
</style>
