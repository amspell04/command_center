<script setup lang="ts">
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfirmModal from '../components/ConfirmModal.vue'
import NoteAgentActions from '../components/NoteAgentActions.vue'
import { ApiError, errorMessage, notesApi } from '../api'
import type { Note } from '../types'

const route = useRoute()
const router = useRouter()
const id = String(route.params.id)

const title = ref('')
const content = ref('')
const summary = ref<Pick<Note, 'summary' | 'summary_generated_at' | 'summary_stale'>>({
  summary: null,
  summary_generated_at: null,
  summary_stale: false,
})
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
    const note = await notesApi.get(id)
    title.value = note.title
    content.value = note.content
    setSummary(note)
    editing.value = !note.content.trim()
    saved.value = snapshot()
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound.value = true
    else error.value = errorMessage(e)
  }
  loading.value = false
}

function setSummary(note: Note) {
  summary.value = {
    summary: note.summary,
    summary_generated_at: note.summary_generated_at,
    summary_stale: note.summary_stale,
  }
}

// Only reachable while nothing is unsaved, so replacing the local content loses no edits.
function applyNote(note: Note) {
  content.value = note.content
  setSummary(note)
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
    setSummary(updated)
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
    <div class="page-bar"><button class="nav-link" @click="leave">← Home</button></div>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="notFound" class="muted">Note not found.</p>
    <div v-else class="note__layout">
      <input v-model="title" class="note__title" aria-label="Note title" maxlength="255" placeholder="Untitled" />

      <div class="note__toolbar">
        <button v-if="editing" type="button" @click="editing = false">Done</button>
        <button v-else type="button" @click="editing = true">Edit</button>
        <NoteAgentActions
          :note-id="id"
          :unsaved="dirty"
          :has-summary="!!summary.summary"
          :stale="summary.summary_stale"
          @summarized="applyNote"
        />
        <div class="note__end">
          <button type="button" class="btn--ghost btn--danger" @click="confirmingDelete = true">Delete note</button>
          <button type="button" class="btn--primary" :disabled="!dirty" @click="save">
            {{ dirty ? 'Save' : 'Saved' }}
          </button>
        </div>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <section v-if="summary.summary" class="summary" data-testid="note-summary">
        <h2>Summary <span v-if="summary.summary_stale" class="badge badge--warn">Outdated</span></h2>
        <p>{{ summary.summary }}</p>
        <small v-if="summary.summary_stale" class="muted">
          The note changed since this summary was written.
        </small>
      </section>

      <div class="note__content">
        <textarea v-if="editing" v-model="content" aria-label="Note content" placeholder="Write markdown…" />
        <template v-else>
          <div
            v-if="content.trim()"
            class="markdown"
            data-testid="note-rendered"
            v-html="rendered"
          />
          <p v-else class="muted">This note is empty.</p>
        </template>
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
  max-width: 800px;
  margin: 0 auto;
  padding: var(--space-5) var(--space-6);
}
.note__layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
/* Borderless until hovered or focused so it reads as a document title. */
.note__title {
  padding: var(--space-1) var(--space-2);
  margin: 0 calc(-1 * var(--space-2));
  width: calc(100% + 2 * var(--space-2));
  border-color: transparent;
  background: transparent;
  font-size: var(--text-2xl);
  font-weight: 700;
}
.note__title:hover:not(:focus) {
  border-color: var(--border-color);
}
.note__toolbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  background: var(--bg-color);
  border-bottom: 1px solid var(--border-color);
}
.note__end {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}
.summary {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
  overflow-wrap: anywhere;
}
.summary h2 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-1);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-color);
}
.summary p {
  margin: 0;
}
.note__content textarea {
  width: 100%;
  min-height: 420px;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
}
.markdown {
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.markdown :deep(> :first-child) {
  margin-top: 0;
}
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4) {
  margin: var(--space-5) 0 var(--space-2);
}
.markdown :deep(h1) {
  font-size: var(--text-2xl);
}
.markdown :deep(h2) {
  padding-bottom: var(--space-1);
  border-bottom: 1px solid var(--border-color);
}
.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 0 0 var(--space-3);
  padding-left: var(--space-5);
}
.markdown :deep(li) {
  margin-bottom: var(--space-1);
}
.markdown :deep(blockquote) {
  margin: 0 0 var(--space-3);
  padding: var(--space-1) var(--space-4);
  border-left: 3px solid var(--border-strong);
  color: var(--text-muted);
}
.markdown :deep(code) {
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  background: var(--card-color);
  font-family: var(--font-mono);
  font-size: 0.9em;
}
.markdown :deep(pre) {
  margin: 0 0 var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--card-color);
  overflow-x: auto;
}
.markdown :deep(pre code) {
  padding: 0;
  background: none;
}
.markdown :deep(table) {
  margin-bottom: var(--space-3);
  border-collapse: collapse;
}
.markdown :deep(th),
.markdown :deep(td) {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border-color);
  text-align: left;
}
.markdown :deep(th) {
  background: var(--card-color);
}
.markdown :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: var(--space-4) 0;
}
.markdown :deep(img) {
  max-width: 100%;
}
@media (max-width: 1000px) {
  .note {
    padding: var(--space-4);
  }
}
</style>
