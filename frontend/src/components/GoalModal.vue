<script setup lang="ts">
import { ref } from 'vue'
import { errorMessage, goalsApi } from '../api'
import type { Goal, NewGoal } from '../types'
import BaseModal from './BaseModal.vue'

// Create mode when `goal` is omitted, edit mode otherwise.
const props = defineProps<{ goal?: Goal }>()
const emit = defineEmits<{ close: []; saved: [goal: Goal]; deleted: [id: string] }>()

const form = ref({ title: props.goal?.title ?? '', details: props.goal?.details ?? '', target_date: props.goal?.target_date ?? '' })
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
  if (!title) return
  // An emptied date clears the deadline; a new goal without one just omits it
  const target_date = form.value.target_date || null
  const body: NewGoal = { title, details: form.value.details, ...(props.goal || target_date ? { target_date } : {}) }
  return run(async () => {
    emit('saved', props.goal ? await goalsApi.update(props.goal.id, body) : await goalsApi.create(body))
    emit('close')
  })
}

function remove() {
  const g = props.goal!
  return run(async () => {
    await goalsApi.remove(g.id)
    emit('deleted', g.id)
    emit('close')
  })
}
</script>

<template>
  <BaseModal :title="goal ? 'Edit goal' : 'New goal'" @close="emit('close')">
    <form class="form" @submit.prevent="save">
      <label>Goal <input v-model="form.title" aria-label="Goal title" required maxlength="255" placeholder="e.g. Finish 5 work tasks a week" /></label>
      <label>
        Details
        <textarea v-model="form.details" aria-label="Goal details" rows="3" placeholder="What does hitting it look like?" />
      </label>
      <label>
        Target date (optional)
        <input v-model="form.target_date" type="date" aria-label="Goal target date" />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="actions">
        <button type="submit" class="btn--primary" :disabled="busy">{{ goal ? 'Save' : 'Create' }}</button>
        <button v-if="goal" type="button" class="btn--danger" :disabled="busy" @click="remove">Delete</button>
      </div>
    </form>
  </BaseModal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
label {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
}
.actions {
  display: flex;
  gap: var(--space-2);
}
.actions .btn--danger {
  margin-left: auto;
}
</style>
