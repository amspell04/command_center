<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { errorMessage, studyBuddyApi, weakPointsApi } from '../api'
import type { ChatMessage, StudyMode, WeakPoint } from '../types'

// The agent reads the saved note, so unsaved edits would be ignored.
const props = defineProps<{ noteId: string; unsaved: boolean }>()
const emit = defineEmits<{ close: [] }>()

const OPENERS: Record<StudyMode, string> = {
  quiz: 'Start the quiz.',
  review: 'Help me talk through my weak points.',
}

const mode = ref<StudyMode>('quiz')
const messages = ref<ChatMessage[]>([])
const draft = ref('')
const streaming = ref(false)
const error = ref<string | null>(null)
const weakPoints = ref<WeakPoint[]>([])
const log = ref<HTMLElement | null>(null)
let abort: AbortController | null = null

const open = computed(() => weakPoints.value.filter((w) => !w.resolved))
const resolved = computed(() => weakPoints.value.filter((w) => w.resolved))
const started = computed(() => messages.value.length > 0)
const canReview = computed(() => open.value.length > 0 || (started.value && mode.value === 'review'))

async function loadWeakPoints() {
  try {
    weakPoints.value = await weakPointsApi.forNote(props.noteId)
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function scroll() {
  await nextTick()
  if (log.value) log.value.scrollTop = log.value.scrollHeight
}

// Streams one reply into a new assistant message. A failure drops the reply if nothing arrived.
async function reply() {
  streaming.value = true
  error.value = null
  abort = new AbortController()
  messages.value.push({ role: 'assistant', content: '' })
  const target = messages.value.length - 1
  try {
    const history = messages.value.slice(0, target)
    for await (const event of studyBuddyApi.stream(props.noteId, mode.value, history, abort.signal)) {
      if (event.type === 'token') {
        messages.value[target].content += event.text
        await scroll()
      } else if (event.type === 'weak_point' || event.type === 'weak_point_resolved') {
        await loadWeakPoints()
      } else if (event.type === 'error') {
        error.value = event.message
      }
    }
  } catch (e) {
    if (!(e instanceof DOMException && e.name === 'AbortError')) error.value = errorMessage(e)
  }
  if (!messages.value[target]?.content) messages.value.splice(target, 1)
  streaming.value = false
  abort = null
}

async function start() {
  messages.value = [{ role: 'user', content: OPENERS[mode.value] }]
  await reply()
}

async function send() {
  const text = draft.value.trim()
  if (!text || streaming.value || props.unsaved) return
  draft.value = ''
  messages.value.push({ role: 'user', content: text })
  await scroll()
  await reply()
}

function setMode(next: StudyMode) {
  if (streaming.value || next === mode.value) return
  mode.value = next
  messages.value = []
  error.value = null
}

async function toggle(w: WeakPoint) {
  try {
    const updated = await weakPointsApi.setResolved(w.id, !w.resolved)
    weakPoints.value = weakPoints.value.map((x) => (x.id === updated.id ? updated : x))
  } catch (e) {
    error.value = errorMessage(e)
  }
}

onMounted(loadWeakPoints)
onUnmounted(() => abort?.abort())
</script>

<template>
  <aside class="buddy" aria-label="Study buddy">
    <header class="buddy__head">
      <h2>Study buddy</h2>
      <button type="button" class="btn--ghost btn--icon" aria-label="Close study buddy" @click="emit('close')">×</button>
    </header>

    <div class="buddy__modes" role="group" aria-label="Mode">
      <button type="button" :class="{ 'btn--primary': mode === 'quiz' }" :disabled="streaming" @click="setMode('quiz')">
        Quiz
      </button>
      <button
        type="button"
        :class="{ 'btn--primary': mode === 'review' }"
        :disabled="streaming || !canReview"
        :title="canReview ? '' : 'No open weak points to review'"
        @click="setMode('review')"
      >
        Review weak points
      </button>
    </div>

    <section class="buddy__points" data-testid="weak-points">
      <h3>Weak points</h3>
      <p v-if="!weakPoints.length" class="muted">None yet. Miss a quiz question and it lands here.</p>
      <ul v-else>
        <li v-for="w in [...open, ...resolved]" :key="w.id" :class="{ 'is-resolved': w.resolved }">
          <span>{{ w.topic }}</span>
          <button type="button" class="btn--ghost" @click="toggle(w)">{{ w.resolved ? 'Reopen' : 'Resolve' }}</button>
        </li>
      </ul>
    </section>

    <div ref="log" class="buddy__log" data-testid="chat-log">
      <p v-if="!started" class="muted">
        {{ mode === 'quiz' ? 'The agent quizzes you on this note and records what you miss.' : 'The agent walks through each open weak point with you.' }}
      </p>
      <div v-for="(m, i) in messages" :key="i" class="msg" :class="`msg--${m.role}`">{{ m.content }}</div>
    </div>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <small v-if="unsaved" class="muted">Save your changes first, the agent reads the saved note.</small>

    <button v-if="!started" type="button" class="btn--primary" :disabled="unsaved || streaming" @click="start">
      Start {{ mode === 'quiz' ? 'quiz' : 'review' }}
    </button>
    <form v-else class="buddy__input" @submit.prevent="send">
      <input v-model="draft" aria-label="Your answer" placeholder="Your answer…" maxlength="4000" :disabled="streaming || unsaved" />
      <button class="btn--primary" :disabled="streaming || unsaved || !draft.trim()">Send</button>
    </form>
  </aside>
</template>

<style scoped>
.buddy {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  width: min(420px, 100vw);
  padding: var(--space-4);
  background: var(--surface-color);
  border-left: 1px solid var(--border-color);
  box-shadow: var(--shadow-lg);
}
.buddy__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.buddy__head h2,
.buddy__points h3 {
  margin: 0;
}
.buddy__points h3 {
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.buddy__modes {
  display: flex;
  gap: var(--space-2);
}
.buddy__points ul {
  margin: var(--space-1) 0 0;
  padding: 0;
  list-style: none;
  max-height: 140px;
  overflow-y: auto;
}
.buddy__points li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.buddy__points li.is-resolved span {
  text-decoration: line-through;
  color: var(--text-muted);
}
.buddy__log {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  overflow-y: auto;
}
.msg {
  max-width: 90%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-lg);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.msg--assistant {
  align-self: flex-start;
  background: var(--card-color);
}
.msg--user {
  align-self: flex-end;
  background: var(--accent-soft);
}
.buddy__input {
  display: flex;
  gap: var(--space-2);
}
.buddy__input input {
  flex: 1;
}
</style>
