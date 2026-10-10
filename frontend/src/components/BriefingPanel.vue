<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError, errorMessage, newsApi } from '../api'
import type { News } from '../types'

const briefing = ref<News | null>(null)
const loading = ref(false)
const generating = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    // The server allows one briefing per day, so the list holds at most one.
    briefing.value = (await newsApi.today())[0] ?? null
  } catch (e) {
    error.value = errorMessage(e)
  }
  loading.value = false
}

async function generate() {
  generating.value = true
  error.value = null
  try {
    briefing.value = await newsApi.refresh()
  } catch (e) {
    // 400 means today's briefing already exists (e.g. made in another tab): show it.
    if (e instanceof ApiError && e.status === 400) await load()
    else error.value = errorMessage(e)
  }
  generating.value = false
}

function printBriefing() {
  // TODO: print only the briefing (e.g. @media print rules hiding other panels)
  window.print()
}

onMounted(load)
</script>

<template>
  <section class="panel">
    <header class="panel__header">
      <h2>Briefing</h2>
      <div>
        <button :disabled="loading || generating || !!briefing" @click="generate">
          {{ generating ? 'Generating…' : 'Generate briefing' }}
        </button>
        <button :disabled="!briefing" @click="printBriefing">Print</button>
      </div>
    </header>

    <p v-if="loading">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button v-if="!briefing" @click="load">Retry</button></p>
    <p v-else-if="generating">Fetching feeds and summarizing, this can take a minute…</p>
    <p v-else-if="!loading && !briefing">No briefing yet today.</p>

    <article v-if="briefing">
      <h3>{{ briefing.title }}</h3>
      <p class="summary">{{ briefing.summary }}</p>

      <template v-if="briefing.quiz_section.length">
        <h4>Quiz</h4>
        <ol>
          <li v-for="(q, i) in briefing.quiz_section" :key="i">
            <details>
              <summary>{{ q.question }}</summary>
              <p>{{ q.answer }}</p>
            </details>
          </li>
        </ol>
      </template>

      <template v-if="briefing.sources.length">
        <h4>Sources</h4>
        <ul>
          <li v-for="src in briefing.sources" :key="src">{{ src }}</li>
        </ul>
      </template>
    </article>
  </section>
</template>

<style scoped>
.panel {
  border: 1px solid #8884;
  border-radius: 8px;
  padding: 1rem;
}
.panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.quiz__answer {
  font-weight: 600;
}
.sources a,
.sources span {
  overflow-wrap: anywhere;
}
.summary {
  white-space: pre-wrap;
}
.error {
  color: #c33;
}
</style>

<style>
@media print {
  body * {
    visibility: hidden;
  }
  .briefing,
  .briefing * {
    visibility: visible;
  }
  .briefing {
    position: absolute;
    inset: 0 auto auto 0;
    width: 100%;
    border: none;
  }
  .briefing .no-print,
  .briefing .panel__header button {
    display: none;
  }
}
.summary {
  white-space: pre-wrap;
}
.error {
  color: #c33;
}
</style>
