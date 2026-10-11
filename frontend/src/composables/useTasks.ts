import { ref } from 'vue'
import { tasksApi } from '../api'
import type { Task } from '../types'

// One task list shared by every panel on the page, so a change in one shows up in all of them.
const tasks = ref<Task[]>([])
const loading = ref(false)
let inflight: Promise<void> | null = null

const byDue = (list: Task[]) => [...list].sort((a, b) => a.due_date.localeCompare(b.due_date))

/** Fetch the list. Panels all call this on mount; concurrent calls share one request. Rejects on failure. */
function load(): Promise<void> {
  if (!inflight) {
    loading.value = true
    inflight = tasksApi
      .list()
      .then((list) => {
        tasks.value = byDue(list)
      })
      .finally(() => {
        loading.value = false
        inflight = null
      })
  }
  return inflight
}

function upsert(saved: Task) {
  tasks.value = byDue(
    tasks.value.some((t) => t.id === saved.id) ? tasks.value.map((t) => (t.id === saved.id ? saved : t)) : [...tasks.value, saved],
  )
}

function dropLocal(id: string) {
  tasks.value = tasks.value.filter((t) => t.id !== id)
}

async function toggleComplete(task: Task) {
  upsert(task.completed ? await tasksApi.update(task.id, { completed: false }) : await tasksApi.complete(task.id))
}

async function remove(task: Task) {
  await tasksApi.remove(task.id)
  dropLocal(task.id)
}

export function useTasks() {
  return { tasks, loading, load, upsert, dropLocal, toggleComplete, remove }
}
