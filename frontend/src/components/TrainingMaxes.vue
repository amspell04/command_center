<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorMessage, trainingApi } from '../api'
import type { Lift, TrainingMax } from '../types'
import { localToday } from '../utils/dates'
import { LIFT_LABEL, LIFTS, lbToKg } from '../utils/training'
import BaseModal from './BaseModal.vue'

// The maxes a program's percentages are taken from, one block per lift. Saving records today's max and keeps the history.
const emit = defineEmits<{ saved: [] }>()

const maxes = ref<TrainingMax[]>([])
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

const parsed = (raw: string) => {
  const n = Number(raw)
  return raw.trim() !== '' && Number.isFinite(n) && n > 0 && n <= 2000 ? n : null
}

// The lift being edited in the modal, if any
const editing = ref<Lift | null>(null)
const input = ref('')
const value = computed(() => parsed(input.value))
const invalid = computed(() => input.value.trim() !== '' && value.value === null)
const unchanged = computed(() => editing.value !== null && value.value === (current.value[editing.value]?.weight_lb ?? null))

function edit(lift: Lift) {
  editing.value = lift
  input.value = current.value[lift] ? String(current.value[lift]!.weight_lb) : ''
  error.value = null
}

function close() {
  editing.value = null
}

async function load() {
  try {
    maxes.value = await trainingApi.maxes()
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function save() {
  if (editing.value === null || value.value === null || unchanged.value) return
  error.value = null
  busy.value = true
  try {
    await trainingApi.setMax({ lift: editing.value, weight: value.value, effective_date: localToday() })
    maxes.value = await trainingApi.maxes()
    emit('saved')
    close()
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
    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="loadFailed" class="error" role="alert">Could not load training maxes.</p>
    <div v-else class="maxes__blocks">
      <article v-for="lift in LIFTS" :key="lift" class="max-block" :data-testid="`max-${lift}`">
        <h3>{{ LIFT_LABEL[lift] }}</h3>
        <template v-if="current[lift]">
          <p class="max-block__weight">{{ current[lift]!.weight_lb }}<span class="max-block__unit"> lb</span></p>
          <p class="muted">{{ lbToKg(current[lift]!.weight_lb) }} kg · since {{ current[lift]!.effective_date }}</p>
        </template>
        <template v-else>
          <p class="max-block__weight max-block__weight--empty">Not set</p>
          <p class="muted">Program weights stay blank until this is set.</p>
        </template>
        <button type="button" class="btn--sm" :aria-label="`Edit ${LIFT_LABEL[lift]} max`" @click="edit(lift)">Edit</button>
      </article>
    </div>

    <BaseModal v-if="editing" :title="`${LIFT_LABEL[editing]} max`" @close="close">
      <form class="maxes__form" @submit.prevent="save">
        <label class="field">
          Max (lb)
          <input v-model="input" :aria-label="`${LIFT_LABEL[editing]} max in lb`" inputmode="decimal" placeholder="Not set" />
          <span class="muted" data-testid="kg">{{ value ? `${lbToKg(value)} kg` : '' }}</span>
        </label>
        <p class="muted">Saving a new number keeps your history.</p>
        <p v-if="invalid" class="error" role="alert">Enter a weight between 0 and 2000 lb.</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button type="submit" class="btn--primary" :disabled="busy || invalid || value === null || unchanged">Save max</button>
      </form>
    </BaseModal>
  </section>
</template>

<style scoped>
.maxes__blocks {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}
.max-block {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  background: var(--card-color);
}
.max-block h3 {
  margin: 0;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.max-block p {
  margin: 0;
}
.max-block__weight {
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1.1;
}
.max-block__weight--empty {
  font-size: var(--text-xl);
  color: var(--text-muted);
}
.max-block__unit {
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text-muted);
}
.max-block button {
  margin-top: var(--space-3);
}
.maxes__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
@media (max-width: 700px) {
  .maxes__blocks {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
