<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { errorMessage, trainingApi } from '../api'
import type { Exercise, Lift, NewExercise, Program } from '../types'
import { addDays, localToday, weekdayShort } from '../utils/dates'
import { LIFT_LABEL, LIFTS, sortExercises, weightLabel } from '../utils/training'
import ConfirmModal from './ConfirmModal.vue'

// Spreadsheet-style editor for a percentage-based program: one table per week, every cell saves when it loses focus.
// `refreshKey` changes when the training maxes change, so the computed weights are fetched again.
const props = defineProps<{ refreshKey?: number }>()

const DAYS = [1, 2, 3, 4, 5, 6, 7]

const programs = ref<Program[]>([])
const programId = ref<string | null>(null)
const exercises = ref<Exercise[]>([])
const week = ref(1)
const loading = ref(true)
const loadFailed = ref(false)
const error = ref<string | null>(null)
const rowErrors = ref<Record<string, string>>({})
const version = ref(0) // bumped to redraw rows whose typed value was refused
const creating = ref(false)
const newProgram = ref({ name: '', start_date: localToday(), weeks: 10, active: true })
const confirmingDelete = ref(false)
const deleteError = ref<string | null>(null)
const draft = ref<NewExercise>({ week: 1, day: 1, lift: 'SQUAT', sets: 3, reps: 5, percent: 70 })
const draftError = ref<string | null>(null)
const copyTarget = ref<number | null>(null)
const copyError = ref<string | null>(null)
const busy = ref(false)

const program = computed(() => programs.value.find((p) => p.id === programId.value))
const weekRows = computed(() => sortExercises(exercises.value.filter((e) => e.week === week.value)))
const weekCounts = computed(() => {
  const counts = new Map<number, number>()
  for (const e of exercises.value) counts.set(e.week, (counts.get(e.week) ?? 0) + 1)
  return counts
})
const copyTargets = computed(() =>
  Array.from({ length: program.value?.weeks ?? 0 }, (_, i) => i + 1).filter((w) => w !== week.value && !weekCounts.value.has(w)),
)

const dayLabel = (day: number) =>
  program.value ? `Day ${day} · ${weekdayShort(addDays(program.value.start_date, (week.value - 1) * 7 + day - 1))}` : `Day ${day}`

const value = (e: Event) => (e.target as HTMLInputElement | HTMLSelectElement).value

const INT_RANGE: Record<string, [number, number]> = { day: [1, 7], sets: [1, 20], reps: [1, 30] }

/** A clean value for one exercise field, or an explanation of what is wrong with it. */
function check(field: keyof NewExercise, raw: string | number): { ok: true; value: number | Lift } | { ok: false; why: string } {
  if (field === 'lift') {
    return LIFTS.includes(raw as Lift) ? { ok: true, value: raw as Lift } : { ok: false, why: 'Pick a lift' }
  }
  const n = typeof raw === 'number' ? raw : raw.trim() === '' ? NaN : Number(raw)
  if (field === 'percent') {
    return n > 0 && n <= 150 ? { ok: true, value: Math.round(n * 10) / 10 } : { ok: false, why: 'Percent must be above 0 and at most 150' }
  }
  const [lo, hi] = INT_RANGE[field]!
  return Number.isInteger(n) && n >= lo && n <= hi ? { ok: true, value: n } : { ok: false, why: `${field} must be a whole number from ${lo} to ${hi}` }
}

async function load() {
  try {
    programs.value = await trainingApi.programs()
    programId.value = (programs.value.find((p) => p.active) ?? programs.value[0])?.id ?? null
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function loadExercises() {
  rowErrors.value = {}
  if (!programId.value) {
    exercises.value = []
    return
  }
  const id = programId.value
  try {
    const rows = await trainingApi.exercises(id)
    if (id === programId.value) exercises.value = rows
  } catch (e) {
    error.value = `Could not load the program: ${errorMessage(e)}`
  }
}

async function run(fn: () => Promise<void>, onError: (m: string) => void = (m) => (error.value = m)) {
  busy.value = true
  try {
    await fn()
  } catch (e) {
    onError(errorMessage(e))
  } finally {
    busy.value = false
  }
}

const replaceProgram = (p: Program) => (programs.value = programs.value.map((x) => (x.id === p.id ? p : x)))

async function editProgram(changes: Partial<Omit<Program, 'id'>>) {
  const p = program.value!
  error.value = null
  await run(
    async () => {
      replaceProgram(await trainingApi.updateProgram(p.id, changes))
      if (changes.active) programs.value = await trainingApi.programs() // the previous active one was switched off
      if (changes.weeks !== undefined) week.value = Math.min(week.value, changes.weeks)
      if (changes.start_date) await loadExercises()
    },
    (m) => {
      error.value = m
      version.value++
    },
  )
}

const editWeeks = (raw: string) => {
  const n = Number(raw)
  if (!Number.isInteger(n) || n < 1 || n > 52) {
    error.value = 'Weeks must be a whole number from 1 to 52'
    version.value++
  } else if (n !== program.value!.weeks) editProgram({ weeks: n })
}

const editName = (raw: string) => {
  const name = raw.trim()
  if (!name) {
    error.value = 'The program needs a name'
    version.value++
  } else if (name !== program.value!.name) editProgram({ name })
}

const editStart = (raw: string) => {
  if (!raw) {
    error.value = 'Pick a start date'
    version.value++
  } else if (raw !== program.value!.start_date) editProgram({ start_date: raw })
}

async function createProgram() {
  const form = newProgram.value
  const name = form.name.trim()
  if (!name || !form.start_date) return
  error.value = null
  await run(async () => {
    const created = await trainingApi.createProgram({ ...form, name })
    programs.value = await trainingApi.programs()
    programId.value = created.id
    creating.value = false
    newProgram.value = { name: '', start_date: localToday(), weeks: 10, active: true }
  })
}

async function removeProgram() {
  const p = program.value!
  deleteError.value = null
  await run(
    async () => {
      await trainingApi.removeProgram(p.id)
      programs.value = programs.value.filter((x) => x.id !== p.id)
      programId.value = (programs.value.find((x) => x.active) ?? programs.value[0])?.id ?? null
      confirmingDelete.value = false
    },
    (m) => (deleteError.value = m),
  )
}

async function editExercise(ex: Exercise, field: keyof NewExercise, raw: string) {
  const checked = check(field, raw)
  if (!checked.ok) {
    rowErrors.value = { ...rowErrors.value, [ex.id]: checked.why }
    version.value++
    return
  }
  if (checked.value === ex[field]) return
  const { [ex.id]: _cleared, ...rest } = rowErrors.value
  rowErrors.value = rest
  await run(
    async () => {
      const saved = await trainingApi.updateExercise(ex.id, { [field]: checked.value })
      exercises.value = exercises.value.map((e) => (e.id === saved.id ? saved : e))
    },
    (m) => {
      rowErrors.value = { ...rowErrors.value, [ex.id]: m }
      version.value++
    },
  )
}

async function addExercise() {
  const d = draft.value
  for (const field of ['day', 'sets', 'reps', 'percent'] as const) {
    const checked = check(field, d[field])
    if (!checked.ok) return (draftError.value = checked.why)
  }
  draftError.value = null
  await run(
    async () => {
      const added = await trainingApi.addExercise(programId.value!, { ...d, week: week.value })
      exercises.value = [...exercises.value, added]
    },
    (m) => (draftError.value = m),
  )
}

async function removeExercise(ex: Exercise) {
  error.value = null
  await run(async () => {
    await trainingApi.removeExercise(ex.id)
    exercises.value = exercises.value.filter((e) => e.id !== ex.id)
  })
}

async function copyWeek() {
  const to = copyTarget.value
  if (to === null) return
  copyError.value = null
  await run(
    async () => {
      const copied = await trainingApi.copyWeek(programId.value!, week.value, to)
      exercises.value = [...exercises.value, ...copied]
      week.value = to
      copyTarget.value = null
    },
    (m) => (copyError.value = m),
  )
}

watch(programId, () => {
  week.value = 1
  copyTarget.value = null
  loadExercises()
})
watch(() => props.refreshKey, loadExercises)
watch(week, () => {
  copyTarget.value = null
  copyError.value = null
  draftError.value = null
})

onMounted(load)
</script>

<template>
  <section class="section editor">
    <h2>Program</h2>
    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="loadFailed" class="error" role="alert">Could not load programs.</p>
    <template v-else>
      <div class="editor__bar">
        <label v-if="programs.length" class="field">
          Program
          <select aria-label="Program" :value="programId" @change="programId = value($event)">
            <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }}{{ p.active ? ' (active)' : '' }}</option>
          </select>
        </label>
        <button type="button" @click="creating = !creating">{{ creating ? 'Cancel' : 'New program' }}</button>
      </div>

      <form v-if="creating" class="editor__new" @submit.prevent="createProgram">
        <label class="field">Name <input v-model="newProgram.name" aria-label="New program name" required maxlength="255" placeholder="e.g. Meet prep" /></label>
        <label class="field">Week 1 starts <input v-model="newProgram.start_date" type="date" aria-label="New program start date" required /></label>
        <label class="field">Weeks <input v-model.number="newProgram.weeks" type="number" min="1" max="52" aria-label="New program weeks" required /></label>
        <label class="field check"><input v-model="newProgram.active" type="checkbox" /> Make active</label>
        <button type="submit" class="btn--primary" :disabled="busy">Create program</button>
      </form>

      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <p v-if="!program && !creating" class="muted">No program yet. Create one to start planning your weeks.</p>

      <template v-if="program">
        <div :key="`settings-${program.id}-${version}`" class="editor__settings">
          <label class="field">Name <input :value="program.name" aria-label="Program name" maxlength="255" @change="editName(value($event))" /></label>
          <label class="field">Week 1 starts <input :value="program.start_date" type="date" aria-label="Start date" @change="editStart(value($event))" /></label>
          <label class="field">Weeks <input :value="program.weeks" type="number" min="1" max="52" aria-label="Weeks" @change="editWeeks(value($event))" /></label>
          <button v-if="!program.active" type="button" :disabled="busy" @click="editProgram({ active: true })">Make active</button>
          <span v-else class="muted">Active program</span>
          <button type="button" class="btn--ghost btn--danger btn--sm editor__delete" @click="confirmingDelete = true">Delete program</button>
        </div>

        <nav class="editor__weeks" aria-label="Weeks">
          <button
            v-for="w in program.weeks"
            :key="w"
            type="button"
            class="week"
            :class="{ 'week--on': w === week, 'week--empty': !weekCounts.has(w) }"
            :aria-label="`Week ${w}`"
            :aria-pressed="w === week"
            @click="week = w"
          >
            {{ w }}
          </button>
        </nav>

        <table class="data-table grid">
          <thead>
            <tr>
              <th>Day</th>
              <th>Lift</th>
              <th>Sets</th>
              <th>Reps</th>
              <th>% of max</th>
              <th>Weight</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-if="!weekRows.length">
              <td colspan="7" class="muted">Week {{ week }} is empty. Add an exercise below or copy another week.</td>
            </tr>
            <template v-for="ex in weekRows" :key="`${ex.id}-${version}`">
              <tr data-testid="row">
                <td>
                  <select aria-label="Day" :value="ex.day" @change="editExercise(ex, 'day', value($event))">
                    <option v-for="d in DAYS" :key="d" :value="d">{{ dayLabel(d) }}</option>
                  </select>
                </td>
                <td>
                  <select aria-label="Lift" :value="ex.lift" @change="editExercise(ex, 'lift', value($event))">
                    <option v-for="l in LIFTS" :key="l" :value="l">{{ LIFT_LABEL[l] }}</option>
                  </select>
                </td>
                <td><input aria-label="Sets" type="number" min="1" max="20" :value="ex.sets" @change="editExercise(ex, 'sets', value($event))" /></td>
                <td><input aria-label="Reps" type="number" min="1" max="30" :value="ex.reps" @change="editExercise(ex, 'reps', value($event))" /></td>
                <td><input aria-label="Percent" type="number" min="0" max="150" step="0.5" :value="ex.percent" @change="editExercise(ex, 'percent', value($event))" /></td>
                <td data-testid="weight" :class="{ muted: ex.weight_lb === null }">{{ weightLabel(ex.weight_lb, ex.weight_kg) }}</td>
                <td><button type="button" class="btn--ghost btn--danger btn--sm" :aria-label="`Remove ${LIFT_LABEL[ex.lift]} exercise`" @click="removeExercise(ex)">Remove</button></td>
              </tr>
              <tr v-if="rowErrors[ex.id]">
                <td colspan="7" class="error" role="alert">{{ rowErrors[ex.id] }}</td>
              </tr>
            </template>
            <tr class="grid__add">
              <td>
                <select v-model.number="draft.day" aria-label="New exercise day">
                  <option v-for="d in DAYS" :key="d" :value="d">{{ dayLabel(d) }}</option>
                </select>
              </td>
              <td>
                <select v-model="draft.lift" aria-label="New exercise lift">
                  <option v-for="l in LIFTS" :key="l" :value="l">{{ LIFT_LABEL[l] }}</option>
                </select>
              </td>
              <td><input v-model.number="draft.sets" aria-label="New exercise sets" type="number" min="1" max="20" /></td>
              <td><input v-model.number="draft.reps" aria-label="New exercise reps" type="number" min="1" max="30" /></td>
              <td><input v-model.number="draft.percent" aria-label="New exercise percent" type="number" min="0" max="150" step="0.5" /></td>
              <td />
              <td><button type="button" class="btn--primary btn--sm" :disabled="busy" @click="addExercise">Add</button></td>
            </tr>
            <tr v-if="draftError">
              <td colspan="7" class="error" role="alert">{{ draftError }}</td>
            </tr>
          </tbody>
        </table>

        <div v-if="weekRows.length" class="editor__copy">
          <label class="field">
            Copy week {{ week }} to
            <select v-model="copyTarget" aria-label="Copy to week">
              <option :value="null" disabled>Choose an empty week</option>
              <option v-for="w in copyTargets" :key="w" :value="w">Week {{ w }}</option>
            </select>
          </label>
          <button type="button" class="btn--sm" :disabled="busy || copyTarget === null" @click="copyWeek">Copy</button>
          <span v-if="!copyTargets.length" class="muted">No empty weeks left.</span>
          <span v-if="copyError" class="error" role="alert">{{ copyError }}</span>
        </div>
      </template>
    </template>

    <ConfirmModal
      v-if="confirmingDelete && program"
      title="Delete program"
      :message="`Delete “${program.name}” and all its exercises? Sessions you already logged are kept.`"
      :error="deleteError"
      @close="confirmingDelete = false"
      @confirm="removeProgram"
    />
  </section>
</template>

<style scoped>
.editor__delete {
  margin-left: auto;
}
.check {
  flex-direction: row;
  align-items: center;
}
.editor__bar,
.editor__new,
.editor__settings,
.editor__copy {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3);
  margin: var(--space-3) 0;
}
.editor__weeks {
  display: inline-flex;
  flex-wrap: wrap;
  margin: 0 0 var(--space-3) 1px;
}
.week {
  min-width: 2.25rem;
  margin: 0 0 -1px -1px;
  border-radius: 0;
}
.week:first-child {
  border-radius: var(--radius-md) 0 0 var(--radius-md);
}
.week:last-child {
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
}
.week--on,
.week--on:hover:not(:disabled) {
  position: relative;
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: #fff;
}
.week--empty:not(.week--on) {
  color: var(--text-muted);
}
.grid input[type='number'] {
  width: 5rem;
}
.grid__add td {
  background: var(--card-color);
}
</style>
