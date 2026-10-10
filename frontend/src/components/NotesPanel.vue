<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { errorMessage, notesApi } from '../api'
import type { Note } from '../types'
import ConfirmModal from './ConfirmModal.vue'
import NoteCreateModal from './NoteCreateModal.vue'

const router = useRouter()
const notes = ref<Note[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const creating = ref(false)
const pendingDelete = ref<Note | null>(null)
const deleteError = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    notes.value = await notesApi.list()
  } catch (e) {
    error.value = errorMessage(e)
  }
  loading.value = false
}

function onCreated(note: Note) {
  notes.value = [note, ...notes.value]
  router.push(`/notes/${note.id}`)
}

async function confirmDelete() {
  const note = pendingDelete.value!
  deleteError.value = null
  try {
    await notesApi.remove(note.id)
    notes.value = notes.value.filter((n) => n.id !== note.id)
    pendingDelete.value = null
  } catch (e) {
    deleteError.value = errorMessage(e)
  }
}

onMounted(load)
</script>

<template>
  <section class="panel">
    <div class="head">
      <h2>Notes</h2>
      <button @click="creating = true">New note</button>
    </div>

    <p v-if="loading">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>
    <p v-else-if="!notes.length && !loading">No notes yet.</p>

    <ul>
      <li v-for="note in notes" :key="note.id" class="row">
        <RouterLink class="title" :to="`/notes/${note.id}`">{{ note.title }}</RouterLink>
        <small>{{ note.date_created }}</small>
        <button :aria-label="`Delete ${note.title}`" @click="deleteError = null; pendingDelete = note">Delete</button>
      </li>
    </ul>

    <NoteCreateModal v-if="creating" @close="creating = false" @created="onCreated" />
    <ConfirmModal
      v-if="pendingDelete"
      title="Delete note?"
      :message="`“${pendingDelete.title}” and all its content will be permanently deleted.`"
      :error="deleteError"
      @close="pendingDelete = null"
      @confirm="confirmDelete"
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
  font-weight: 600;
  color: inherit;
  text-decoration: none;
}
.error {
  color: #c33;
}
ul {
  padding-left: 0;
  list-style: none;
}
</style>
