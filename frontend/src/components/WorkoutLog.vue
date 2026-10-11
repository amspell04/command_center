<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { errorMessage, trainingApi } from '../api'
import type { Exercise, Lift, WorkoutSession } from '../types'
import { localToday, longDate } from '../utils/dates'
import { LIFT_LABEL, LIFTS, lbToKg } from '../utils/training'
import ConfirmModal from './ConfirmModal.vue'

// Log what you lifted on a day. A day with a program prescription starts filled in with the planned sets and weights;
// a day that is already logged opens for editing. Saving a date again replaces that day's sets.
const emit = defineEmits<{ saved: [session: WorkoutSession]; deleted: [] }>()

interface Row {
  key: number
  lift: Lift
  weight: string // lb, as typed
  reps: string
  program_set_id: string | null
}

let nextKey = 0
const date = ref(localToday())
const rows = ref<Row[]>([])
const notes = ref('')
const bodyweight = ref('')
const existing = ref<WorkoutSession | null>(null)
const planned = ref<Exercise[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const error = ref<string | null>(null)
const saved = ref(false)
const busy = ref(false)
const confirmingDelete = ref(false)
const deleteError = ref<string | null>(null)

const num = (raw: string) => (raw.trim() === '' ? NaN : Number(raw))
const validWeight = (raw: string) => num(raw) > 0 && num(raw) <= 2000
const validReps = (raw: string) => Number.isInteger(num(raw)) && num(raw) >= 1 && num(raw) <= 30
const bodyweightOk = computed(() => bodyweight.value.trim() === '' || (num(bodyweight.value) > 0 && num(bodyweight.value) <= 1000))

const problem = computed(() => {
  if (!date.value) return 'Pick a date'
  if (!rows.value.length) return 'Add at least one set'
  if (!rows.value.every((r) => validWeight(r.weight))) return 'Every set needs a weight above 0 and at most 2000 lb'
  if (!rows.value.every((r) => validReps(r.reps))) return 'Every set needs a whole number of reps from 1 to 30'
  if (!bodyweightOk.value) return 'Bodyweight must be above 0 and at most 1000 lb'
  return null
})

const newRow = (lift: Lift, weight: string, reps: string, program_set_id: string | null = null): Row => ({
  key: nextKey++,
  lift,
  weight,
  reps,
  program_set_id,
})

function fromPlan(plan: Exercise[]): Row[] {
  return plan.flatMap((ex) =>
    Array.from({ length: ex.sets }, () => newRow(ex.lift, ex.weight_lb === null ? '' : String(ex.weight_lb), String(ex.reps), ex.id)),
  )
}

async function load() {
  const day = date.value
  if (!day) return
  loading.value = true
  loadError.value = null
  error.value = null
  saved.value = false
  try {
    const [plan, sessions] = await Promise.all([trainingApi.planned(day), trainingApi.sessionsBetween(day, day)])
    if (day !== date.value) return // the date changed while loading
    planned.value = plan
    existing.value = sessions[0] ?? null
    if (existing.value) {
      rows.value = existing.value.sets.map((s) => newRow(s.lift, String(s.weight_lb), String(s.reps), s.program_set_id))
      notes.value = existing.value.notes
      bodyweight.value = existing.value.bodyweight_lb === null ? '' : String(existing.value.bodyweight_lb)
    } else {
      rows.value = fromPlan(plan)
      notes.value = ''
      bodyweight.value = ''
    }
  } catch (e) {
    if (day === date.value) loadError.value = `Could not load this day: ${errorMessage(e)}`
  } finally {
    if (day === date.value) loading.value = false
  }
}

const addSet = () => {
  const last = rows.value[rows.value.length - 1]
  rows.value.push(newRow(last?.lift ?? 'SQUAT', last?.weight ?? '', last?.reps ?? '5'))
  saved.value = false
}
const removeSet = (key: number) => {
  rows.value = rows.value.filter((r) => r.key !== key)
  saved.value = false
}

async function save() {
  if (problem.value) return
  error.value = null
  saved.value = false
  busy.value = true
  try {
    const session = await trainingApi.saveSession({
      date: date.value,
      notes: notes.value,
      bodyweight: bodyweight.value.trim() === '' ? null : Number(bodyweight.value),
      sets: rows.value.map((r) => ({ lift: r.lift, weight: Number(r.weight), reps: Number(r.reps), program_set_id: r.program_set_id })),
    })
    existing.value = session
    saved.value = true
    emit('saved', session)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

async function removeSession() {
  deleteError.value = null
  busy.value = true
  try {
    await trainingApi.removeSession(existing.value!.id)
    confirmingDelete.value = false
    emit('deleted')
    await load() // back to the plan for that day
  } catch (e) {
    deleteError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

const planLabel = computed(() => (planned.value.length ? `Week ${planned.value[0]!.week} · Day ${planned.value[0]!.day}` : null))
const missingMax = computed(() => planned.value.some((p) => p.weight_lb === null))

watch(date, load)
onMounted(load)
</script>

<template>
  <section class="section log">
    <h2>Log a workout</h2>
    <label class="field log__date">
      Date
      <input v-model="date" type="date" aria-label="Workout date" />
    </label>
    <p v-if="date" class="muted">{{ longDate(date) }}<template v-if="planLabel"> · Planned: {{ planLabel }}</template></p>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="loadError" class="error" role="alert">{{ loadError }}</p>
    <form v-else class="log__form" @submit.prevent="save">
      <p v-if="existing" class="muted">Already logged. Saving replaces this day’s sets.</p>
      <p v-else-if="planLabel" class="muted">Filled in from your program. Change anything that went differently.</p>
      <p v-else class="muted">No program day for this date. Add the sets you did.</p>
      <p v-if="missingMax && !existing" class="muted">Some planned weights are blank because that lift has no training max yet.</p>

      <table class="data-table log__sets">
        <thead>
          <tr>
            <th>Lift</th>
            <th>Weight (lb)</th>
            <th>kg</th>
            <th>Reps</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length">
            <td colspan="5" class="muted">No sets yet.</td>
          </tr>
          <tr v-for="r in rows" :key="r.key" data-testid="set">
            <td>
              <select v-model="r.lift" aria-label="Lift" @change="saved = false">
                <option v-for="l in LIFTS" :key="l" :value="l">{{ LIFT_LABEL[l] }}</option>
              </select>
            </td>
            <td><input v-model="r.weight" aria-label="Weight in lb" inputmode="decimal" @input="saved = false" /></td>
            <td class="muted" data-testid="kg">{{ validWeight(r.weight) ? lbToKg(Number(r.weight)) : '–' }}</td>
            <td><input v-model="r.reps" aria-label="Reps" inputmode="numeric" @input="saved = false" /></td>
            <td><button type="button" class="btn--ghost btn--danger btn--sm" aria-label="Remove set" @click="removeSet(r.key)">Remove</button></td>
          </tr>
        </tbody>
      </table>
      <button type="button" class="btn--sm log__add" @click="addSet">Add set</button>

      <label class="field">
        Bodyweight (lb, optional)
        <input v-model="bodyweight" aria-label="Bodyweight in lb" inputmode="decimal" @input="saved = false" />
      </label>
      <label class="field">
        Notes
        <textarea v-model="notes" aria-label="Workout notes" rows="2" @input="saved = false" />
      </label>

      <p v-if="problem && rows.length" class="error" role="alert">{{ problem }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="saved" class="log__saved" role="status">Saved.</p>
      <div class="log__actions">
        <button type="submit" class="btn--primary" :disabled="busy || !!problem">{{ existing ? 'Update workout' : 'Save workout' }}</button>
        <button v-if="existing" type="button" class="btn--ghost btn--danger" :disabled="busy" @click="confirmingDelete = true">Delete workout</button>
      </div>
    </form>

    <ConfirmModal
      v-if="confirmingDelete"
      title="Delete workout"
      :message="`Delete the workout logged on ${date}?`"
      :error="deleteError"
      @close="confirmingDelete = false"
      @confirm="removeSession"
    />
  </section>
</template>

<style scoped>
.log__date {
  width: fit-content;
  margin: var(--space-2) 0;
}
.log__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  }
.log__sets input {
  width: 100%;
  min-width: 4rem;
}
.log__add {
  width: fit-content;
}
.log__actions {
  display: flex;
  gap: var(--space-2);
}
.log__actions .btn--danger {
  margin-left: auto;
}
.log__saved {
  margin: 0;
  color: var(--accent-color);
}
</style>
