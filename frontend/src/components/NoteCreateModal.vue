<script setup lang="ts">
import { ref } from 'vue'
import { errorMessage, notesApi } from '../api'
import type { Note } from '../types'
import BaseModal from './BaseModal.vue'

const emit = defineEmits<{ close: []; created: [note: Note] }>()

const title = ref('')
const error = ref<string | null>(null)
const busy = ref(false)

async function create() {
  const t = title.value.trim()
  if (!t) return
  error.value = null
  busy.value = true
  try {
    emit('created', await notesApi.create({ title: t, content_blocks: [] }))
    emit('close')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <BaseModal title="New note" @close="emit('close')">
    <form class="form" @submit.prevent="create">
      <label>Title <input v-model="title" aria-label="Note title" required maxlength="255" /></label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="busy">Create</button>
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
.error {
  color: #c33;
  margin: 0;
}
</style>
