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
      <button class="btn--primary btn--sm" @click="creating = true">New note</button>
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
.row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-2);
  margin: 0 calc(-1 * var(--space-2));
  border-radius: var(--radius-md);
  transition: background-color var(--transition);
}
.row:hover {
  background: var(--card-color);
}
.title {
  flex: 1;
  min-width: 0;
  padding: var(--space-1) 0;
  color: var(--text-color);
  text-decoration: none;
  overflow-wrap: anywhere;
}
.title:hover {
  color: var(--accent-color);
}
.row small,
.row button {
  flex-shrink: 0;
}
ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}
</style>
