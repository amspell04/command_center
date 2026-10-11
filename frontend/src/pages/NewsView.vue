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
    <div class="page-bar no-print"><button class="nav-link" @click="router.push('/')">← Home</button></div>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="notFound" class="muted">Briefing not found.</p>
    <p v-else-if="error" class="error" role="alert">{{ error }} <button @click="load">Retry</button></p>

    <article v-else-if="briefing" class="briefing">
      <header class="briefing__head">
        <div>
          <small class="briefing__date">{{ briefing.date_created }}</small>
          <h1>{{ briefing.title }}</h1>
        </div>
        <button class="btn--sm no-print" @click="printBriefing">Print</button>
      </header>
      <p class="briefing__summary" data-testid="briefing-summary">{{ briefing.summary }}</p>
      <p class="briefing__body" data-testid="briefing-body">{{ briefing.body }}</p>

      <section v-if="briefing.quiz_section.length" class="section">
        <h2>Quiz</h2>
        <ol class="quiz">
          <li v-for="(q, i) in briefing.quiz_section" :key="i">
            <details>
              <summary>{{ q.question }}</summary>
              <p>{{ q.answer }}</p>
            </details>
          </li>
        </ol>
      </section>

      <section v-if="briefing.sources.length" class="section">
        <h2>Sources</h2>
        <ul class="sources">
          <li v-for="src in briefing.sources" :key="src">
            <a v-if="/^https?:\/\//.test(src)" :href="src" target="_blank" rel="noopener noreferrer">{{ src }}</a>
            <template v-else>{{ src }}</template>
          </li>
        </ul>
      </section>
    </article>
  </main>
</template>

<style scoped>
.news {
  max-width: 760px;
  margin: 0 auto;
  padding: var(--space-5) var(--space-6);
}
.briefing__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.briefing__date {
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.briefing h1 {
  margin: var(--space-1) 0 0;
  font-size: var(--text-2xl);
}
.briefing__summary {
  margin-bottom: var(--space-4);
  font-size: var(--text-lg);
  font-weight: 500;
  line-height: 1.6;
}
.briefing__body {
  margin-bottom: var(--space-5);
  white-space: pre-wrap;
  line-height: 1.7;
}
.section {
  margin-top: var(--space-5);
}
.quiz,
.sources {
  margin: 0;
  padding: 0;
  list-style: none;
}
.quiz {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  counter-reset: q;
}
.quiz li {
  counter-increment: q;
  border-radius: var(--radius-lg);
  background: var(--card-color);
}
.quiz summary {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  font-weight: 500;
  list-style: none;
}
.quiz summary::-webkit-details-marker {
  display: none;
}
.quiz summary::before {
  content: counter(q);
  flex-shrink: 0;
  color: var(--accent-color);
  font-weight: 700;
}
.quiz summary::after {
  content: '+';
  margin-left: auto;
  color: var(--text-muted);
}
.quiz details[open] summary::after {
  content: '−';
}
.quiz details p {
  margin: 0;
  padding: 0 var(--space-4) var(--space-3) calc(var(--space-4) + var(--space-3) + 1ch);
  color: var(--text-muted);
}
.sources li {
  padding: var(--space-1) 0;
  border-top: 1px solid var(--border-color);
  font-size: var(--text-sm);
  overflow-wrap: anywhere;
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
