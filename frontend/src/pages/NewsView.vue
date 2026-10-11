<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, errorMessage, newsApi } from '../api'
import type { News } from '../types'

const route = useRoute()
const router = useRouter()
const id = String(route.params.id)

const briefing = ref<News | null>(null)
const loading = ref(true)
const notFound = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    briefing.value = await newsApi.get(id)
  } catch (e) {
    // A malformed id is a 422 from the server: also "not found" to the user.
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound.value = true
    else error.value = errorMessage(e)
  }
  loading.value = false
}

function printBriefing() {
  window.print()
}

onMounted(load)
</script>

<template>
  <main class="news">
    <button class="back no-print" @click="router.push('/')">← Back</button>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="notFound" class="muted">Briefing not found.</p>
    <p v-else-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>

    <article v-else-if="briefing" class="briefing">
      <header>
        <h1>{{ briefing.title }}</h1>
        <small class="muted">{{ briefing.date_created }}</small>
        <button class="no-print" @click="printBriefing">Print</button>
      </header>
      <p class="summary">{{ briefing.summary }}</p>

      <template v-if="briefing.quiz_section.length">
        <h2>Quiz</h2>
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
        <h2>Sources</h2>
        <ul>
          <li v-for="src in briefing.sources" :key="src">{{ src }}</li>
        </ul>
      </template>
    </article>
  </main>
</template>

<style scoped>
.news {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-5) var(--space-6);
}
.back {
  margin-bottom: var(--space-4);
}
.briefing {
  max-width: 70ch;
}
.briefing header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-3);
}
.briefing h1 {
  flex-basis: 100%;
  font-size: var(--text-2xl);
}
.briefing h2 {
  margin-top: var(--space-5);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.summary {
  white-space: pre-wrap;
  line-height: 1.65;
}
ol,
ul {
  margin: 0;
  padding-left: var(--space-5);
}
li {
  margin-bottom: var(--space-2);
}
summary {
  cursor: pointer;
  font-weight: 500;
}
details p {
  margin: var(--space-2) 0 0;
  color: var(--text-muted);
}
@media (max-width: 1000px) {
  .news {
    padding: var(--space-4);
  }
}
</style>

<style>
@media print {
  .no-print {
    display: none;
  }
}
</style>
