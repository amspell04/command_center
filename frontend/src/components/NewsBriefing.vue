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
    // The server allows one briefing per day, so the list holds at most one.
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

async function generate() {
  generating.value = true
  error.value = null
  try {
    briefing.value = await newsApi.refresh()
    hasToday.value = true
  } catch (e) {
    // 400 means today's briefing already exists (e.g. made in another tab): show it.
    if (e instanceof ApiError && e.status === 400) await load()
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
      <button v-if="!hasToday && !loading" class="btn--primary btn--sm" :disabled="generating" @click="generate">
        {{ generating ? 'Generating…' : 'Generate briefing' }}
      </button>
    </header>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button v-if="!briefing" @click="load">Retry</button></p>
    <p v-else-if="generating" class="muted">Fetching feeds and summarizing, this can take a minute…</p>

    <template v-if="briefing">
      <RouterLink class="headline" :to="`/news/${briefing.id}`">{{ briefing.title }}</RouterLink>
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
  text-decoration: none;
}
.headline:hover {
  text-decoration: underline;
}
</style>
