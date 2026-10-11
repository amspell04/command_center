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

    <template v-if="briefing">
      <RouterLink class="headline" :to="`/news/${briefing.id}`">{{ briefing.title }}</RouterLink>
      <p class="summary" data-testid="briefing-summary">{{ briefing.summary }}</p>
      <ul v-if="briefing.articles.length" class="links" aria-label="Articles covered" data-testid="briefing-links">
        <li v-for="a in briefing.articles" :key="a.url">
          <a v-if="/^https?:\/\//.test(a.url)" :href="a.url" target="_blank" rel="noopener noreferrer">{{ a.title }}</a>
        </li>
      </ul>
      <small v-if="!hasToday" class="muted">From {{ briefing.date_created }}</small>
    </template>
    <p v-else-if="!loading && !error" class="muted">No briefing yet.</p>
  </section>
</template>

<style scoped>
.news {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.headline {
  font-weight: 600;
}
.links {
  margin: 0 0 var(--space-2);
  padding-left: var(--space-4);
  font-size: var(--text-sm);
}
.summary {
  margin: var(--space-2) 0;
  line-height: 1.6;
}
</style>
