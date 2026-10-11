<script setup lang="ts">
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfirmModal from '../components/ConfirmModal.vue'
import NoteAgentActions from '../components/NoteAgentActions.vue'
import { errorMessage, notesApi } from '../api'
import type { Note } from '../types'

const route = useRoute()
const router = useRouter()
const id = String(route.params.id)

const title = ref('')
const content = ref('')
const editing = ref(false)
const saved = ref('')
const loading = ref(true)
const notFound = ref(false)
const error = ref<string | null>(null)
const confirmingDelete = ref(false)

const snapshot = () => JSON.stringify([title.value, content.value])
const dirty = computed(() => !loading.value && snapshot() !== saved.value)

async function load() {
  loading.value = true
  error.value = null
  try {
    // The API has no single-note endpoint, so find it in the list.
    const note = (await notesApi.list()).find((n) => n.id === id)
    if (!note) {
      notFound.value = true
    } else {
      title.value = note.title
      content.value = note.content
      editing.value = !note.content.trim()
      saved.value = snapshot()
    }
  } catch (e) {
    error.value = errorMessage(e)
  }
  loading.value = false
}

// Only reachable while nothing is unsaved, so replacing the local content loses no edits.
function applyNote(note: Note) {
  content.value = note.content
  saved.value = snapshot()
}

async function save() {
  const t = title.value.trim()
  if (!t) {
    error.value = 'Title is required'
    return
  }
  error.value = null
  try {
    const updated = await notesApi.update(id, { title: t, content: content.value })
    title.value = updated.title
    content.value = updated.content
    saved.value = snapshot()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function remove() {
  try {
    await notesApi.remove(id)
    router.push('/')
  } catch (e) {
    error.value = errorMessage(e)
    confirmingDelete.value = false
  }
}

// Sanitized because note text can be written by the agent, not just the user.
const rendered = computed(() => DOMPurify.sanitize(marked.parse(content.value, { async: false })))

function leave() {
  if (!dirty.value || confirm('Discard unsaved changes?')) router.push('/')
}

onMounted(load)
</script>

<template>
  <main class="note">
    <button class="back" @click="leave">← Back</button>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="notFound" class="muted">Note not found.</p>
    <div v-else class="note__layout">
      <input v-model="title" class="note__title" aria-label="Note title" maxlength="255" />
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <div class="note__content">
        <template v-if="editing">
          <textarea v-model="content" aria-label="Note content" placeholder="Write markdown…" />
          <button type="button" @click="editing = false">Done</button>
        </template>
        <template v-else>
          <div
            v-if="content.trim()"
            class="markdown"
            data-testid="note-rendered"
            v-html="rendered"
          />
          <p v-else class="muted">This note is empty.</p>
          <button type="button" @click="editing = true">Edit</button>
        </template>
      </div>

      <NoteAgentActions :note-id="id" :unsaved="dirty" @summarized="applyNote" />

      <div class="actions">
        <button type="button" class="btn--primary" :disabled="!dirty" @click="save">
          {{ dirty ? 'Save' : 'Saved' }}
        </button>
        <button type="button" class="btn--danger" @click="confirmingDelete = true">
          Delete note
        </button>
      </div>
    </div>
    <p v-if="error && (loading || notFound)" class="error" role="alert">{{ error }}</p>

    <ConfirmModal
      v-if="confirmingDelete"
      title="Delete note?"
      message="This note and all its content will be permanently deleted."
      @close="confirmingDelete = false"
      @confirm="remove"
    />
  </main>
</template>

<style scoped>
.note {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-5) var(--space-6);
}
.back {
  margin-bottom: var(--space-4);
}
.note__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 335px;
  grid-template-areas:
    'title buttons'
    'error error'
    'content side'
    'actions side';
  column-gap: var(--space-6);
  align-items: start;
}
.note__title {
  grid-area: title;
  width: 100%;
  font-size: var(--text-2xl);
  font-weight: 700;
  margin: 0 0 var(--space-4);
}
.note__layout > .error {
  grid-area: error;
}
.note__content {
  grid-area: content;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
}
.actions {
  grid-area: actions;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.actions .btn--danger {
  margin-left: auto;
}
.note__content textarea {
  width: 100%;
  min-height: 320px;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
}
.markdown {
  width: 100%;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.markdown :deep(pre) {
  overflow-x: auto;
}
@media (max-width: 1000px) {
  .note {
    padding: var(--space-4);
  }
  .note__layout {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: 'title' 'buttons' 'error' 'content' 'actions' 'side';
  }
}
</style>
