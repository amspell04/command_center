<script setup lang="ts">
import { ref } from 'vue'
import { agentsApi, errorMessage } from '../api'
import type { Note } from '../types'

const props = defineProps<{ noteId: string; unsaved: boolean }>()
const emit = defineEmits<{ summarized: [note: Note] }>()

const busy = ref<'summarize' | null>(null)
const error = ref<string | null>(null)

// The agent reads the saved note, so unsaved edits would be ignored (or overwritten by a summary).
async function summarize() {
  busy.value = 'summarize'
  error.value = null
  try {
    emit('summarized', await agentsApi.summarizeNote(props.noteId))
  } catch (e) {
    error.value = errorMessage(e)
  }
  busy.value = null
}
</script>

<template>
  <div class="agent">
    <div class="agent__buttons">
      <button class="btn--primary" :disabled="busy !== null || unsaved" @click="summarize">
        {{ busy === 'summarize' ? 'Summarizing…' : 'Summarize' }}
      </button>
      <small v-if="unsaved">Save your changes first, the agent reads the saved note.</small>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
/* Children join the page grid: buttons sit in the header. */
.agent {
  display: contents;
}
.agent__buttons {
  grid-area: buttons;
  display: flex;
  gap: var(--space-2);
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
}
</style>
