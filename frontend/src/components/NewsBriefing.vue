<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError, errorMessage, newsApi } from '../api'
import type { News } from '../types'

// The latest briefing, which may be from an earlier day when none exists yet today.
const briefing = ref<News | null>(null)
const hasToday = ref(false)
const loading = ref(false)
const generating = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    // The server keeps one briefing per day (regenerating replaces it), so the list holds at most one.
    const todays = (await newsApi.today())[0]
    hasToday.value = !!todays
    if (todays) {
      briefing.value = todays
    } else {
      try {
        briefing.value = await newsApi.latest()
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 404)) throw e
        briefing.value = null
      }
    }
  } catch (e) {
    error.value = errorMessage(e)
  }
  loading.value = false
}

async function generate(replace = false) {
  generating.value = true
  error.value = null
  try {
    briefing.value = await newsApi.refresh(replace)
    hasToday.value = true
  } catch (e) {
    // 409 means today's briefing already exists (e.g. made in another tab): show it.
    if (e instanceof ApiError && e.status === 409) await load()
    else error.value = errorMessage(e)
  }
  generating.value = false
}

onMounted(load)
</script>

<template>
  <section class="panel news" aria-label="News briefing">
    <header class="panel__header">
      <h2>News briefing</h2>
      <button v-if="!hasToday && !loading" class="btn--primary btn--sm" :disabled="generating" @click="generate()">
        {{ generating ? 'Generating…' : 'Generate briefing' }}
      </button>
      <button v-else-if="!loading" class="btn--sm" :disabled="generating" @click="generate(true)">
        {{ generating ? 'Generating…' : 'Regenerate' }}
      </button>
    </header>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button v-if="!briefing" @click="load">Retry</button></p>
    <p v-else-if="generating" class="muted">Fetching feeds and summarizing, this can take a minute…</p>

    <article v-if="briefing" class="briefing">
      <small v-if="!hasToday" class="muted">From {{ briefing.date_created }}</small>
      <h3 class="headline">{{ briefing.title }}</h3>
      <p class="summary" data-testid="briefing-summary">{{ briefing.summary }}</p>
      <div class="briefing__cols">
        <p class="body" data-testid="briefing-body">{{ briefing.body }}</p>
        <div class="side">
          <section v-if="briefing.quiz_section.length" class="quiz" data-testid="briefing-quiz">
            <h4>Quiz</h4>
            <ol>
              <li v-for="(q, i) in briefing.quiz_section" :key="i">
                <details>
                  <summary>{{ q.question }}</summary>
                  <p>{{ q.answer }}</p>
                </details>
              </li>
            </ol>
          </section>
          <section v-if="briefing.articles.length" class="sources" data-testid="briefing-links">
            <h4>Sources</h4>
            <ul>
              <li v-for="a in briefing.articles" :key="a.url">
                <a v-if="/^https?:\/\//.test(a.url)" :href="a.url" target="_blank" rel="noopener noreferrer">{{ a.title }}</a>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </article>
    <p v-else-if="!loading && !error" class="muted">No briefing yet.</p>
  </section>
</template>

<style scoped>
.news {
  display: flex;
  flex-direction: column;
}
.headline {
  margin: 0;
  font-size: var(--text-xl);
}
.summary {
  margin: var(--space-2) 0 var(--space-3);
  font-weight: 500;
  line-height: 1.6;
}
.briefing__cols {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: var(--space-5);
  align-items: start;
}
.body {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.7;
}
h4 {
  margin: 0 0 var(--space-2);
}
.quiz ol,
.sources ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.quiz ol {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.quiz li {
  border-radius: var(--radius-lg);
  background: var(--card-color);
}
.quiz summary {
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  font-weight: 500;
}
.quiz details p {
  margin: 0;
  padding: 0 var(--space-3) var(--space-2);
  color: var(--text-muted);
}
.side {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.sources li {
  padding: var(--space-1) 0;
  border-top: 1px solid var(--border-color);
  font-size: var(--text-sm);
  overflow-wrap: anywhere;
}
@media (max-width: 700px) {
  .briefing__cols {
    grid-template-columns: 1fr;
  }
}
</style>
