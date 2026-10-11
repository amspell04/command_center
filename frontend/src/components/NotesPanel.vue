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
    <div class="panel__header">
      <h2>Notes</h2>
      <button class="btn--primary" @click="creating = true">New note</button>
    </div>

    <div class="panel__body">
    <p v-if="loading" class="muted">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>
    <p v-else-if="!notes.length && !loading" class="muted">No notes yet.</p>

    <ul>
      <li v-for="note in notes" :key="note.id" class="row">
        <RouterLink class="title" :to="`/notes/${note.id}`">{{ note.title }}</RouterLink>
        <small>{{ note.date_created }}</small>
        <button class="btn--ghost btn--danger btn--sm" :aria-label="`Delete ${note.title}`" @click="deleteError = null; pendingDelete = note">Delete</button>
      </li>
    </ul>
    </div>

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
.panel__body {
  min-height: 160px;
}
.row {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 120px;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--card-color);
  transition:
    border-color var(--transition),
    box-shadow var(--transition);
}
.row:hover {
  border-color: #cfc7de;
  box-shadow: var(--shadow-sm);
}
.title {
  font-weight: 600;
  color: var(--text-color);
  text-decoration: none;
  overflow-wrap: anywhere;
}
.title:hover {
  color: var(--accent-color);
}
.row button {
  align-self: flex-end;
}
ul {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: var(--space-4);
  margin: 0;
  padding-left: 0;
  list-style: none;
}
</style>
