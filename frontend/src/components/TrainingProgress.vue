<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { trainingApi } from '../api'
import type { E1RMPoint, Lift } from '../types'
import { longDate } from '../utils/dates'
import { chartPoints, LIFT_LABEL, LIFTS, personalRecords } from '../utils/training'

// Estimated 1RM per lift over time (best set of each session, Epley), personal records. `refreshKey` changes when a workout is saved or deleted.
const props = defineProps<{ refreshKey?: number }>()

const W = 320
const H = 110

const history = ref<Record<Lift, E1RMPoint[]>>({ SQUAT: [], BENCH: [], DEADLIFT: [] })
const failed = ref<Lift[]>([])
const loading = ref(true)

const summaries = computed(() =>
  LIFTS.map((lift) => {
    const points = history.value[lift]
    const records = personalRecords(points)
    const latest = points[points.length - 1]
    const best = records[records.length - 1]
    return {
      lift,
      points,
      latest,
      best,
      gain: points.length > 1 ? Math.round((latest!.estimated_1rm_lb - points[0]!.estimated_1rm_lb) * 10) / 10 : null,
      records: [...records].reverse().slice(0, 3),
      chart: chartPoints(points, W, H),
    }
  }),
)
const failedLabel = computed(() => failed.value.map((l) => LIFT_LABEL[l]).join(', '))
const anyData = computed(() => LIFTS.some((l) => history.value[l].length))

async function load() {
  const results = await Promise.allSettled(LIFTS.map((l) => trainingApi.progress(l)))
  failed.value = []
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') history.value[LIFTS[i]!] = r.value
    else failed.value.push(LIFTS[i]!)
  })
  loading.value = false
}

const polyline = (pts: { x: number; y: number }[]) => pts.map((p) => `${p.x},${p.y}`).join(' ')

watch(() => props.refreshKey, load)
onMounted(load)
</script>

<template>
  <section class="section progress">
    <h2>Progress</h2>
    <p v-if="loading" class="muted">Loading…</p>
    <template v-else>
      <p v-if="failed.length" class="error" role="alert">
        Could not load progress for {{ failedLabel }}.
      </p>
      <p v-if="!anyData && !failed.length" class="muted">Log a workout to start tracking your estimated 1RM.</p>

      <div class="progress__lifts">
        <article v-for="s in summaries" :key="s.lift" class="lift" :data-testid="`lift-${s.lift}`">
          <h3>{{ LIFT_LABEL[s.lift] }}</h3>
          <p v-if="!s.latest" class="muted">No sets logged yet.</p>
          <template v-else>
            <p class="lift__now" data-testid="latest">
              <span class="lift__num">{{ s.latest.estimated_1rm_lb }} lb / {{ s.latest.estimated_1rm_kg }} kg</span>
              <small class="muted">estimated 1RM on {{ longDate(s.latest.date) }}</small>
            </p>
            <p v-if="s.gain !== null" class="lift__gain" data-testid="gain">
              <span class="badge" :class="s.gain >= 0 ? 'badge--ok' : 'badge--danger'">{{ s.gain >= 0 ? '+' : '' }}{{ s.gain }} lb</span>
              since {{ longDate(s.points[0]!.date) }}
            </p>
            <svg
              :viewBox="`0 0 ${W} ${H}`"
              class="lift__chart"
              role="img"
              :aria-label="`${LIFT_LABEL[s.lift]} estimated 1RM, ${s.points.length} ${s.points.length === 1 ? 'session' : 'sessions'}`"
            >
              <line x1="0" :x2="W" :y1="H - 0.5" :y2="H - 0.5" class="lift__axis" />
              <polyline v-if="s.chart.length > 1" :points="polyline(s.chart)" fill="none" stroke="currentColor" stroke-width="2" />
              <circle v-for="c in s.chart" :key="c.point.date" :cx="c.x" :cy="c.y" r="3.5" fill="currentColor">
                <title>{{ c.point.date }}: {{ c.point.estimated_1rm_lb }} lb / {{ c.point.estimated_1rm_kg }} kg</title>
              </circle>
            </svg>
            <details class="lift__records">
              <summary>Records</summary>
              <ul class="lift__prs" data-testid="records">
                <li v-for="r in s.records" :key="r.date">
                  {{ r.estimated_1rm_lb }} lb / {{ r.estimated_1rm_kg }} kg <span class="muted">· {{ longDate(r.date) }}</span>
                </li>
              </ul>
            </details>
          </template>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-muted);
}
.progress__lifts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--space-4);
}
.lift {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--card-color);
}
.lift__now {
  display: flex;
  flex-direction: column;
  margin: 0;
}
.lift__num {
  font-size: var(--text-xl);
  font-weight: 700;
  letter-spacing: -0.01em;
}
.lift__gain {
  margin: var(--space-1) 0 var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
}
.lift__records {
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-color);
}
.lift__records summary {
  cursor: pointer;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.lift__records ul {
  margin-top: var(--space-2);
}
.lift__axis {
  stroke: var(--border-strong);
  stroke-width: 1;
}
.lift__chart {
  width: 100%;
  height: auto;
  color: var(--accent-color);
}
.lift__prs {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--text-sm);
}
</style>
