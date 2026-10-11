import { ref } from 'vue'
import { trainingApi } from '../api'
import type { GymDay } from '../types'

// This week's gym days (planned or logged), shared by the week timeline and the today panel.
// The markers are a bonus on top of the task views, so a failed load just shows none.
const days = ref<GymDay[]>([])
let inflight: Promise<void> | null = null

function load(): Promise<void> {
  if (!inflight) {
    inflight = (async () => {
      try {
        days.value = await trainingApi.week()
      } catch {
        days.value = []
      } finally {
        inflight = null
      }
    })()
  }
  return inflight
}

export function useGymWeek() {
  return { days, load, forDate: (date: string) => days.value.find((d) => d.date === date) }
}
