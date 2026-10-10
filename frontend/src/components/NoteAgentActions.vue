<script setup lang="ts">
import { ref } from 'vue'
import { agentsApi, errorMessage } from '../api'
import type { Note, NoteCritique } from '../types'

const props = defineProps<{ noteId: string; unsaved: boolean }>()
const emit = defineEmits<{ summarized: [note: Note] }>()

const critique = ref<NoteCritique | null>(null)
const busy = ref<'summarize' | 'critique' | null>(null)
const error = ref<string | null>(null)

// The agents read the saved note, so unsaved edits would be ignored (or overwritten by a summary).
async function run(kind: 'summarize' | 'critique') {
  busy.value = kind
  error.value = null
  try {
    if (kind === 'summarize') emit('summarized', await agentsApi.summarizeNote(props.noteId))
    else critique.value = await agentsApi.critiqueNote(props.noteId)
  } catch (e) {
    error.value = errorMessage(e)
  }
  busy.value = null
}

const empty = (c: NoteCritique) => !c.gaps.length && !c.unclear_claims.length && !c.questions.length
</script>

<template>
  <div class="agent">
    <div class="agent__buttons">
      <button :disabled="busy !== null || unsaved" @click="run('summarize')">
        {{ busy === 'summarize' ? 'Summarizing…' : 'Summarize' }}
      </button>
      <button :disabled="busy !== null || unsaved" @click="run('critique')">
        {{ busy === 'critique' ? 'Critiquing…' : 'Critique' }}
      </button>
      <small v-if="unsaved">Save your changes first, the agent reads the saved note.</small>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section v-if="critique" aria-label="Critique">
      <h3>Critique</h3>
      <p v-if="empty(critique)">Nothing to flag.</p>
      <template v-else>
        <template v-for="[label, points] in [['Gaps', critique.gaps], ['Unclear claims', critique.unclear_claims]] as const" :key="label">
          <template v-if="points.length">
            <h4>{{ label }}</h4>
            <ul>
              <li v-for="(p, i) in points" :key="i">
                {{ p.point }}<blockquote>{{ p.quote }}</blockquote>
              </li>
            </ul>
          </template>
        </template>
        <template v-if="critique.questions.length">
          <h4>Questions to answer</h4>
          <ul>
            <li v-for="(q, i) in critique.questions" :key="i">{{ q }}</li>
          </ul>
        </template>
      </template>
      <button @click="critique = null">Dismiss</button>
    </section>
  </div>
</template>

<style scoped>
.agent__buttons {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin: 0.5rem 0;
}
blockquote {
  margin: 0.2rem 0 0.6rem 0.5rem;
  padding-left: 0.6rem;
  border-left: 3px solid #8886;
  opacity: 0.8;
}
.error {
  color: #c33;
}
</style>
