import type { E1RMPoint, Exercise, Lift } from '../types'
import { parseISO } from './dates'

export const LIFTS: Lift[] = ['SQUAT', 'BENCH', 'DEADLIFT']

export const LIFT_LABEL: Record<Lift, string> = { SQUAT: 'Squat', BENCH: 'Bench', DEADLIFT: 'Deadlift' }

const LB_PER_KG = 2.20462262185

/** Same conversion and rounding as the backend, for showing kg while a value is still being typed. */
export const lbToKg = (lb: number) => Math.round((lb / LB_PER_KG) * 10) / 10

/** "315 lb / 142.9 kg", or a dash when there is no weight. */
export const weightLabel = (lb: number | null, kg: number | null) => (lb === null || kg === null ? '–' : `${lb} lb / ${kg} kg`)

/** Backend order: day, then lift, then heaviest percentage first. */
export function sortExercises(rows: Exercise[]): Exercise[] {
  return [...rows].sort(
    (a, b) => a.day - b.day || LIFTS.indexOf(a.lift) - LIFTS.indexOf(b.lift) || b.percent - a.percent,
  )
}

/** Points (oldest first) that beat every earlier one. The first point counts as a record. */
export function personalRecords(points: E1RMPoint[]): E1RMPoint[] {
  let best = 0
  return points.filter((p) => {
    const isRecord = p.estimated_1rm_lb > best
    if (isRecord) best = p.estimated_1rm_lb
    return isRecord
  })
}

/** Whole days from `from` to `to` (negative if `to` is earlier). */
export const daysBetween = (from: string, to: string) =>
  Math.round((parseISO(to).getTime() - parseISO(from).getTime()) / 86_400_000)

export interface ChartPoint {
  x: number
  y: number
  point: E1RMPoint
}

/** Positions points in a `width` x `height` box: x by calendar date, y by lb, with `pad` kept clear on every side. */
export function chartPoints(points: E1RMPoint[], width: number, height: number, pad = 8): ChartPoint[] {
  if (!points.length) return []
  const first = points[0]!.date
  const span = daysBetween(first, points[points.length - 1]!.date)
  const values = points.map((p) => p.estimated_1rm_lb)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  return points.map((point) => ({
    point,
    x: span === 0 ? width / 2 : pad + (daysBetween(first, point.date) / span) * (width - 2 * pad),
    y: hi === lo ? height / 2 : pad + (1 - (point.estimated_1rm_lb - lo) / (hi - lo)) * (height - 2 * pad),
  }))
}
