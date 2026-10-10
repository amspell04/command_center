<script setup lang="ts">
import { ref } from 'vue'
import { agentsApi, errorMessage, tasksApi } from '../api'
import type { DayPlan, SweepProposal, Task } from '../types'

const emit = defineEmits<{ updated: [task: Task] }>()

const plan = ref<DayPlan | null>(null)
const proposals = ref<SweepProposal[] | null>(null)
const busy = ref<'plan' | 'sweep' | null>(null)
const error = ref<string | null>(null)

async function planDay() {
  busy.value = 'plan'
  error.value = null
  try {
    plan.value = await agentsApi.planDay()
  } catch (e) {
    error.value = errorMessage(e)
  }
  busy.value = null
}

async function sweep() {
  busy.value = 'sweep'
  error.value = null
  try {
    proposals.value = (await agentsApi.overdueSweep()).proposals
  } catch (e) {
    error.value = errorMessage(e)
  }
  busy.value = null
}

const drop = (p: SweepProposal) => {
  proposals.value = proposals.value?.filter((x) => x.task_id !== p.task_id) ?? null
}

// A proposal stays in the list if the update fails, so it can be retried.
async function accept(p: SweepProposal) {
  error.value = null
  try {
    emit('updated', await tasksApi.update(p.task_id, { due_date: p.new_due_date }))
    drop(p)
  } catch (e) {
    error.value = errorMessage(e)
  }
}
</script>

<template>
  <div class="agent">
    <div class="agent__buttons">
      <button :disabled="busy !== null" @click="planDay">{{ busy === 'plan' ? 'Planning…' : 'Plan my day' }}</button>
      <button :disabled="busy !== null" @click="sweep">{{ busy === 'sweep' ? 'Checking…' : 'Overdue sweep' }}</button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section v-if="plan" aria-label="Day plan">
      <h3>Plan for {{ plan.date }}</h3>
      <p v-if="!plan.items.length">Nothing to plan.</p>
      <ol v-else>
        <li v-for="item in plan.items" :key="item.task_id">
          {{ item.title }}<small v-if="item.reason"> — {{ item.reason }}</small>
        </li>
      </ol>
      <button @click="plan = null">Dismiss</button>
    </section>

    <section v-if="proposals" aria-label="Overdue sweep">
      <h3>Proposed new dates</h3>
      <p v-if="!proposals.length">No overdue tasks to reschedule.</p>
      <ul v-else>
        <li v-for="p in proposals" :key="p.task_id">
          {{ p.title }}: {{ p.current_due_date }} → {{ p.new_due_date }}<small> — {{ p.reason }}</small>
          <button :aria-label="`Accept ${p.title}`" @click="accept(p)">Accept</button>
          <button :aria-label="`Reject ${p.title}`" @click="drop(p)">Reject</button>
        </li>
      </ul>
      <button @click="proposals = null">Dismiss</button>
    </section>
  </div>
</template>

<style scoped>
.agent__buttons {
  display: flex;
  gap: 0.5rem;
  margin: 0.5rem 0;
}
.error {
  color: #c33;
}
ul {
  padding-left: 0;
  list-style: none;
}
</style>
