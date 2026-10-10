<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfirmModal from '../components/ConfirmModal.vue'
import NoteAgentActions from '../components/NoteAgentActions.vue'
import { errorMessage, notesApi } from '../api'
import type { Note, NoteBlock } from '../types'

const route = useRoute()
const router = useRouter()
const id = String(route.params.id)

const title = ref('')
const blocks = ref<NoteBlock[]>([])
const saved = ref('')
const loading = ref(true)
const notFound = ref(false)
const error = ref<string | null>(null)
const confirmingDelete = ref(false)

const snapshot = () => JSON.stringify([title.value, blocks.value])
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
      blocks.value = note.content_blocks.map((b) => ({ ...b }))
      if (!blocks.value.length) blocks.value.push({ content: '' })
      saved.value = snapshot()
    }
  } catch (e) {
    error.value = errorMessage(e)
  }
  loading.value = false
}

// Only reachable while nothing is unsaved, so replacing the local blocks loses no edits.
function applyNote(note: Note) {
  blocks.value = note.content_blocks.map((b) => ({ ...b }))
  if (!blocks.value.length) blocks.value.push({ content: '' })
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
    const updated = await notesApi.update(id, {
      title: t,
      content_blocks: blocks.value.filter((b) => b.content.trim()),
    })
    title.value = updated.title
    blocks.value = updated.content_blocks.map((b) => ({ ...b }))
    if (!blocks.value.length) blocks.value.push({ content: '' })
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

function removeBlock(i: number) {
  blocks.value.splice(i, 1)
  if (!blocks.value.length) blocks.value.push({ content: '' })
}

function leave() {
  if (!dirty.value || confirm('Discard unsaved changes?')) router.push('/')
}

onMounted(load)
</script>

<template>
  <main class="note">
    <button @click="leave">← Back</button>

    <p v-if="loading">Loading…</p>
    <p v-else-if="notFound">Note not found.</p>
    <template v-else>
      <input v-model="title" class="note__title" aria-label="Note title" maxlength="255" />
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <div v-for="(block, i) in blocks" :key="i" class="block">
        <textarea v-model="block.content" aria-label="Note content" rows="4" placeholder="Write markdown…" />
        <button type="button" aria-label="Remove block" @click="removeBlock(i)">×</button>
      </div>

      <NoteAgentActions :note-id="id" :unsaved="dirty" @summarized="applyNote" />

      <div class="actions">
        <button type="button" @click="blocks.push({ content: '' })">+ Add block</button>
        <button type="button" :disabled="!dirty" @click="save">{{ dirty ? 'Save' : 'Saved' }}</button>
        <button type="button" @click="confirmingDelete = true">Delete note</button>
      </div>
    </template>
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
  max-width: 760px;
  margin: 0 auto;
  padding: 1rem 1.5rem;
}
.note__title {
  display: block;
  width: 100%;
  font-size: 1.6rem;
  font-weight: 700;
  border: none;
  border-bottom: 1px solid #8884;
  background: none;
  color: inherit;
  margin: 1rem 0;
}
.block {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.6rem;
}
.block textarea {
  flex: 1;
  font-family: ui-monospace, monospace;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
.error {
  color: #c33;
}
</style>
