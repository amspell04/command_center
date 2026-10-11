const pad = (n: number) => String(n).padStart(2, '0')

export function toISO(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export const localToday = () => toISO(new Date())

// ISO date strings parse as UTC; build a local date instead so weekdays do not shift.
export function parseISO(iso: string): Date {
  const [y = 0, m = 1, d = 1] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** The seven dates of the Monday-to-Sunday week containing `iso`, matching the backend's week. */
export function weekDates(iso: string): string[] {
  const d = parseISO(iso)
  const monday = new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7))
  return Array.from({ length: 7 }, (_, i) => toISO(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)))
}

export const weekdayShort = (iso: string) => parseISO(iso).toLocaleDateString(undefined, { weekday: 'short' })
export const dayOfMonth = (iso: string) => parseISO(iso).getDate()
export const longDate = (iso: string) =>
  parseISO(iso).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })

export function duration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? (m ? `${h} h ${m} min` : `${h} h`) : `${m} min`
}
