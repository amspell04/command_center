<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorMessage, trainingApi } from '../api'
import type { Lift, TrainingMax } from '../types'
import { localToday } from '../utils/dates'
import { LIFT_LABEL, LIFTS, lbToKg } from '../utils/training'

// The maxes a program's percentages are taken from. Saving records today's max and keeps the history.
const emit = defineEmits<{ saved: [] }>()

const maxes = ref<TrainingMax[]>([])
const inputs = ref<Record<Lift, string>>({ SQUAT: '', BENCH: '', DEADLIFT: '' })
const loading = ref(true)
const loadFailed = ref(false)
const error = ref<string | null>(null)
const busy = ref(false)

// Newest max per lift that is already in force
const current = computed(() => {
  const today = localToday()
  const found: Partial<Record<Lift, TrainingMax>> = {}
  for (const m of [...maxes.value].sort((a, b) => b.effective_date.localeCompare(a.effective_date))) {
    if (m.effective_date <= today && !found[m.lift]) found[m.lift] = m
  }
  return found
})

const parsed = (lift: Lift) => {
  const n = Number(inputs.value[lift])
  return inputs.value[lift].trim() !== '' && Number.isFinite(n) && n > 0 && n <= 2000 ? n : null
}
const changed = computed(() => LIFTS.filter((l) => parsed(l) !== null && parsed(l) !== (current.value[l]?.weight_lb ?? null)))
const invalid = computed(() => LIFTS.some((l) => inputs.value[l].trim() !== '' && parsed(l) === null))

function fill() {
  for (const l of LIFTS) inputs.value[l] = current.value[l] ? String(current.value[l]!.weight_lb) : ''
}

async function load() {
  try {
    maxes.value = await trainingApi.maxes()
    fill()
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function save() {
  error.value = null
  busy.value = true
  try {
    for (const lift of changed.value) {
      await trainingApi.setMax({ lift, weight: parsed(lift)!, effective_date: localToday() })
    }
    maxes.value = await trainingApi.maxes()
    fill()
    emit('saved')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="section maxes">
    <h2>Training maxes</h2>
    <p class="muted">Program percentages are taken from these. Saving a new number keeps your history.</p>
    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="loadFailed" class="error" role="alert">Could not load training maxes.</p>
    <form v-else class="maxes__form" @submit.prevent="save">
      <label v-for="lift in LIFTS" :key="lift" class="field">
        {{ LIFT_LABEL[lift] }} (lb)
        <input v-model="inputs[lift]" :aria-label="`${LIFT_LABEL[lift]} max in lb`" inputmode="decimal" placeholder="Not set" />
        <span class="muted" :data-testid="`kg-${lift}`">{{ parsed(lift) ? `${lbToKg(parsed(lift)!)} kg` : '' }}</span>
      </label>
      <p v-if="invalid" class="error" role="alert">Enter a weight between 0 and 2000 lb.</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" class="btn--primary" :disabled="busy || invalid || !changed.length">Save maxes</button>
    </form>
  </section>
</template>

<style scoped>
.maxes__form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3);
}
input {
  width: 8rem;
}
</style>
