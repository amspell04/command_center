<script setup lang="ts">
import { ref } from 'vue'
import { errorMessage, tasksApi } from '../api'
import type { NewTask, Task } from '../types'
import BaseModal from './BaseModal.vue'

// Create mode when `task` is omitted, edit/manage mode otherwise.
const props = defineProps<{ task?: Task; defaultDate: string }>()
const emit = defineEmits<{ close: []; saved: [task: Task]; deleted: [id: string] }>()

const form = ref<NewTask>({
  title: props.task?.title ?? '',
  type: props.task?.type ?? 'PERSONAL',
  requirement: props.task?.requirement ?? '',
  due_date: props.task?.due_date ?? props.defaultDate,
})
const error = ref<string | null>(null)
const busy = ref(false)

async function run(fn: () => Promise<void>) {
  error.value = null
  busy.value = true
  try {
    await fn()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

function save() {
  const title = form.value.title.trim()
  if (!title || !form.value.due_date) return
  const body = { ...form.value, title }
  return run(async () => {
    emit('saved', props.task ? await tasksApi.update(props.task.id, body) : await tasksApi.create(body))
    emit('close')
  })
}

function toggleComplete() {
  const t = props.task!
  return run(async () => {
    emit('saved', t.completed ? await tasksApi.update(t.id, { completed: false }) : await tasksApi.complete(t.id))
    emit('close')
  })
}

function remove() {
  const t = props.task!
  return run(async () => {
    await tasksApi.remove(t.id)
    emit('deleted', t.id)
    emit('close')
  })
}
</script>

<template>
  <BaseModal :title="task ? 'Edit task' : 'New task'" @close="emit('close')">
    <form class="form" @submit.prevent="save">
      <label>Title <input v-model="form.title" aria-label="Task title" required maxlength="255" /></label>
      <label>
        Type
        <select v-model="form.type" aria-label="Task type">
          <option value="PERSONAL">Personal</option>
          <option value="WORK">Work</option>
        </select>
      </label>
      <label>Due date <input v-model="form.due_date" type="date" aria-label="Due date" required /></label>
      <label>Requirement <textarea v-model="form.requirement" aria-label="Requirement" rows="3" /></label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="actions">
        <button type="submit" :disabled="busy">{{ task ? 'Save' : 'Create' }}</button>
        <template v-if="task">
          <button type="button" :disabled="busy" @click="toggleComplete">
            {{ task.completed ? 'Mark incomplete' : 'Mark complete' }}
          </button>
          <button type="button" :disabled="busy" @click="remove">Delete</button>
        </template>
      </div>
    </form>
  </BaseModal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-top: 0.75rem;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.85rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
.error {
  color: #c33;
  margin: 0;
}
</style>
